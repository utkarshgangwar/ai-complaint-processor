import json
import os
import time
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any

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
                LOGGER.warning(f"Failed to read cache manifest, creating a fresh one: {e}")
                return {}
        return {}

    def _save_manifest(self, manifest: Dict[str, str]):
        """Persists updated file hashes to disk."""
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

    def _load_errors(self) -> Dict[str, str]:
        """Loads existing processing error records from disk."""
        if self.errors_path.exists():
            try:
                with open(self.errors_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                LOGGER.warning(f"Failed to read error records: {e}")
                return {}
        return {}

    def _save_errors(self, errors: Dict[str, str]):
        """Persists updated processing errors to disk."""
        self.errors_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.errors_path, "w", encoding="utf-8") as f:
            json.dump(errors, f, indent=2)

    def process_single_document(self, file_path: Path) -> Dict[str, Any]:
        """Runs the full 3-step LLM extraction and generation workflow for a single file."""
        start_time = time.time()
        file_stem = get_base_filename(file_path)
        LOGGER.info(f"--- Processing: {file_path.name} ---")

        # 1. Ingestion
        doc_data = load_document(file_path)
        doc_text = doc_data["content"]
        if not doc_text.strip():
            raise ValueError(f"No extractable text found in file: {file_path.name}")

        # 2. Structured Extraction
        extracted_data = self.chains.run_extraction(doc_text)
        structured_dict = extracted_data.model_dump()

        # Save structured JSON
        json_path = self.structured_dir / f"{file_stem}.json"
        save_json_file(structured_dict, json_path)

        # 3A. Customer Email Generation
        customer_email = self.chains.run_email_generation(extracted_data)
        email_path = self.emails_dir / f"{file_stem}_email.txt"
        save_text_file(customer_email, email_path)

        # 3B. Management Case Summary Generation
        case_summary = self.chains.run_summary_generation(extracted_data, doc_text)
        summary_path = self.summaries_dir / f"{file_stem}_summary.txt"
        save_text_file(case_summary, summary_path)

        latency = round(time.time() - start_time, 2)
        LOGGER.info(f"Completed {file_path.name} in {latency}s")

        # Compile flat record for the CSV report
        record = {
            "file_name": file_path.name,
            "latency_seconds": latency,
            **structured_dict,
            "structured_data_path": str(json_path.relative_to(BASE_DIR)),
            "customer_email_path": str(email_path.relative_to(BASE_DIR)),
            "case_summary_path": str(summary_path.relative_to(BASE_DIR)),
        }
        return record

    def run(self, progress_callback=None, force_reprocess: bool = False) -> pd.DataFrame:
        """Processes all valid documents with SHA-256 caching and tracks unhandled exceptions."""
        files = [
            f for f in self.data_dir.iterdir()
            if f.is_file() and f.suffix.lower() in self.supported_extensions
        ]

        total_files = len(files)
        LOGGER.info(f"Found {total_files} eligible documents for batch processing in '{self.data_dir}'.")

        if total_files == 0:
            LOGGER.warning("No valid documents found to process.")
            self._save_errors({})
            return pd.DataFrame()

        manifest = {} if force_reprocess else self._load_manifest()
        current_errors = {} if force_reprocess else self._load_errors()
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
            # CACHE HIT: Reuse existing disk artifacts without LLM calls
            # -------------------------------------------------------------
            if (
                not force_reprocess
                and file_path.name in manifest
                and manifest[file_path.name] == file_hash
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
                    # Clear error record if previously logged
                    current_errors.pop(file_path.name, None)
                    continue
                except Exception as cache_err:
                    LOGGER.warning(f"Cache read failed for {file_path.name}, executing full run: {cache_err}")

            # -------------------------------------------------------------
            # CACHE MISS / FORCED RUN: Execute LLM Workflow
            # -------------------------------------------------------------
            try:
                record = self.process_single_document(file_path)
                processed_records.append(record)
                manifest[file_path.name] = file_hash
                # Success removes previous failure records
                current_errors.pop(file_path.name, None)
            except (DocumentIngestionError, ValueError) as err:
                error_msg = str(err)
                LOGGER.error(f"Validation/Ingestion error on {file_path.name}: {error_msg}")
                current_errors[file_path.name] = error_msg
            except Exception as unhandled:
                error_msg = f"{type(unhandled).__name__}: {str(unhandled)}"
                LOGGER.exception(f"Unhandled error processing {file_path.name}: {error_msg}")
                current_errors[file_path.name] = error_msg

        # Persist manifest and error tracking states
        self._save_manifest(manifest)
        self._save_errors(current_errors)

        # Generate Consolidated CSV
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