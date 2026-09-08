import streamlit as st
import pandas as pd
import math
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

# Tab Constants
TAB_ALL = "📊 Consolidated Report"
TAB_ESC = "🚨 Escalations Required"
TAB_ACT = "⏳ Open & Active Cases"
TAB_INS = "🔍 Document Inspector"
TAB_OPTIONS = [TAB_ALL, TAB_ESC, TAB_ACT, TAB_INS]

# Initialize Session State
if "active_tab" not in st.session_state:
    st.session_state.active_tab = TAB_ALL
if "selected_doc" not in st.session_state:
    st.session_state.selected_doc = None
if "search_query" not in st.session_state:
    st.session_state.search_query = ""
if "current_page" not in st.session_state:
    st.session_state.current_page = 1
if "page_size" not in st.session_state:
    st.session_state.page_size = 5

def open_inspector(filename):
    st.session_state.selected_doc = filename
    st.session_state.active_tab = TAB_INS

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

    existing_files = [f.name for f in data_dir.iterdir() if f.is_file()]
    st.markdown(f"**Files currently in `{data_dir.name}/`:** `{len(existing_files)}`")
    if existing_files:
        with st.expander("View file list"):
            for name in existing_files:
                st.text(f"• {name}")

    st.markdown("---")
    st.header("2. Run Pipeline")
    
    # Cache Control Checkbox
    force_reprocess = st.checkbox(
        "⚡ Force Re-process All",
        value=False,
        help="Bypasses SHA-256 cache and regenerates extractions, emails, and summaries for all files."
    )
    
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
    spinner_msg = (
        "Re-processing all files (bypassing cache)..."
        if force_reprocess
        else "Processing documents (cached files will be skipped)..."
    )

    with st.spinner(spinner_msg):
        df = pipeline.run(
            progress_callback=update_progress,
            force_reprocess=force_reprocess
        )

    status_text.success("Batch execution completed successfully!")
    progress_bar.empty()
    st.rerun()

# Helper function to render paginated table with View buttons
def render_paginated_table(df_subset, prefix_key):
    if df_subset.empty:
        st.info("No matching records found.")
        return

    # Pagination controls
    col_size, col_info, col_prev, col_page, col_next = st.columns([2, 3, 1, 1.5, 1])
    
    with col_size:
        page_size = st.selectbox(
            "Rows per page:", 
            [5, 10, 20], 
            index=0, 
            key=f"{prefix_key}_size_select"
        )
    
    total_records = len(df_subset)
    total_pages = max(1, math.ceil(total_records / page_size))
    
    # Ensure current page is valid for this subset
    page_key = f"{prefix_key}_page_num"
    if page_key not in st.session_state or st.session_state[page_key] > total_pages:
        st.session_state[page_key] = 1

    current_p = st.session_state[page_key]

    with col_prev:
        if st.button("◀ Prev", key=f"{prefix_key}_prev", disabled=(current_p <= 1)):
            st.session_state[page_key] -= 1
            st.rerun()

    with col_page:
        st.markdown(f"**Page {current_p} of {total_pages}**")

    with col_next:
        if st.button("Next ▶", key=f"{prefix_key}_next", disabled=(current_p >= total_pages)):
            st.session_state[page_key] += 1
            st.rerun()

    with col_info:
        start_idx = (current_p - 1) * page_size
        end_idx = min(start_idx + page_size, total_records)
        st.caption(f"Showing rows {start_idx + 1} to {end_idx} of {total_records}")

    # Slice DataFrame for current page
    page_df = df_subset.iloc[start_idx:end_idx]

    st.markdown("---")
    # Render table header
    h_btn, h_file, h_name, h_cat, h_status, h_esc = st.columns([1.2, 2.5, 2, 2, 1.5, 1.5])
    h_btn.markdown("**Action**")
    h_file.markdown("**File Name**")
    h_name.markdown("**Customer**")
    h_cat.markdown("**Category**")
    h_status.markdown("**Status**")
    h_esc.markdown("**Escalate?**")
    st.markdown("<hr style='margin:0.2rem 0'>", unsafe_allow_html=True)

    # Render rows
    for idx, row in page_df.iterrows():
        c_btn, c_file, c_name, c_cat, c_status, c_esc = st.columns([1.2, 2.5, 2, 2, 1.5, 1.5])
        with c_btn:
            st.button("👁️ View", key=f"{prefix_key}_view_{row['file_name']}_{idx}", on_click=open_inspector, args=(row['file_name'],))
        with c_file:
            st.write(f"`{row['file_name']}`")
        with c_name:
            st.write(str(row.get('customer_name', 'N/A')))
        with c_cat:
            st.write(str(row.get('complaint_category', 'N/A')))
        with c_status:
            st.write(str(row.get('case_status', 'N/A')))
        with c_esc:
            esc_flag = row.get('escalation_required', False)
            st.write("🚨 Yes" if esc_flag else "No")
        st.markdown("<hr style='margin:0.2rem 0; opacity:0.3'>", unsafe_allow_html=True)

# -------------------------------------------------------------
# 1. TOP METRIC KPI CARDS & SEARCH
# -------------------------------------------------------------
if csv_path.exists():
    df_report = pd.read_csv(csv_path)
    all_files = df_report["file_name"].tolist()

    if not st.session_state.selected_doc or st.session_state.selected_doc not in all_files:
        st.session_state.selected_doc = all_files[0] if all_files else None

    # Global Metrics
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

    # Debounced Search Input Bar
    c_search, c_clear = st.columns([5, 1])
    with c_search:
        raw_query = st.text_input(
            "🔎 Search cases (Customer, File, Category, or Description):",
            value=st.session_state.search_query,
            placeholder="Type search terms and press Enter...",
            key="search_input_widget"
        )
        if raw_query != st.session_state.search_query:
            st.session_state.search_query = raw_query
            st.rerun()

    with c_clear:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        if st.button("Clear Search", use_container_width=True):
            st.session_state.search_query = ""
            st.rerun()

    # Filter DataFrame based on debounced search query
    filtered_df = df_report.copy()
    if st.session_state.search_query.strip():
        q = st.session_state.search_query.strip().lower()
        search_cols = ["file_name", "customer_name", "complaint_category", "issue_description"]
        mask = False
        for col in search_cols:
            if col in filtered_df.columns:
                mask = mask | filtered_df[col].astype(str).str.lower().str.contains(q, na=False)
        filtered_df = filtered_df[mask]
        st.caption(f"Found **{len(filtered_df)}** result(s) for query: `\"{st.session_state.search_query}\"`")

    # -------------------------------------------------------------
    # 2. PROGRAMMATIC TAB NAVIGATION BAR
    # -------------------------------------------------------------
    active_tab = st.radio(
        "Navigation",
        options=TAB_OPTIONS,
        index=TAB_OPTIONS.index(st.session_state.active_tab),
        horizontal=True,
        label_visibility="collapsed",
        key="active_tab"
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # VIEW 1: All Documents (Paginated)
    if active_tab == TAB_ALL:
        st.subheader("All Processed Documents")
        st.download_button(
            label="📥 Download final_report.csv",
            data=filtered_df.to_csv(index=False).encode("utf-8"),
            file_name="final_report.csv",
            mime="text/csv"
        )
        render_paginated_table(filtered_df, prefix_key="all_cases")

    # VIEW 2: Priority Escalation Queue (Paginated)
    elif active_tab == TAB_ESC:
        st.subheader("🚨 Priority Escalation Queue")
        st.caption("Cases requiring managerial review, legal attention, or high-tier intervention.")
        df_escalated = filtered_df[filtered_df["escalation_required"] == True]
        render_paginated_table(df_escalated, prefix_key="esc_cases")

    # VIEW 3: Active / Pending Queue (Paginated)
    elif active_tab == TAB_ACT:
        st.subheader("⏳ Active Work Queue")
        st.caption("Cases marked 'Open' or 'In Progress' where resolutions are still pending.")
        df_active = filtered_df[filtered_df["case_status"].isin(["Open", "In Progress"])]
        render_paginated_table(df_active, prefix_key="act_cases")

    # VIEW 4: Document Inspector
    elif active_tab == TAB_INS:
        st.subheader("🔍 Document Inspector")
        
        selected_index = all_files.index(st.session_state.selected_doc) if st.session_state.selected_doc in all_files else 0
        
        selected_file = st.selectbox(
            "Select document to inspect:", 
            all_files, 
            index=selected_index,
            key="doc_selector"
        )
        st.session_state.selected_doc = selected_file
        
        if selected_file:
            stem = get_base_filename(selected_file)
            col_json, col_text = st.columns([1, 1])

            # Left Column: Extracted Structured JSON
            with col_json:
                st.subheader("Extracted Structured Data (JSON)")
                json_file = structured_dir / f"{stem}.json"
                if json_file.exists():
                    with open(json_file, "r", encoding="utf-8") as f:
                        json_content = f.read()
                    
                    st.download_button(
                        label="📥 Download JSON",
                        data=json_content,
                        file_name=f"{stem}.json",
                        mime="application/json",
                        key=f"dl_json_{stem}"
                    )
                    st.code(json_content, language="json")
                else:
                    st.warning("JSON file missing.")

            # Right Column: Generated Email & Case Summary
            with col_text:
                # 1. Customer Email
                st.subheader("Generated Customer Response Email")
                email_file = emails_dir / f"{stem}_email.txt"
                if email_file.exists():
                    with open(email_file, "r", encoding="utf-8") as f:
                        email_content = f.read()

                    col_email_dl, col_email_pop = st.columns([1, 1])
                    with col_email_dl:
                        st.download_button(
                            label="📥 Download Email (.txt)",
                            data=email_content,
                            file_name=f"{stem}_email.txt",
                            mime="text/plain",
                            key=f"dl_email_{stem}"
                        )
                    with col_email_pop:
                        with st.popover("🔍 Open in Pop-up"):
                            st.markdown("### Customer Response Email Draft")
                            st.text_area("Email Content", value=email_content, height=300, disabled=True)

                    st.info(email_content)
                else:
                    st.warning("Email file missing.")

                st.markdown("---")

                # 2. Case Summary
                st.subheader("Internal Management Case Summary")
                summary_file = summaries_dir / f"{stem}_summary.txt"
                if summary_file.exists():
                    with open(summary_file, "r", encoding="utf-8") as f:
                        summary_content = f.read()

                    col_sum_dl, col_sum_pop = st.columns([1, 1])
                    with col_sum_dl:
                        st.download_button(
                            label="📥 Download Summary (.txt)",
                            data=summary_content,
                            file_name=f"{stem}_summary.txt",
                            mime="text/plain",
                            key=f"dl_sum_{stem}"
                        )
                    with col_sum_pop:
                        with st.popover("🔍 Open in Pop-up"):
                            st.markdown(summary_content)

                    st.markdown(summary_content)
                else:
                    st.warning("Summary file missing.")
else:
    st.info("No report found. Upload files and click 'Execute Batch Workflow' from the sidebar to view data.")