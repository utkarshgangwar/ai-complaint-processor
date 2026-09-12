import os
import json
import time
from pathlib import Path
import pandas as pd
import streamlit as st
import extra_streamlit_components as stx

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
# 1-HOUR PERSISTENT AUTHENTICATION (COOKIES + SESSION STATE)
# -------------------------------------------------------------
AUTH_USER = os.getenv("APP_USER", "admin")
AUTH_PASS = os.getenv("APP_PASSWORD", "secretpassword123")
SESSION_MAX_AGE_SECONDS = 3600  # 1 Hour TTL

cookie_manager = stx.CookieManager()

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

auth_cookie = cookie_manager.get("auth_session")
current_ts = int(time.time())

if auth_cookie and isinstance(auth_cookie, dict):
    saved_user = auth_cookie.get("user")
    login_ts = auth_cookie.get("timestamp", 0)

    if saved_user == AUTH_USER and (current_ts - login_ts) < SESSION_MAX_AGE_SECONDS:
        st.session_state.authenticated = True
    else:
        cookie_manager.delete("auth_session")
        st.session_state.authenticated = False

# -------------------------------------------------------------
# SESSION STATE INITIALIZATION
# -------------------------------------------------------------
PAGE_MAIN = "📊 Main Dashboard"
PAGE_REPO = "📁 Manage & Ingest Files"
PAGE_ABOUT = "ℹ️ About Platform"
PAGE_OPTIONS = [PAGE_MAIN, PAGE_REPO, PAGE_ABOUT]

if "active_page" not in st.session_state:
    st.session_state.active_page = PAGE_MAIN

if "main_uploader_key" not in st.session_state:
    st.session_state.main_uploader_key = 0

# -------------------------------------------------------------
# FIXED PRODUCTION THEME PALETTE
# -------------------------------------------------------------
t_bg = "#f8fafc"
t_surface = "#ffffff"
t_border = "#e2e8f0"
t_text = "#0f172a"
t_subtext = "#64748b"
t_divider = "#f1f5f9"
t_metric_bg = "#ffffff"
t_badge_proc = ("#dcfce7", "#15803d", "#bbf7d0")
t_badge_unpr = ("#f1f5f9", "#475569", "#e2e8f0")
t_badge_err = ("#fee2e2", "#b91c1c", "#fecaca")

# -------------------------------------------------------------
# CLEAN CSS (RESPONSIVE INTERFACE & TABLE EXPANSION)
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

    div[data-testid="stDataFrame"] {{
        width: 100% !important;
        border: 1px solid {t_border} !important;
        border-radius: 8px !important;
        overflow: hidden !important;
    }}

    div[data-testid="stButton"] button {{
        padding: 2px 8px !important;
        min-height: 28px !important;
        font-size: 0.75rem !important;
        border-radius: 4px !important;
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
# LOGIN FORM (SETS 1-HOUR EXPIRING COOKIE)
# -------------------------------------------------------------
def login_form():
    col1, col2, col3 = st.columns([1, 1.1, 1])
    with col2:
        st.markdown("<div style='height: 100px;'></div>", unsafe_allow_html=True)
        st.markdown(
            f"""
            <div style="background:{t_surface}; border:1px solid {t_border}; border-radius:8px; padding:20px 24px;">
                <h4 style="margin-bottom:2px; color:{t_text};">🔐 Enterprise Case Portal</h4>
                <p style="color:{t_subtext}; font-size:0.8rem; margin-bottom:12px;">Sign in with administrative credentials. Sessions persist for 1 hour.</p>
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
                    cookie_payload = {
                        "user": AUTH_USER,
                        "timestamp": int(time.time())
                    }
                    cookie_manager.set(
                        "auth_session", 
                        cookie_payload, 
                        max_age=SESSION_MAX_AGE_SECONDS,
                        key="set_auth_cookie"
                    )
                    st.session_state.authenticated = True
                    st.toast("Authenticated! Session valid for 1 hour.")
                    time.sleep(0.3)
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

def clear_artifacts_only(filename):
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

def delete_file_and_artifacts(filename):
    target_path = data_dir / filename
    if target_path.exists():
        target_path.unlink()
    clear_artifacts_only(filename)

    if st.session_state.selected_doc == filename:
        st.session_state.selected_doc = None

def get_file_status_label(filename, errors_dict):
    if filename in errors_dict:
        return "⚠️ Errored"

    stem = get_base_filename(filename)
    json_file = structured_dir / f"{stem}.json"
    email_file = emails_dir / f"{stem}_email.txt"
    summary_file = summaries_dir / f"{stem}_summary.txt"

    if json_file.exists() and email_file.exists() and summary_file.exists():
        return "✅ Processed"
    return "⏳ Unprocessed"

error_log = load_error_log()

# -------------------------------------------------------------
# SIDEBAR NAVIGATION
# -------------------------------------------------------------
with st.sidebar:
    st.markdown(
        f"""
        <div style="margin-bottom: 12px;">
            <div style="font-size: 1.15rem; font-weight: 800; color: {t_text};">⚡ AI Case Engine</div>
            <div style="font-size: 0.72rem; color: {t_subtext};">Session active (1h TTL) &bull; <b>{AUTH_USER}</b></div>
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
    
    if st.button("Log Out", key="sidebar_logout_btn", use_container_width=True):
        cookie_manager.delete("auth_session")
        st.session_state.authenticated = False
        time.sleep(0.2)
        st.rerun()

# -------------------------------------------------------------
# RESPONSIVE & HEADER-SORTABLE DATAFRAME COMPONENT (PAGE 1)
# -------------------------------------------------------------
def render_sortable_dashboard_table(df_subset, table_key):
    if df_subset.empty:
        st.info("No matching records found in this view.")
        return

    cols_to_display = [
        "file_name", "customer_name", "complaint_category", 
        "case_status", "escalation_required", "latency_seconds"
    ]
    available_cols = [c for c in cols_to_display if c in df_subset.columns]
    display_df = df_subset[available_cols].copy()

    if "escalation_required" in display_df.columns:
        display_df["escalation_required"] = display_df["escalation_required"].map(
            lambda x: "🚨 Escalated" if bool(x) else "🟢 Standard"
        )

    col_config = {
        "file_name": st.column_config.TextColumn("File Name", help="Click header to sort by File Name"),
        "customer_name": st.column_config.TextColumn("Customer", help="Click header to sort by Customer"),
        "complaint_category": st.column_config.TextColumn("Category", help="Click header to sort by Category"),
        "case_status": st.column_config.TextColumn("Status", help="Click header to sort by Case Status"),
        "escalation_required": st.column_config.TextColumn("Priority", help="Click header to sort by Priority"),
        "latency_seconds": st.column_config.NumberColumn("Latency", format="%.2fs", help="Click header to sort by Latency"),
    }

    st.dataframe(
        display_df,
        column_config=col_config,
        use_container_width=True,
        hide_index=True,
        height=360,
        key=f"df_sortable_{table_key}"
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

        # Search Bar & Navigation Tabs
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
                key="active_tab_selector"
            )
            if active_tab != st.session_state.active_tab:
                st.session_state.active_tab = active_tab
                st.rerun()

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
        if st.session_state.active_tab == TAB_ALL:
            col_hdr, col_dl = st.columns([8.8, 1.2])
            with col_hdr:
                st.caption(f"Showing all processed cases ({len(filtered_df)} total) &bull; Click any header to sort")
            with col_dl:
                if not filtered_df.empty:
                    st.download_button(
                        label="📥 Export CSV",
                        data=filtered_df.to_csv(index=False).encode("utf-8"),
                        file_name="final_report.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
            render_sortable_dashboard_table(filtered_df, table_key="all_cases")

        elif st.session_state.active_tab == TAB_ESC:
            st.caption("🚨 Priority Escalation Queue &bull; Click any header to sort")
            df_escalated = filtered_df[filtered_df["escalation_required"] == True] if not filtered_df.empty and "escalation_required" in filtered_df else pd.DataFrame()
            render_sortable_dashboard_table(df_escalated, table_key="esc_cases")

        elif st.session_state.active_tab == TAB_ACT:
            st.caption("⏳ Active Work Queue &bull; Click any header to sort")
            df_active = filtered_df[filtered_df["case_status"].isin(["Open", "In Progress"])] if not filtered_df.empty and "case_status" in filtered_df else pd.DataFrame()
            render_sortable_dashboard_table(df_active, table_key="act_cases")

        elif st.session_state.active_tab == TAB_ERR:
            st.caption("⚠️ Document Processing Exceptions &bull; Click headers to sort")
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
                        "File Name": st.column_config.TextColumn("File Name", help="Sort by file name"),
                        "Exception Reason": st.column_config.TextColumn("Exception Trace", help="Sort by exception message"),
                    },
                    use_container_width=True,
                    hide_index=True,
                    height=280
                )

        elif st.session_state.active_tab == TAB_INS:
            if not all_files:
                st.info("No processed artifacts available for inspection.")
            else:
                col_sel, col_stat = st.columns([5, 5])
                with col_sel:
                    selected_index = all_files.index(st.session_state.selected_doc) if st.session_state.selected_doc in all_files else 0
                    selected_file = st.selectbox("Inspect Document:", all_files, index=selected_index, label_visibility="collapsed", key="doc_selector")
                    st.session_state.selected_doc = selected_file
                with col_stat:
                    st.caption(f"Currently viewing artifacts for: **{st.session_state.selected_doc}**")

                if selected_file:
                    stem = get_base_filename(selected_file)
                    with st.container(height=420):
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
            accept_multiple_files=True,
            key=f"main_ingest_uploader_{st.session_state.main_uploader_key}"
        )
        if uploaded_files:
            for file in uploaded_files:
                target_path = data_dir / file.name
                with open(target_path, "wb") as f:
                    f.write(file.getbuffer())
            st.toast(f"Saved {len(uploaded_files)} file(s) to `{data_dir.name}/`")
            st.session_state.main_uploader_key += 1
            st.rerun()

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

    # Repository Listing & Multi-Row Selection Table
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
        st.caption("Select one or more rows directly using the checkboxes, or click headers to sort.")

        repo_rows = []
        for name in filtered_repo_files:
            file_path = data_dir / name
            size_kb = round(file_path.stat().st_size / 1024, 2) if file_path.exists() else 0.0
            status_label = get_file_status_label(name, error_log)
            file_ext = Path(name).suffix.lower()

            repo_rows.append({
                "File Name": name,
                "Extension": file_ext,
                "Size (KB)": size_kb,
                "Status": status_label
            })

        repo_df = pd.DataFrame(repo_rows)

        col_repo_config = {
            "File Name": st.column_config.TextColumn("File Name", help="Click to sort by name"),
            "Extension": st.column_config.TextColumn("Extension", help="Click to sort by file type"),
            "Size (KB)": st.column_config.NumberColumn("Size (KB)", format="%.2f KB", help="Click to sort by file size"),
            "Status": st.column_config.TextColumn("Status", help="Click to sort by processing status"),
        }

        # Multi-row selectable, responsive and header-sortable table
        selection_event = st.dataframe(
            repo_df,
            column_config=col_repo_config,
            use_container_width=True,
            hide_index=True,
            selection_mode="multi-row",
            on_select="rerun",
            height=320,
            key="repo_interactive_dataframe"
        )

        selected_row_indices = selection_event.selection.rows
        selected_files = [repo_df.iloc[i]["File Name"] for i in selected_row_indices] if selected_row_indices else []

        st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)
        col_status_info, col_del_action = st.columns([7, 3])
        with col_status_info:
            if selected_files:
                st.caption(f"Selected **{len(selected_files)}** file(s): `{', '.join(selected_files)}`")
            else:
                st.caption("No files selected in table.")

        with col_del_action:
            delete_btn_label = f"🗑️ Delete Selected ({len(selected_files)})" if selected_files else "🗑️ Delete Selected"
            if st.button(delete_btn_label, disabled=(len(selected_files) == 0), type="primary", use_container_width=True):
                for f in selected_files:
                    delete_file_and_artifacts(f)
                st.toast(f"Deleted {len(selected_files)} file(s) from storage.")
                time.sleep(0.3)
                st.rerun()

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