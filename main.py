import sys
from src.config import LOGGER
from src.pipeline import run_batch_pipeline

def main():
    LOGGER.info("Starting headless CLI batch processing execution...")
    try:
        results_df = run_batch_pipeline()
        if results_df.empty:
            print("\n[!] No files processed. Place files inside the 'data/' folder and rerun.")
            sys.exit(0)

        print("\n================ BATCH PROCESSING COMPLETE ================")
        print(f"Total Documents Processed: {len(results_df)}")
        print("Columns Generated:")
        for col in results_df.columns:
            print(f" - {col}")
        print("\nOutputs saved in the 'output/' directory.")
        print("Consolidated CSV report available at 'output/final_report.csv'.")
        print("===========================================================\n")
    except Exception as e:
        LOGGER.exception(f"Fatal error during CLI batch run: {e}")
        print(f"\n[ERROR] Pipeline failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()