import os
import time
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any

from src.config import CONFIG, BASE_DIR, LOGGER
from src.document_loader import load_document, DocumentIngestionError
from src.chains import ComplaintProcessingChains
from src.utils import save_json_file, save_text_file, get_base_filename

class BatchProcessingPipeline:
    def __init__(self):
        self.chains = ComplaintProcessingChains()
        self.paths = CONFIG.get("paths", {})
        
        self.data_dir = BASE_DIR / self.paths.get("data_dir", "data")
        self.structured_dir = BASE_DIR / self.paths.get("structured_data_dir", "output/structured_data")
        self.emails_dir = BASE_DIR / self.paths.get("customer_emails_dir", "output/customer_emails")
        self.summaries_dir = BASE_DIR / self.paths.get("case_summaries_dir", "output/case_summaries")
        self.csv_output_path = BASE_DIR / self.paths.get("final_report_csv", "output/final_report.csv")
        
        self.supported_extensions = tuple(
            CONFIG.get("processing", {}).get("supported_extensions", [".pdf", ".docx", ".txt"])
        )

    def process_single_document(self, file_path: Path) -> Dict[str, Any]:
        """Runs the 3-step workflow for a single file[cite: 1]."""
        start_time = time.time()
        file_stem = get_base_filename(file_path)
        LOGGER.info(f"--- Processing: {file_path.name} ---")

        # 1. Ingestion[cite: 1]
        doc_data = load_document(file_path)
        doc_text = doc_data["content"]
        if not doc_text.strip():
            raise ValueError(f"No extractable text found in file: {file_path.name}")

        # 2. Structured Extraction[cite: 1]
        extracted_data = self.chains.run_extraction(doc_text)
        structured_dict = extracted_data.model_dump()
        
        # Save structured JSON[cite: 1]
        json_path = self.structured_dir / f"{file_stem}.json"
        save_json_file(structured_dict, json_path)

        # 3A. Customer Email Generation[cite: 1]
        customer_email = self.chains.run_email_generation(extracted_data)
        email_path = self.emails_dir / f"{file_stem}_email.txt"
        save_text_file(customer_email, email_path)

        # 3B. Management Case Summary Generation[cite: 1]
        case_summary = self.chains.run_summary_generation(extracted_data, doc_text)
        summary_path = self.summaries_dir / f"{file_stem}_summary.txt"
        save_text_file(case_summary, summary_path)

        latency = round(time.time() - start_time, 2)
        LOGGER.info(f"Completed {file_path.name} in {latency}s")

        # Compile flat record for the CSV report[cite: 1]
        record = {
            "file_name": file_path.name,
            "latency_seconds": latency,
            **structured_dict,
            "structured_data_path": str(json_path.relative_to(BASE_DIR)),
            "customer_email_path": str(email_path.relative_to(BASE_DIR)),
            "case_summary_path": str(summary_path.relative_to(BASE_DIR)),
        }
        return record

    def run(self, progress_callback=None) -> pd.DataFrame:
        """Processes all valid documents in the data folder and compiles a CSV report[cite: 1]."""
        files = [
            f for f in self.data_dir.iterdir()
            if f.is_file() and f.suffix.lower() in self.supported_extensions
        ]

        total_files = len(files)
        LOGGER.info(f"Found {total_files} eligible documents for batch processing in '{self.data_dir}'.")

        if total_files == 0:
            LOGGER.warning("No valid documents found to process.")
            return pd.DataFrame()

        processed_records: List[Dict[str, Any]] = []

        for index, file_path in enumerate(files, start=1):
            if progress_callback:
                progress_callback(index, total_files, file_path.name)

            try:
                record = self.process_single_document(file_path)
                processed_records.append(record)
            except (DocumentIngestionError, ValueError) as err:
                LOGGER.error(f"Validation/Ingestion error on {file_path.name}: {err}")
            except Exception as unhandled:
                LOGGER.exception(f"Unhandled error processing {file_path.name}: {unhandled}")

        # 4. Generate Consolidated CSV[cite: 1]
        if processed_records:
            df = pd.DataFrame(processed_records)
            self.csv_output_path.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(self.csv_output_path, index=False, encoding="utf-8")
            LOGGER.info(f"Consolidated final report generated at: {self.csv_output_path}")
            return df

        return pd.DataFrame()

def run_batch_pipeline() -> pd.DataFrame:
    """Direct callable interface."""
    pipeline = BatchProcessingPipeline()
    return pipeline.run()