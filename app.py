import os
import json
import math
from pathlib import Path
import pandas as pd
import streamlit as st

from src.config import BASE_DIR, CONFIG
from src.pipeline import BatchProcessingPipeline
from src.utils import compute_file_hash, get_base_filename

st.set_page_config(
    page_title="Enterprise AI Case Intelligence",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------------------------------------------------
# SESSION STATE INITIALIZATION
# -------------------------------------------------------------
if "app_theme" not in st.session_state:
    st.session_state.app_theme = "Light"

PAGE_MAIN = "📊 Main Dashboard"
PAGE_REPO = "📁 Manage & Ingest Files"
PAGE_ABOUT = "ℹ️ About Platform"
PAGE_OPTIONS = [PAGE_MAIN, PAGE_REPO, PAGE_ABOUT]

if "active_page" not in st.session_state:
    st.session_state.active_page = PAGE_MAIN

# -------------------------------------------------------------
# DYNAMIC THEME COLOR TOKENS
# -------------------------------------------------------------
if st.session_state.app_theme == "Light":
    t_bg = "#f8fafc"
    t_surface = "#ffffff"
    t_surface_alt = "#f1f5f9"
    t_border = "#e2e8f0"
    t_text = "#0f172a"
    t_subtext = "#64748b"
    t_divider = "#f1f5f9"
    t_metric_bg = "#ffffff"
    t_badge_proc = ("#dcfce7", "#15803d", "#bbf7d0")
    t_badge_unpr = ("#f1f5f9", "#475569", "#e2e8f0")
    t_badge_err = ("#fee2e2", "#b91c1c", "#fecaca")
else:
    t_bg = "#090d16"
    t_surface = "#111827"
    t_surface_alt = "#1f2937"
    t_border = "rgba(255, 255, 255, 0.1)"
    t_text = "#f9fafb"
    t_subtext = "#9ca3af"
    t_divider = "rgba(255, 255, 255, 0.07)"
    t_metric_bg = "rgba(255, 255, 255, 0.03)"
    t_badge_proc = ("rgba(34, 197, 94, 0.15)", "#22c55e", "rgba(34, 197, 94, 0.3)")
    t_badge_unpr = ("rgba(156, 163, 175, 0.15)", "#9ca3af", "rgba(156, 163, 175, 0.3)")
    t_badge_err = ("rgba(239, 68, 68, 0.15)", "#ef4444", "rgba(239, 68, 68, 0.3)")

# -------------------------------------------------------------
# CLEAN CSS (MODERN THEME, COMPACT INTERFACE)
# -------------------------------------------------------------
st.markdown(
    f"""
    <style>
    /* Hide default Streamlit chrome */
    #MainMenu, footer, .stDeployButton, 
    div[data-testid="stToolbarActions"], 
    div[data-testid="stAppDeployButton"] {{
        visibility: hidden !important;
        display: none !important;
    }}

    header[data-testid="stHeader"] {{
        background: transparent !important;
        z-index: 1000 !important;
    }}

    .stApp {{
        background-color: {t_bg} !important;
        color: {t_text} !important;
    }}
    .block-container {{
        padding-top: 1.2rem !important;
        padding-bottom: 2.5rem !important;
        max-width: 98% !important;
    }}

    section[data-testid="stSidebar"] {{
        background-color: {t_surface} !important;
        border-right: 1px solid {t_border} !important;
        width: 320px !important;
    }}

    div[data-testid="stMetric"] {{
        background: {t_metric_bg} !important;
        border: 1px solid {t_border} !important;
        border-radius: 8px !important;
        padding: 8px 12px !important;
    }}
    div[data-testid="stMetric"] label {{
        color: {t_subtext} !important;
        font-weight: 600 !important;
        font-size: 0.76rem !important;
        margin-bottom: 0px !important;
    }}
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {{
        color: {t_text} !important;
        font-size: 1.35rem !important;
        font-weight: 700 !important;
    }}

    .status-pill {{
        font-size: 0.7rem;
        padding: 2px 7px;
        border-radius: 9999px;
        font-weight: 600;
        display: inline-block;
        letter-spacing: 0.2px;
    }}
    .status-processed {{
        background-color: {t_badge_proc[0]};
        color: {t_badge_proc[1]};
        border: 1px solid {t_badge_proc[2]};
    }}
    .status-unprocessed {{
        background-color: {t_badge_unpr[0]};
        color: {t_badge_unpr[1]};
        border: 1px solid {t_badge_unpr[2]};
    }}
    .status-errored {{
        background-color: {t_badge_err[0]};
        color: {t_badge_err[1]};
        border: 1px solid {t_badge_err[2]};
    }}

    .table-row-divider {{
        margin: 2px 0 !important;
        border: none !important;
        border-top: 1px solid {t_divider} !important;
    }}

    .app-footer {{
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        height: 28px;
        background-color: {t_surface};
        border-top: 1px solid {t_border};
        color: {t_subtext};
        text-align: right;
        padding: 4px 20px;
        font-size: 0.68rem;
        z-index: 99999;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }}
    </style>
    """,
    unsafe_allow_html=True
)

# -------------------------------------------------------------
# AUTHENTICATION GATEWAY
# -------------------------------------------------------------
AUTH_USER = os.getenv("APP_USER", "admin")
AUTH_PASS = os.getenv("APP_PASSWORD", "secretpassword123")

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

def login_form():
    col1, col2, col3 = st.columns([1, 1.1, 1])
    with col2:
        st.markdown("<div style='height: 100px;'></div>", unsafe_allow_html=True)
        st.markdown(
            f"""
            <div style="background:{t_surface}; border:1px solid {t_border}; border-radius:8px; padding:20px 24px;">
                <h4 style="margin-bottom:2px; color:{t_text};">🔐 Enterprise Case Portal</h4>
                <p style="color:{t_subtext}; font-size:0.8rem; margin-bottom:12px;">Sign in with administrative credentials.</p>
            </div>
            """,
            unsafe_allow_html=True
        )
        with st.form("login_credentials_form"):
            username_input = st.text_input("User ID", placeholder="e.g. admin")
            password_input = st.text_input("Password", type="password", placeholder="••••••••")
            submit_login = st.form_submit_button("Sign In", use_container_width=True, type="primary")

            if submit_login:
                if username_input == AUTH_USER and password_input == AUTH_PASS:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Authentication failed: Invalid credentials.")
    st.markdown('<div class="app-footer">AI Case Processing Engine &nbsp;|&nbsp; Release: <b>v1.0.0</b></div>', unsafe_allow_html=True)

if not st.session_state.authenticated:
    login_form()
    st.stop()

# -------------------------------------------------------------
# PATH INITIALIZATION & RUNTIME STORAGE
# -------------------------------------------------------------
data_dir = BASE_DIR / CONFIG.get("paths", {}).get("data_dir", "data")
output_dir = BASE_DIR / CONFIG.get("paths", {}).get("output_base_dir", "output")
csv_path = BASE_DIR / CONFIG.get("paths", {}).get("final_report_csv", "output/final_report.csv")
structured_dir = BASE_DIR / CONFIG.get("paths", {}).get("structured_data_dir", "output/structured_data")
emails_dir = BASE_DIR / CONFIG.get("paths", {}).get("customer_emails_dir", "output/customer_emails")
summaries_dir = BASE_DIR / CONFIG.get("paths", {}).get("case_summaries_dir", "output/case_summaries")
manifest_path = csv_path.parent / ".processed_manifest.json"
errors_path = csv_path.parent / ".processing_errors.json"

TAB_ALL = "📊 All Cases"
TAB_ESC = "🚨 Escalated"
TAB_ACT = "⏳ Active"
TAB_ERR = "⚠️ Errored"
TAB_INS = "🔍 Inspector"
TAB_OPTIONS = [TAB_ALL, TAB_ESC, TAB_ACT, TAB_ERR, TAB_INS]

if "active_tab" not in st.session_state:
    st.session_state.active_tab = TAB_ALL
if "selected_doc" not in st.session_state:
    st.session_state.selected_doc = None
if "search_query" not in st.session_state:
    st.session_state.search_query = ""

def load_error_log() -> dict:
    if errors_path.exists():
        try:
            with open(errors_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def open_inspector(filename):
    st.session_state.selected_doc = filename
    st.session_state.active_tab = TAB_INS
    st.session_state.active_page = PAGE_MAIN
    st.rerun()

def delete_file_and_artifacts(filename):
    target_path = data_dir / filename
    if target_path.exists():
        target_path.unlink()

    stem = get_base_filename(filename)
    for art in [
        structured_dir / f"{stem}.json",
        emails_dir / f"{stem}_email.txt",
        summaries_dir / f"{stem}_summary.txt"
    ]:
        if art.exists():
            art.unlink()

    if manifest_path.exists():
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            if filename in manifest:
                del manifest[filename]
                with open(manifest_path, "w", encoding="utf-8") as f:
                    json.dump(manifest, f, indent=2)
        except Exception:
            pass

    if errors_path.exists():
        try:
            with open(errors_path, "r", encoding="utf-8") as f:
                err_data = json.load(f)
            if filename in err_data:
                del err_data[filename]
                with open(errors_path, "w", encoding="utf-8") as f:
                    json.dump(err_data, f, indent=2)
        except Exception:
            pass

    if csv_path.exists():
        try:
            df = pd.read_csv(csv_path)
            if "file_name" in df.columns:
                df = df[df["file_name"] != filename]
                df.to_csv(csv_path, index=False)
        except Exception:
            pass

    if st.session_state.selected_doc == filename:
        st.session_state.selected_doc = None
    st.rerun()

def get_file_status(filename, errors_dict):
    if filename in errors_dict:
        return "errored", "status-errored", "Errored"

    stem = get_base_filename(filename)
    json_file = structured_dir / f"{stem}.json"
    email_file = emails_dir / f"{stem}_email.txt"
    summary_file = summaries_dir / f"{stem}_summary.txt"

    if json_file.exists() and email_file.exists() and summary_file.exists():
        return "processed", "status-processed", "Processed"
    return "unprocessed", "status-unprocessed", "Unprocessed"

error_log = load_error_log()

# -------------------------------------------------------------
# SIDEBAR NAVIGATION
# -------------------------------------------------------------
with st.sidebar:
    st.markdown(
        f"""
        <div style="margin-bottom: 12px;">
            <div style="font-size: 1.15rem; font-weight: 800; color: {t_text};">⚡ AI Case Engine</div>
            <div style="font-size: 0.72rem; color: {t_subtext};">Release v1.0.0 &bull; Operator: <b>{AUTH_USER}</b></div>
        </div>
        """,
        unsafe_allow_html=True
    )

    selected_page = st.radio(
        "Navigation",
        options=PAGE_OPTIONS,
        index=PAGE_OPTIONS.index(st.session_state.active_page),
        key="sidebar_page_selector"
    )
    if selected_page != st.session_state.active_page:
        st.session_state.active_page = selected_page
        st.rerun()

    st.markdown("---")
    
    col_th, col_lg = st.columns([1, 1])
    with col_th:
        is_dark = (st.session_state.app_theme == "Dark")
        theme_toggle = st.toggle("🌙 Dark", value=is_dark, key="theme_toggle_btn")
        new_theme = "Dark" if theme_toggle else "Light"
        if new_theme != st.session_state.app_theme:
            st.session_state.app_theme = new_theme
            st.rerun()
    with col_lg:
        if st.button("Log Out", key="sidebar_logout_btn", use_container_width=True):
            st.session_state.authenticated = False
            st.rerun()

# -------------------------------------------------------------
# INTERACTIVE DATAFRAME COMPONENT (PRIORITY TAGS INSTEAD OF CHECKBOXES)
# -------------------------------------------------------------
def render_interactive_table(df_subset, table_key):
    if df_subset.empty:
        st.info("No matching records found in this view.")
        return

    cols_to_display = [
        "file_name", "customer_name", "complaint_category", 
        "case_status", "escalation_required", "latency_seconds"
    ]
    available_cols = [c for c in cols_to_display if c in df_subset.columns]
    display_df = df_subset[available_cols].copy()

    # Map boolean values to visual priority badges
    if "escalation_required" in display_df.columns:
        display_df["escalation_required"] = display_df["escalation_required"].map(
            lambda x: "🚨 Escalated" if bool(x) else "🟢 Standard"
        )

    col_config = {
        "file_name": st.column_config.TextColumn("File Name", help="Document name in storage", width="medium"),
        "customer_name": st.column_config.TextColumn("Customer", width="medium"),
        "complaint_category": st.column_config.TextColumn("Category", width="medium"),
        "case_status": st.column_config.TextColumn("Status", width="small"),
        "escalation_required": st.column_config.TextColumn("Priority / Escalation", help="High-priority manager review status", width="small"),
        "latency_seconds": st.column_config.NumberColumn("Latency", format="%.2fs", width="small"),
    }

    st.dataframe(
        display_df,
        column_config=col_config,
        use_container_width=True,
        hide_index=True,
        height=320,
        key=f"df_view_{table_key}"
    )

# =============================================================
# PAGE 1: MAIN DASHBOARD
# =============================================================
if st.session_state.active_page == PAGE_MAIN:
    st.markdown("### 📊 Customer Case Processing Dashboard")

    has_report = csv_path.exists()
    has_errors = bool(error_log)

    if has_report or has_errors:
        df_report = pd.read_csv(csv_path) if has_report else pd.DataFrame()
        all_files = df_report["file_name"].tolist() if not df_report.empty and "file_name" in df_report else []

        if all_files and (not st.session_state.selected_doc or st.session_state.selected_doc not in all_files):
            st.session_state.selected_doc = all_files[0]

        total_cases = len(df_report)
        escalations_needed = int(df_report["escalation_required"].sum()) if not df_report.empty and "escalation_required" in df_report else 0
        active_pending = int(df_report["case_status"].isin(["Open", "In Progress"]).sum()) if not df_report.empty and "case_status" in df_report else 0
        num_errored = len(error_log)

        # KPI Metrics
        kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)
        kpi_col1.metric("Processed Cases", total_cases)
        kpi_col2.metric("Escalations Needed", escalations_needed)
        kpi_col3.metric("Active / Pending", active_pending)
        kpi_col4.metric("Failed / Errored", num_errored, delta=f"{num_errored} Errors" if num_errored > 0 else None, delta_color="inverse")

        st.markdown("<div style='height: 6px;'></div>", unsafe_allow_html=True)

        # Search Bar & Tabs
        c_search, c_tabs = st.columns([3.5, 6.5])
        with c_search:
            raw_query = st.text_input(
                "Filter records",
                value=st.session_state.search_query,
                placeholder="Search customer, file, issue...",
                label_visibility="collapsed",
                key="main_search_input"
            )
            if raw_query != st.session_state.search_query:
                st.session_state.search_query = raw_query
                st.rerun()

        with c_tabs:
            active_tab = st.radio(
                "Viewports",
                options=TAB_OPTIONS,
                index=TAB_OPTIONS.index(st.session_state.active_tab),
                horizontal=True,
                label_visibility="collapsed",
                key="active_tab"
            )

        filtered_df = df_report.copy()
        if not filtered_df.empty and st.session_state.search_query.strip():
            q = st.session_state.search_query.strip().lower()
            search_cols = ["file_name", "customer_name", "complaint_category", "issue_description"]
            mask = False
            for col in search_cols:
                if col in filtered_df.columns:
                    mask = mask | filtered_df[col].astype(str).str.lower().str.contains(q, na=False)
            filtered_df = filtered_df[mask]

        # Tab Views
        if active_tab == TAB_ALL:
            col_hdr, col_dl = st.columns([8.8, 1.2])
            with col_hdr:
                st.caption(f"Showing all processed cases ({len(filtered_df)} total)")
            with col_dl:
                if not filtered_df.empty:
                    st.download_button(
                        label="📥 Export CSV",
                        data=filtered_df.to_csv(index=False).encode("utf-8"),
                        file_name="final_report.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
            render_interactive_table(filtered_df, table_key="all_cases")

        elif active_tab == TAB_ESC:
            st.caption("🚨 Priority Escalation Queue (Managerial & Legal Attention)")
            df_escalated = filtered_df[filtered_df["escalation_required"] == True] if not filtered_df.empty and "escalation_required" in filtered_df else pd.DataFrame()
            render_interactive_table(df_escalated, table_key="esc_cases")

        elif active_tab == TAB_ACT:
            st.caption("⏳ Active Work Queue (Open & In Progress)")
            df_active = filtered_df[filtered_df["case_status"].isin(["Open", "In Progress"])] if not filtered_df.empty and "case_status" in filtered_df else pd.DataFrame()
            render_interactive_table(df_active, table_key="act_cases")

        elif active_tab == TAB_ERR:
            st.caption("⚠️ Document Processing Exceptions & Parser Errors")
            if not error_log:
                st.success("Zero exceptions registered. All ingested documents processed cleanly.")
            else:
                col_clear_err, _ = st.columns([2, 8])
                with col_clear_err:
                    if st.button("Clear Log", use_container_width=True):
                        if errors_path.exists():
                            errors_path.unlink()
                        st.rerun()

                err_df = pd.DataFrame([
                    {"File Name": k, "Exception Reason": v} for k, v in error_log.items()
                ])
                st.dataframe(
                    err_df,
                    column_config={
                        "File Name": st.column_config.TextColumn("File Name", width="medium"),
                        "Exception Reason": st.column_config.TextColumn("Exception Trace", width="large"),
                    },
                    use_container_width=True,
                    hide_index=True,
                    height=280
                )

        elif active_tab == TAB_INS:
            if not all_files:
                st.info("No processed artifacts available for inspection.")
            else:
                col_sel, _ = st.columns([4, 6])
                with col_sel:
                    selected_index = all_files.index(st.session_state.selected_doc) if st.session_state.selected_doc in all_files else 0
                    selected_file = st.selectbox("Inspect Document:", all_files, index=selected_index, label_visibility="collapsed", key="doc_selector")
                    st.session_state.selected_doc = selected_file

                if selected_file:
                    stem = get_base_filename(selected_file)
                    with st.container(height=380):
                        col_json, col_text = st.columns([1, 1])
                        with col_json:
                            st.markdown(f"<span style='font-size:0.8rem; font-weight:700; color:{t_subtext};'>EXTRACTED JSON DATA</span>", unsafe_allow_html=True)
                            json_file = structured_dir / f"{stem}.json"
                            if json_file.exists():
                                with open(json_file, "r", encoding="utf-8") as f:
                                    json_content = f.read()
                                st.download_button(label="📥 JSON", data=json_content, file_name=f"{stem}.json", mime="application/json", key=f"dl_json_{stem}")
                                st.code(json_content, language="json")
                            else:
                                st.warning("Missing JSON artifact.")

                        with col_text:
                            st.markdown(f"<span style='font-size:0.8rem; font-weight:700; color:{t_subtext};'>CUSTOMER RESPONSE EMAIL</span>", unsafe_allow_html=True)
                            email_file = emails_dir / f"{stem}_email.txt"
                            if email_file.exists():
                                with open(email_file, "r", encoding="utf-8") as f:
                                    email_content = f.read()
                                col_dl, col_pop = st.columns([1, 1])
                                with col_dl:
                                    st.download_button(label="📥 Email (.txt)", data=email_content, file_name=f"{stem}_email.txt", mime="text/plain", key=f"dl_email_{stem}")
                                with col_pop:
                                    with st.popover("🔍 Modal"):
                                        st.markdown("### Customer Email Draft")
                                        st.text_area("Email Content", value=email_content, height=220, disabled=True)
                                st.info(email_content)
                            else:
                                st.warning("Missing email artifact.")

                            st.markdown("<hr style='margin: 4px 0;'>", unsafe_allow_html=True)
                            st.markdown(f"<span style='font-size:0.8rem; font-weight:700; color:{t_subtext};'>MANAGEMENT BRIEFING MEMO</span>", unsafe_allow_html=True)
                            summary_file = summaries_dir / f"{stem}_summary.txt"
                            if summary_file.exists():
                                with open(summary_file, "r", encoding="utf-8") as f:
                                    summary_content = f.read()
                                col_s_dl, col_s_pop = st.columns([1, 1])
                                with col_s_dl:
                                    st.download_button(label="📥 Memo (.txt)", data=summary_content, file_name=f"{stem}_summary.txt", mime="text/plain", key=f"dl_sum_{stem}")
                                with col_s_pop:
                                    with st.popover("🔍 Modal"):
                                        st.markdown(summary_content)
                                st.markdown(summary_content)
                            else:
                                st.warning("Missing summary artifact.")
    else:
        st.info("No report found yet. Select '📁 Manage & Ingest Files' in the sidebar to upload files and run the workflow.")

# =============================================================
# PAGE 2: MANAGE & INGEST FILES + EXECUTE PIPELINE
# =============================================================
elif st.session_state.active_page == PAGE_REPO:
    st.markdown("### 📁 Document Ingestion & Storage Manager")
    st.caption("Upload documents, manage stored files, and execute the batch workflow.")

    col_upload_hub, col_pipeline_run = st.columns([6, 4])

    with col_upload_hub:
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
            st.success(f"Saved {len(uploaded_files)} file(s) to `{data_dir.name}/`")

    with col_pipeline_run:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        force_reprocess = st.checkbox(
            "Force Re-process All Files",
            value=False,
            help="Bypasses hash caching and runs extractions from scratch."
        )
        run_pipeline_btn = st.button("⚡ Run Batch Processing Pipeline", type="primary", use_container_width=True)

    if run_pipeline_btn:
        progress_bar = st.progress(0)
        status_text = st.empty()

        def update_progress(current, total, filename):
            fraction = current / total
            progress_bar.progress(fraction)
            status_text.info(f"Processing ({current}/{total}): **{filename}**")

        pipeline = BatchProcessingPipeline()
        spinner_msg = "Re-processing all files..." if force_reprocess else "Running batch pipeline..."

        with st.spinner(spinner_msg):
            df = pipeline.run(
                progress_callback=update_progress,
                force_reprocess=force_reprocess
            )

        status_text.success("Pipeline executed successfully! Switch to 'Main Dashboard' to inspect results.")
        progress_bar.empty()
        st.rerun()

    st.markdown("<hr style='margin:10px 0; border:none; border-top:1px solid " + t_border + ";'>", unsafe_allow_html=True)

    existing_files = sorted([f.name for f in data_dir.iterdir() if f.is_file()])

    col_rep_head, col_rep_search = st.columns([5, 5])
    with col_rep_head:
        st.markdown(f"<span style='font-size:0.9rem; font-weight:700;'>Stored Documents ({len(existing_files)})</span>", unsafe_allow_html=True)
    with col_rep_search:
        repo_search = st.text_input(
            "Filter files",
            placeholder="Search repository files...",
            label_visibility="collapsed",
            key="repo_page_file_filter"
        ).strip().lower()

    filtered_repo_files = (
        [f for f in existing_files if repo_search in f.lower()]
        if repo_search
        else existing_files
    )

    if not filtered_repo_files:
        st.info("No documents found matching query.")
    else:
        h_ficon, h_fname, h_fstatus, h_factions = st.columns([0.4, 4.6, 2, 3])
        h_fname.markdown(f"<span style='font-size:0.72rem; font-weight:700; color:{t_subtext};'>FILE NAME</span>", unsafe_allow_html=True)
        h_fstatus.markdown(f"<span style='font-size:0.72rem; font-weight:700; color:{t_subtext};'>STATUS</span>", unsafe_allow_html=True)
        h_factions.markdown(f"<span style='font-size:0.72rem; font-weight:700; color:{t_subtext};'>ACTIONS</span>", unsafe_allow_html=True)
        st.markdown(f"<hr style='margin:1px 0 4px 0; border:none; border-top:1px solid {t_border};'>", unsafe_allow_html=True)

        with st.container(height=340):
            for name in filtered_repo_files:
                _, badge_class, label = get_file_status(name, error_log)
                c_icon, c_name, c_status, c_actions = st.columns([0.4, 4.6, 2, 3])

                with c_icon:
                    st.markdown("<span style='font-size:0.8rem;'>📄</span>", unsafe_allow_html=True)
                with c_name:
                    st.markdown(f"<span class='table-cell-text' style='font-weight:600; color:{t_text}; font-family:monospace;'>{name}</span>", unsafe_allow_html=True)
                with c_status:
                    st.markdown(f"<span class='status-pill {badge_class}'>{label}</span>", unsafe_allow_html=True)
                with c_actions:
                    col_act_rep, col_act_del = st.columns([1, 1])
                    with col_act_rep:
                        with st.popover("Replace", use_container_width=True):
                            st.caption(f"Replace **{name}**")
                            rep_file = st.file_uploader("Select file", type=["pdf", "docx", "txt"], key=f"repo_page_rep_{name}", label_visibility="collapsed")
                            if rep_file is not None:
                                target_path = data_dir / name
                                with open(target_path, "wb") as f:
                                    f.write(rep_file.getbuffer())
                                delete_file_and_artifacts(name)
                                st.toast(f"Replaced {name}")
                                st.rerun()
                    with col_act_del:
                        if st.button("Delete", key=f"repo_page_del_{name}", use_container_width=True):
                            delete_file_and_artifacts(name)
                st.markdown("<hr class='table-row-divider'>", unsafe_allow_html=True)

# =============================================================
# PAGE 3: ABOUT PAGE
# =============================================================
elif st.session_state.active_page == PAGE_ABOUT:
    st.markdown("### ℹ️ About Enterprise AI Case Processing Platform")
    st.caption("Architecture overview, data pipelines, caching mechanics, and system specifications.")

    col_ab_left, col_ab_right = st.columns([6, 4])

    with col_ab_left:
        st.markdown(
            f"""
            <div style="background:{t_surface}; border:1px solid {t_border}; border-radius:6px; padding:16px 20px;">
                <b style="color:{t_text}; font-size:0.9rem;">Architecture Overview</b>
                <p style="font-size:0.82rem; color:{t_subtext}; line-height:1.5; margin-top:6px;">
                    The platform coordinates batch processing for enterprise customer grievance logs.
                    It supports heterogeneous formats (<b>PDF, Word DOCX, Plain Text</b>), applies schema-bound LLM extraction chains,
                    drafts empathetic customer emails, and prepares internal managerial memos.
                </p>
                <b style="color:{t_text}; font-size:0.85rem;">Pipeline Stages:</b>
                <ol style="font-size:0.8rem; color:{t_subtext}; line-height:1.5; padding-left:16px; margin-top:4px;">
                    <li><b>Document Loader</b>: Extracts raw text bodies and metadata from ingested files.</li>
                    <li><b>Structured Extraction Chain</b>: Binds Pydantic schemas to LLM function calling.</li>
                    <li><b>Response Email Chain</b>: Generates formal customer communications.</li>
                    <li><b>Briefing Memo Chain</b>: Prepares root-cause executive summaries.</li>
                </ol>
            </div>
            """,
            unsafe_allow_html=True
        )

    with col_ab_right:
        st.markdown(
            f"""
            <div style="background:{t_surface}; border:1px solid {t_border}; border-radius:6px; padding:16px 20px;">
                <b style="color:{t_text}; font-size:0.9rem;">System Specifications</b>
                <ul style="list-style:none; padding:0; font-size:0.8rem; color:{t_subtext}; line-height:1.6; margin-top:6px;">
                    <li><b>Platform Release:</b> v1.0.0</li>
                    <li><b>Core Framework:</b> Streamlit & Python</li>
                    <li><b>LLM Framework:</b> LangChain Expression Language (LCEL)</li>
                    <li><b>Persistence:</b> Local File Manifests (SHA-256 Hashing)</li>
                    <li><b>Access Guard:</b> Administrative Session Gate</li>
                </ul>
                <hr style="border:none; border-top:1px solid {t_border}; margin:10px 0;">
                <b style="font-size:0.82rem; color:{t_text};">Deterministic Cache Strategy</b>
                <p style="font-size:0.78rem; color:{t_subtext}; margin-top:4px;">
                    Each input file is hashed via SHA-256. If a document hash matches the registry and artifacts exist on disk, 
                    the pipeline reuses previous extractions at zero latency.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )

# -------------------------------------------------------------
# FIXED BOTTOM FOOTER
# -------------------------------------------------------------
st.markdown('<div class="app-footer">AI Case Processing Engine &nbsp;|&nbsp; Enterprise Release: <b>v1.0.0</b></div>', unsafe_allow_html=True)