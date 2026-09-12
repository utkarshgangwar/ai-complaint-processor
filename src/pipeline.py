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
        """Pre-check for empty or completely blank input."""
        words = doc_text.strip().split()
        if len(words) < 3:
            return False, "Insufficient content: Text body has fewer than 3 words."
        return True, ""

    def _validate_record_completeness(self, structured_dict: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validates case records. Routes to insufficient info only if 
        all three core identity/contact fields (customer_name, email, phone_number) are absent.
        """
        invalid_markers = {"", "n/a", "na", "none", "unknown", "null", "undefined", "not provided", "unspecified", "valued customer", "customer", "client", "user"}

        # 1. Check Customer Name
        raw_cust_name = structured_dict.get("customer_name")
        cust_name = str(raw_cust_name).strip().lower() if raw_cust_name is not None else ""
        has_valid_name = bool(cust_name and cust_name not in invalid_markers)

        # 2. Check Email
        raw_email = structured_dict.get("email")
        email_str = str(raw_email).strip().lower() if raw_email is not None else ""
        has_valid_email = bool(email_str and email_str not in invalid_markers and "@" in email_str)

        # 3. Check Phone Number
        raw_phone = structured_dict.get("phone_number")
        phone_str = str(raw_phone).strip().lower() if raw_phone is not None else ""
        has_valid_phone = bool(phone_str and phone_str not in invalid_markers)

        # If all three identity/contact fields are missing, flag as insufficient info
        if not has_valid_name and not has_valid_email and not has_valid_phone:
            return False, "Insufficient info: Missing customer name, email, and phone number."

        # 4. Issue / Inquiry Description Check
        raw_desc = structured_dict.get("issue_description")
        issue_desc = str(raw_desc).strip() if raw_desc is not None else ""
        if not issue_desc or issue_desc.lower() in invalid_markers or len(issue_desc.split()) < 2:
            return False, "Insufficient info: Missing issue or inquiry description."

        # Set default fallback category if blank
        raw_cat = structured_dict.get("complaint_category")
        if not raw_cat or str(raw_cat).strip().lower() in invalid_markers:
            structured_dict["complaint_category"] = "General Inquiry"

        return True, ""

    def _has_valid_email(self, structured_dict: Dict[str, Any]) -> bool:
        """Determines if a valid, sendable customer email address exists."""
        raw_email = structured_dict.get("email")
        if raw_email is None:
            return False
        email_str = str(raw_email).strip().lower()
        invalid_markers = {"", "n/a", "na", "none", "unknown", "null", "undefined", "not provided"}
        return bool(email_str and email_str not in invalid_markers and "@" in email_str)

    def _create_insufficient_record(
        self,
        file_path: Path,
        reason: str,
        start_time: float
    ) -> Tuple[Dict[str, Any], bool, str]:
        """Suppresses downstream artifact generation and records an insufficient entry."""
        file_stem = get_base_filename(file_path)

        for target_artifact in [
            self.structured_dir / f"{file_stem}.json",
            self.emails_dir / f"{file_stem}_email.txt",
            self.summaries_dir / f"{file_stem}_summary.txt"
        ]:
            if target_artifact.exists():
                target_artifact.unlink()

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

    def process_single_document(self, file_path: Path) -> Tuple[Dict[str, Any], bool, str]:
        """Processes document and generates response email only when customer email is present."""
        start_time = time.time()
        file_stem = get_base_filename(file_path)
        LOGGER.info(f"--- Processing: {file_path.name} ---")

        # 1. Document Ingestion
        doc_data = load_document(file_path)
        doc_text = doc_data.get("content", "")
        if not doc_text.strip():
            raise ValueError(f"No extractable text found in file: {file_path.name}")

        # 2. Text Sparseness Check
        is_sufficient, reason = self._check_content_sufficiency(doc_text)
        if not is_sufficient:
            LOGGER.warning(f"{file_path.name} flagged as insufficient: {reason}")
            return self._create_insufficient_record(file_path, reason, start_time)

        # 3. Structured Extraction
        extracted_data = self.chains.run_extraction(doc_text)
        structured_dict = extracted_data.model_dump()

        # 4. Completeness Validation
        is_complete, completeness_reason = self._validate_record_completeness(structured_dict)
        if not is_complete:
            LOGGER.warning(f"{file_path.name} routed to insufficient info: {completeness_reason}")
            return self._create_insufficient_record(file_path, completeness_reason, start_time)

        # 5. Save Structured JSON Data
        json_path = self.structured_dir / f"{file_stem}.json"
        save_json_file(structured_dict, json_path)

        # 6. Customer Email Generation: Generated ONLY if a valid email address is present
        email_path_str = ""
        email_file = self.emails_dir / f"{file_stem}_email.txt"

        if self._has_valid_email(structured_dict):
            customer_email = self.chains.run_email_generation(extracted_data)
            save_text_file(customer_email, email_file)
            email_path_str = str(email_file.relative_to(BASE_DIR))
            LOGGER.info(f"Generated customer email for {structured_dict.get('customer_name')} ({structured_dict.get('email')})")
        else:
            if email_file.exists():
                email_file.unlink()
            LOGGER.info(f"Skipping email generation for {file_path.name} (no email address found).")

        # 7. Management Case Summary Memo
        case_summary = self.chains.run_summary_generation(extracted_data, doc_text)
        summary_path = self.summaries_dir / f"{file_stem}_summary.txt"
        save_text_file(case_summary, summary_path)

        latency = round(time.time() - start_time, 2)
        LOGGER.info(f"Completed processing for {file_path.name} in {latency}s")

        record = {
            "file_name": file_path.name,
            "latency_seconds": latency,
            **structured_dict,
            "structured_data_path": str(json_path.relative_to(BASE_DIR)),
            "customer_email_path": email_path_str,
            "case_summary_path": str(summary_path.relative_to(BASE_DIR)),
        }
        return record, False, ""

    def run(self, progress_callback=None, force_reprocess: bool = False) -> pd.DataFrame:
        """Runs batch processing, handles caching, and synchronizes manifest and logs."""
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

            # Cache Hit: Valid, fully populated record
            if (
                not force_reprocess
                and file_path.name in manifest
                and manifest[file_path.name] == file_hash
                and file_path.name not in current_insufficient
                and json_path.exists()
                and summary_path.exists()
            ):
                LOGGER.info(f"Skipping {file_path.name} (identical hash, cached complete).")
                try:
                    with open(json_path, "r", encoding="utf-8") as jf:
                        cached_dict = json.load(jf)

                    cached_email_path = str(email_path.relative_to(BASE_DIR)) if email_path.exists() else ""

                    cached_record = {
                        "file_name": file_path.name,
                        "latency_seconds": 0.0,
                        **cached_dict,
                        "structured_data_path": str(json_path.relative_to(BASE_DIR)),
                        "customer_email_path": cached_email_path,
                        "case_summary_path": str(summary_path.relative_to(BASE_DIR)),
                    }
                    processed_records.append(cached_record)
                    current_errors.pop(file_path.name, None)
                    current_insufficient.pop(file_path.name, None)
                    continue
                except Exception as cache_err:
                    LOGGER.warning(f"Cache read failed for {file_path.name}, running fresh extraction: {cache_err}")

            # Cache Hit: Insufficient file
            if (
                not force_reprocess
                and file_path.name in manifest
                and manifest[file_path.name] == file_hash
                and file_path.name in current_insufficient
            ):
                LOGGER.info(f"Skipping {file_path.name} (identical hash, cached insufficient).")
                current_errors.pop(file_path.name, None)
                continue

            # Run Document Processing
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

        # Persist registries
        self._save_manifest(manifest)
        self._save_json_record(current_errors, self.errors_path)
        self._save_json_record(current_insufficient, self.insufficient_path)

        # Save clean final report containing only valid processed cases
        if processed_records:
            df = pd.DataFrame(processed_records)
            self.csv_output_path.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(self.csv_output_path, index=False, encoding="utf-8")
            LOGGER.info(f"Consolidated final report generated at: {self.csv_output_path}")
            return df
        else:
            if self.csv_output_path.exists():
                self.csv_output_path.unlink()

        return pd.DataFrame()


def run_batch_pipeline(force_reprocess: bool = False) -> pd.DataFrame:
    """Direct callable interface."""
    pipeline = BatchProcessingPipeline()
    return pipeline.run(force_reprocess=force_reprocess)