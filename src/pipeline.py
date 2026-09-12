import json
import os
import time
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Tuple

from src.config import CONFIG, BASE_DIR, LOGGER
from src.document_loader import load_document, DocumentIngestionError
from src.chains import ComplaintProcessingChains
from src.utils import save_json_file, save_text_file, get_base_filename, compute_file_hash


class BatchProcessingPipeline:
    def __init__(self):
        self.chains = ComplaintProcessingChains()
        self.paths = CONFIG.get("paths", {})

        self.data_dir = BASE_DIR / self.paths.get("data_dir", "data")
        self.structured_dir = BASE_DIR / self.paths.get("structured_data_dir", "output/structured_data")
        self.emails_dir = BASE_DIR / self.paths.get("customer_emails_dir", "output/customer_emails")
        self.summaries_dir = BASE_DIR / self.paths.get("case_summaries_dir", "output/case_summaries")
        self.csv_output_path = BASE_DIR / self.paths.get("final_report_csv", "output/final_report.csv")
        self.manifest_path = self.csv_output_path.parent / ".processed_manifest.json"
        self.errors_path = self.csv_output_path.parent / ".processing_errors.json"
        self.insufficient_path = self.csv_output_path.parent / ".insufficient_records.json"

        self.supported_extensions = tuple(
            CONFIG.get("processing", {}).get("supported_extensions", [".pdf", ".docx", ".txt"])
        )

    def _load_manifest(self) -> Dict[str, str]:
        """Loads cached SHA-256 file hashes from disk."""
        if self.manifest_path.exists():
            try:
                with open(self.manifest_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                LOGGER.warning(f"Failed to read cache manifest, creating fresh one: {e}")
                return {}
        return {}

    def _save_manifest(self, manifest: Dict[str, str]):
        """Persists updated file hashes to disk."""
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

    def _load_json_record(self, target_path: Path) -> Dict[str, str]:
        """Loads a generic JSON map from disk."""
        if target_path.exists():
            try:
                with open(target_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                LOGGER.warning(f"Failed to read record from {target_path.name}: {e}")
                return {}
        return {}

    def _save_json_record(self, data: Dict[str, str], target_path: Path):
        """Persists a generic JSON map to disk."""
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def _check_content_sufficiency(self, doc_text: str) -> Tuple[bool, str]:
        """
        Heuristic check for empty, truncated, or unintelligible input.
        """
        words = doc_text.strip().split()
        if len(words) < 8:
            return False, "Insufficient content: Text body has fewer than 8 words."

        # Detect repeated punctuation or uniform characters (e.g., 'asdfasdf', '?????')
        alphanumeric_chars = [c for c in doc_text if c.isalnum()]
        if len(alphanumeric_chars) < 15:
            return False, "Absurd content: File lacks sufficient alphanumeric text."

        return True, ""

    def process_single_document(self, file_path: Path) -> Tuple[Dict[str, Any], bool, str]:
        """
        Runs the extraction workflow for a single file.
        Returns: (record_dict, is_insufficient, observation_reason)
        """
        start_time = time.time()
        file_stem = get_base_filename(file_path)
        LOGGER.info(f"--- Processing: {file_path.name} ---")

        # 1. Ingestion
        doc_data = load_document(file_path)
        doc_text = doc_data["content"]
        if not doc_text.strip():
            raise ValueError(f"No extractable text found in file: {file_path.name}")

        # 2. Pre-check for absurd / sparse input
        is_sufficient, reason = self._check_content_sufficiency(doc_text)
        if not is_sufficient:
            LOGGER.warning(f"{file_path.name} flagged as insufficient/absurd: {reason}")
            # Do NOT generate customer email or summary memo
            # Clean up artifacts if they existed from prior runs
            for art in [self.emails_dir / f"{file_stem}_email.txt", self.summaries_dir / f"{file_stem}_summary.txt"]:
                if art.exists():
                    art.unlink()

            latency = round(time.time() - start_time, 2)
            record = {
                "file_name": file_path.name,
                "latency_seconds": latency,
                "customer_name": "N/A",
                "complaint_category": "Insufficient Data",
                "issue_description": reason,
                "case_status": "Closed",
                "escalation_required": False,
                "structured_data_path": "",
                "customer_email_path": "",
                "case_summary_path": "",
            }
            return record, True, reason

        # 3. Structured Extraction
        extracted_data = self.chains.run_extraction(doc_text)
        structured_dict = extracted_data.model_dump()

        # Check semantic extraction output for nonsense/hollow cases
        issue_desc = str(structured_dict.get("issue_description", "")).strip()
        cat = str(structured_dict.get("complaint_category", "")).strip().lower()

        if len(issue_desc.split()) < 4 or cat in ["unknown", "none", "n/a"]:
            insuff_reason = "Model evaluated content as unintelligible, absurd, or missing actionable grievance details."
            LOGGER.warning(f"{file_path.name} flagged as insufficient post-extraction: {insuff_reason}")

            # Save partial extraction JSON for audit trail
            json_path = self.structured_dir / f"{file_stem}.json"
            save_json_file(structured_dict, json_path)

            # Ensure email and summary are NOT produced or retained
            for art in [self.emails_dir / f"{file_stem}_email.txt", self.summaries_dir / f"{file_stem}_summary.txt"]:
                if art.exists():
                    art.unlink()

            latency = round(time.time() - start_time, 2)
            record = {
                "file_name": file_path.name,
                "latency_seconds": latency,
                **structured_dict,
                "structured_data_path": str(json_path.relative_to(BASE_DIR)),
                "customer_email_path": "",
                "case_summary_path": "",
            }
            return record, True, insuff_reason

        # 4. Standard Flow: Valid complaint content -> Generate all artifacts
        json_path = self.structured_dir / f"{file_stem}.json"
        save_json_file(structured_dict, json_path)

        customer_email = self.chains.run_email_generation(extracted_data)
        email_path = self.emails_dir / f"{file_stem}_email.txt"
        save_text_file(customer_email, email_path)

        case_summary = self.chains.run_summary_generation(extracted_data, doc_text)
        summary_path = self.summaries_dir / f"{file_stem}_summary.txt"
        save_text_file(case_summary, summary_path)

        latency = round(time.time() - start_time, 2)
        LOGGER.info(f"Completed {file_path.name} in {latency}s")

        record = {
            "file_name": file_path.name,
            "latency_seconds": latency,
            **structured_dict,
            "structured_data_path": str(json_path.relative_to(BASE_DIR)),
            "customer_email_path": str(email_path.relative_to(BASE_DIR)),
            "case_summary_path": str(summary_path.relative_to(BASE_DIR)),
        }
        return record, False, ""

    def run(self, progress_callback=None, force_reprocess: bool = False) -> pd.DataFrame:
        """Processes all valid documents with SHA-256 caching and tracks unhandled exceptions & insufficient files."""
        files = [
            f for f in self.data_dir.iterdir()
            if f.is_file() and f.suffix.lower() in self.supported_extensions
        ]

        total_files = len(files)
        LOGGER.info(f"Found {total_files} eligible documents for batch processing in '{self.data_dir}'.")

        if total_files == 0:
            LOGGER.warning("No valid documents found to process.")
            self._save_json_record({}, self.errors_path)
            self._save_json_record({}, self.insufficient_path)
            return pd.DataFrame()

        manifest = {} if force_reprocess else self._load_manifest()
        current_errors = {} if force_reprocess else self._load_json_record(self.errors_path)
        current_insufficient = {} if force_reprocess else self._load_json_record(self.insufficient_path)
        processed_records: List[Dict[str, Any]] = []

        for index, file_path in enumerate(files, start=1):
            if progress_callback:
                progress_callback(index, total_files, file_path.name)

            file_stem = get_base_filename(file_path)
            json_path = self.structured_dir / f"{file_stem}.json"
            email_path = self.emails_dir / f"{file_stem}_email.txt"
            summary_path = self.summaries_dir / f"{file_stem}_summary.txt"

            file_hash = compute_file_hash(file_path)

            # -------------------------------------------------------------
            # CACHE HIT: Valid previously processed document
            # -------------------------------------------------------------
            if (
                not force_reprocess
                and file_path.name in manifest
                and manifest[file_path.name] == file_hash
                and file_path.name not in current_insufficient
                and json_path.exists()
                and email_path.exists()
                and summary_path.exists()
            ):
                LOGGER.info(f"Skipping {file_path.name} (identical hash, cached).")
                try:
                    with open(json_path, "r", encoding="utf-8") as jf:
                        cached_dict = json.load(jf)

                    cached_record = {
                        "file_name": file_path.name,
                        "latency_seconds": 0.0,
                        **cached_dict,
                        "structured_data_path": str(json_path.relative_to(BASE_DIR)),
                        "customer_email_path": str(email_path.relative_to(BASE_DIR)),
                        "case_summary_path": str(summary_path.relative_to(BASE_DIR)),
                    }
                    processed_records.append(cached_record)
                    current_errors.pop(file_path.name, None)
                    current_insufficient.pop(file_path.name, None)
                    continue
                except Exception as cache_err:
                    LOGGER.warning(f"Cache read failed for {file_path.name}, executing full run: {cache_err}")

            # -------------------------------------------------------------
            # CACHE HIT: Insufficient document previously cataloged
            # -------------------------------------------------------------
            if (
                not force_reprocess
                and file_path.name in manifest
                and manifest[file_path.name] == file_hash
                and file_path.name in current_insufficient
            ):
                LOGGER.info(f"Skipping {file_path.name} (identical hash, known insufficient).")
                current_errors.pop(file_path.name, None)
                continue

            # -------------------------------------------------------------
            # RUN WORKFLOW
            # -------------------------------------------------------------
            try:
                record, is_insufficient, reason = self.process_single_document(file_path)
                manifest[file_path.name] = file_hash
                current_errors.pop(file_path.name, None)

                if is_insufficient:
                    current_insufficient[file_path.name] = reason
                else:
                    current_insufficient.pop(file_path.name, None)
                    processed_records.append(record)

            except (DocumentIngestionError, ValueError) as err:
                error_msg = str(err)
                LOGGER.error(f"Validation/Ingestion error on {file_path.name}: {error_msg}")
                current_errors[file_path.name] = error_msg
                current_insufficient.pop(file_path.name, None)
            except Exception as unhandled:
                error_msg = f"{type(unhandled).__name__}: {str(unhandled)}"
                LOGGER.exception(f"Unhandled error processing {file_path.name}: {error_msg}")
                current_errors[file_path.name] = error_msg
                current_insufficient.pop(file_path.name, None)

        # Persist manifest, errors, and insufficient registry
        self._save_manifest(manifest)
        self._save_json_record(current_errors, self.errors_path)
        self._save_json_record(current_insufficient, self.insufficient_path)

        # Generate Consolidated CSV (clean, valid cases only)
        if processed_records:
            df = pd.DataFrame(processed_records)
            self.csv_output_path.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(self.csv_output_path, index=False, encoding="utf-8")
            LOGGER.info(f"Consolidated final report generated at: {self.csv_output_path}")
            return df

        return pd.DataFrame()


def run_batch_pipeline(force_reprocess: bool = False) -> pd.DataFrame:
    """Direct callable interface."""
    pipeline = BatchProcessingPipeline()
    return pipeline.run(force_reprocess=force_reprocess)