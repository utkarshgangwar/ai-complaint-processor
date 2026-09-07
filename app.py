import streamlit as st
import pandas as pd
from pathlib import Path
from src.config import CONFIG, BASE_DIR
from src.pipeline import BatchProcessingPipeline
from src.utils import get_base_filename

# Streamlit Page Setup
st.set_page_config(
    page_title="AI Case & Document Processing Platform",
    page_icon="📄",
    layout="wide"
)

st.title("📄 AI Customer Case Processing System")
st.caption("Batch Document Processing, Structured Information Extraction & Management Workflow")

# Initialize Paths
data_dir = BASE_DIR / CONFIG.get("paths", {}).get("data_dir", "data")
output_dir = BASE_DIR / CONFIG.get("paths", {}).get("output_base_dir", "output")
csv_path = BASE_DIR / CONFIG.get("paths", {}).get("final_report_csv", "output/final_report.csv")
structured_dir = BASE_DIR / CONFIG.get("paths", {}).get("structured_data_dir", "output/structured_data")
emails_dir = BASE_DIR / CONFIG.get("paths", {}).get("customer_emails_dir", "output/customer_emails")
summaries_dir = BASE_DIR / CONFIG.get("paths", {}).get("case_summaries_dir", "output/case_summaries")

# Sidebar - Ingestion & Trigger Controls
with st.sidebar:
    st.header("1. Ingestion Controls")
    uploaded_files = st.file_uploader(
        "Upload Documents (.pdf, .docx, .txt)",
        type=["pdf", "docx", "txt"],
        accept_multiple_files=True
    )

    if uploaded_files:
        for file in uploaded_files:
            target_path = data_dir / file.name
            with open(target_path, "wb") as f:
                f.write(file.getbuffer())
        st.success(f"Saved {len(uploaded_files)} file(s) to {data_dir.name}/")

    # Display current files
    existing_files = [f.name for f in data_dir.iterdir() if f.is_file()]
    st.markdown(f"**Files currently in `{data_dir.name}/`:** `{len(existing_files)}`")
    if existing_files:
        with st.expander("View file list"):
            for name in existing_files:
                st.text(f"• {name}")

    st.markdown("---")
    st.header("2. Run Pipeline")
    run_btn = st.button("Execute Batch Workflow", type="primary", use_container_width=True)

# Main Application Body - Run Pipeline Trigger
if run_btn:
    progress_bar = st.progress(0)
    status_text = st.empty()

    def update_progress(current, total, filename):
        fraction = current / total
        progress_bar.progress(fraction)
        status_text.info(f"Processing ({current}/{total}): **{filename}**")

    pipeline = BatchProcessingPipeline()
    with st.spinner("Executing document parsing, LLM extraction & summary chains..."):
        df = pipeline.run(progress_callback=update_progress)

    status_text.success("Batch execution completed successfully!")
    progress_bar.empty()

# -------------------------------------------------------------
# 1. TOP METRIC KPI CARDS (Always visible above tabs)
# -------------------------------------------------------------
if csv_path.exists():
    df_report = pd.read_csv(csv_path)

    total_cases = len(df_report)
    escalations_needed = int(df_report["escalation_required"].sum()) if "escalation_required" in df_report else 0
    active_pending = int(df_report["case_status"].isin(["Open", "In Progress"]).sum()) if "case_status" in df_report else 0
    avg_latency = round(df_report["latency_seconds"].mean(), 2) if "latency_seconds" in df_report else 0.0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Cases", total_cases)
    col2.metric("Escalations Needed", escalations_needed)
    col3.metric("Active / Pending", active_pending)
    col4.metric("Avg Latency (s)", f"{avg_latency}s")

    st.markdown("---")

    # -------------------------------------------------------------
    # 2. CATEGORIZED TABS
    # -------------------------------------------------------------
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Consolidated Report", 
        "🚨 Escalations Required", 
        "⏳ Open & Active Cases", 
        "🔍 Document Inspector"
    ])

    # Tab 1: All Documents
    with tab1:
        st.subheader("All Processed Documents")
        st.dataframe(df_report, use_container_width=True)
        st.download_button(
            label="📥 Download final_report.csv",
            data=df_report.to_csv(index=False).encode("utf-8"),
            file_name="final_report.csv",
            mime="text/csv"
        )

    # Tab 2: Escalations Only
    with tab2:
        st.subheader("🚨 Priority Escalation Queue")
        st.caption("Cases requiring managerial review, legal attention, or high-tier intervention.")
        df_escalated = df_report[df_report["escalation_required"] == True]
        if not df_escalated.empty:
            st.dataframe(
                df_escalated[["file_name", "customer_name", "complaint_category", "issue_description", "case_status"]], 
                use_container_width=True
            )
        else:
            st.success("No escalations detected in the current batch.")

    # Tab 3: Open & Active Cases
    with tab3:
        st.subheader("⏳ Active Work Queue")
        st.caption("Cases marked 'Open' or 'In Progress' where resolutions are still pending.")
        df_active = df_report[df_report["case_status"].isin(["Open", "In Progress"])]
        if not df_active.empty:
            st.dataframe(
                df_active[["file_name", "customer_name", "complaint_category", "case_status", "resolution_provided"]], 
                use_container_width=True
            )
        else:
            st.success("All cases are resolved or closed.")

    # Tab 4: Document Inspector
    with tab4:
        doc_names = df_report["file_name"].tolist()
        selected_file = st.selectbox("Select document to inspect:", doc_names)
        
        if selected_file:
            stem = get_base_filename(selected_file)
            col_json, col_text = st.columns([1, 1])

            with col_json:
                st.subheader("Extracted Structured Data (JSON)")
                json_file = structured_dir / f"{stem}.json"
                if json_file.exists():
                    with open(json_file, "r", encoding="utf-8") as f:
                        st.code(f.read(), language="json")
                else:
                    st.warning("JSON file missing.")

            with col_text:
                st.subheader("Generated Customer Response Email")
                email_file = emails_dir / f"{stem}_email.txt"
                if email_file.exists():
                    with open(email_file, "r", encoding="utf-8") as f:
                        st.info(f.read())
                else:
                    st.warning("Email file missing.")

                st.subheader("Internal Management Case Summary")
                summary_file = summaries_dir / f"{stem}_summary.txt"
                if summary_file.exists():
                    with open(summary_file, "r", encoding="utf-8") as f:
                        st.markdown(f.read())
                else:
                    st.warning("Summary file missing.")
else:
    st.info("No report found. Upload files and click 'Execute Batch Workflow' from the sidebar to view data.")