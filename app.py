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
# SESSION STATE INITIALIZATION & SAFE REDIRECT RESOLUTION
# -------------------------------------------------------------
PAGE_MAIN = "📊 Main Dashboard"
PAGE_REPO = "📁 Manage & Ingest Files"
PAGE_ABOUT = "ℹ️ About Platform"
PAGE_OPTIONS = [PAGE_MAIN, PAGE_REPO, PAGE_ABOUT]

TAB_ALL = "📊 All Cases"
TAB_ESC = "🚨 Escalated"
TAB_ACT = "⏳ Active"
TAB_ERR = "⚠️ Failed / Errored"
TAB_OTH = "📦 Others / Insufficient"
TAB_INS = "🔍 Inspector"
TAB_OPTIONS = [TAB_ALL, TAB_ESC, TAB_ACT, TAB_ERR, TAB_OTH, TAB_INS]

# Consume staged redirects before widgets instantiate
if "redirect_target" in st.session_state:
    st.session_state.sidebar_page_selector = st.session_state.pop("redirect_target")

if "tab_redirect_target" in st.session_state:
    st.session_state.active_tab_selector = st.session_state.pop("tab_redirect_target")

if "sidebar_page_selector" not in st.session_state:
    st.session_state.sidebar_page_selector = PAGE_MAIN

if "active_tab_selector" not in st.session_state:
    st.session_state.active_tab_selector = TAB_ALL

if "selected_doc" not in st.session_state:
    st.session_state.selected_doc = None

if "search_query" not in st.session_state:
    st.session_state.search_query = ""

if "main_uploader_key" not in st.session_state:
    st.session_state.main_uploader_key = 0

if "repo_table_nonce" not in st.session_state:
    st.session_state.repo_table_nonce = 0

# -------------------------------------------------------------
# FIXED PRODUCTION THEME PALETTE
# -------------------------------------------------------------
t_bg = "#f8fafc"
t_surface = "#ffffff"
t_surface_alt = "#f8fafc"
t_border = "#e2e8f0"
t_border_strong = "#cbd5e1"
t_text = "#0f172a"
t_subtext = "#64748b"
t_metric_bg = "#ffffff"

# -------------------------------------------------------------
# CLEAN CSS (FIXED OVERLAPS, PROPER CLEARANCE & COMPACT TABLES)
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
        height: 0px !important;
    }}

    /* Lock viewport height cleanly */
    html, body, [data-testid="stAppViewContainer"] {{
        background-color: {t_bg} !important;
        color: {t_text} !important;
        overflow: hidden !important;
        height: 100vh !important;
        max-height: 100vh !important;
    }}

    /* Proper top clearance to prevent header overlaps */
    .block-container {{
        padding-top: 1.2rem !important;
        padding-bottom: 2rem !important;
        padding-left: 1.2rem !important;
        padding-right: 1.2rem !important;
        max-width: 99% !important;
        height: calc(100vh - 28px) !important;
        overflow-y: hidden !important;
    }}

    /* Balanced spacing between major page sections */
    div[data-testid="stVerticalBlock"] {{
        gap: 0.45rem !important;
    }}

    section[data-testid="stSidebar"] {{
        background-color: {t_surface} !important;
        border-right: 1px solid {t_border} !important;
        width: 290px !important;
    }}

    /* Heading bar with clean spacing */
    .dashboard-page-title {{
        font-size: 1.05rem !important;
        font-weight: 800 !important;
        color: {t_text} !important;
        margin-top: 10px !important;
        margin-bottom: 2rem !important;
        # display: block !important;
        line-height: 1.3 !important;
        justify-content: center;
        display: flex;
        
    }}

    /* Metric Cards */
    div[data-testid="stMetric"] {{
        background: {t_metric_bg} !important;
        border: 1px solid {t_border} !important;
        border-radius: 6px !important;
        padding: 6px 10px !important;
        min-height: 52px !important;
    }}
    div[data-testid="stMetric"] label {{
        color: {t_subtext} !important;
        font-weight: 600 !important;
        font-size: 0.69rem !important;
        margin-bottom: 0px !important;
        line-height: 1.1 !important;
    }}
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {{
        color: {t_text} !important;
        font-size: 1.15rem !important;
        font-weight: 700 !important;
        line-height: 1.1 !important;
    }}

    div[data-testid="stDataFrame"] {{
        width: 100% !important;
        border: 1px solid {t_border} !important;
        border-radius: 6px !important;
        overflow: hidden !important;
    }}

    .table-cell-text {{
        font-size: 0.77rem !important;
        line-height: 1.2 !important;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }}

    /* =========================================================
       BOXED HEADER ROW: SEAMLESS CARD BORDER & VERTICAL DIVIDERS
       ========================================================= */
    div[data-testid="stHorizontalBlock"]:has(.table-header-anchor) {{
        border: 1.5px solid {t_border_strong} !important;
        border-radius: 7px !important;
        background-color: {t_surface} !important;
        padding: 3px 4px !important;
        margin-top: 2px !important;
        margin-bottom: 4px !important;
        display: flex !important;
        align-items: center !important;
        min-height: 30px !important;
    }}

    div[data-testid="stHorizontalBlock"]:has(.table-header-anchor) div[data-testid="stColumn"]:not(:last-child) {{
        border-right: 1px solid {t_border} !important;
    }}

    div[data-testid="stHorizontalBlock"]:has(.table-header-anchor) div[data-testid="stColumn"] {{
        padding-left: 6px !important;
        padding-right: 6px !important;
        display: flex !important;
        align-items: center !important;
    }}

    .table-header-label {{
        font-size: 0.69rem !important;
        font-weight: 700 !important;
        color: {t_subtext} !important;
        letter-spacing: 0.05em !important;
        text-transform: uppercase !important;
        margin: 0 !important;
        user-select: none !important;
        width: 100% !important;
        line-height: 1.1 !important;
    }}

    /* =========================================================
       HEADER SORT BUTTONS: ZERO BORDER, FLAT GHOST STYLE
       ========================================================= */
    div[data-testid="stHorizontalBlock"]:has(.table-header-anchor) div[data-testid="stButton"] {{
        margin: 0 !important;
        padding: 0 !important;
        width: 100% !important;
    }}

    div[data-testid="stHorizontalBlock"]:has(.table-header-anchor) button,
    div[data-testid="stHorizontalBlock"]:has(.table-header-anchor) div[data-testid="stButton"] button {{
        background: transparent !important;
        background-color: transparent !important;
        border: none !important;
        border-width: 0px !important;
        border-style: none !important;
        outline: none !important;
        box-shadow: none !important;
        border-radius: 0px !important;
        padding: 0px 4px !important;
        min-height: 22px !important;
        height: 22px !important;
        width: 100% !important;
        font-size: 0.70rem !important;
        font-weight: 600 !important;
        color: #334155 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: flex-start !important;
        transition: color 0.15s ease !important;
    }}

    div[data-testid="stHorizontalBlock"]:has(.table-header-anchor) button:hover,
    div[data-testid="stHorizontalBlock"]:has(.table-header-anchor) div[data-testid="stButton"] button:hover {{
        border: none !important;
        border-width: 0px !important;
        outline: none !important;
        box-shadow: none !important;
        background: transparent !important;
        background-color: transparent !important;
        color: #0284c7 !important;
    }}

    div[data-testid="stHorizontalBlock"]:has(.table-header-anchor) button:focus,
    div[data-testid="stHorizontalBlock"]:has(.table-header-anchor) button:active,
    div[data-testid="stHorizontalBlock"]:has(.table-header-anchor) div[data-testid="stButton"] button:focus,
    div[data-testid="stHorizontalBlock"]:has(.table-header-anchor) div[data-testid="stButton"] button:active {{
        border: none !important;
        border-width: 0px !important;
        outline: none !important;
        box-shadow: none !important;
        background: transparent !important;
        background-color: transparent !important;
    }}

    /* =========================================================
       DATA ROWS CONTAINER: VERTICAL LINES, ZEBRA STRIPING, ZERO GAPS
       ========================================================= */
    div[data-testid="stVerticalBlock"]:has(> div > div[data-testid="stHorizontalBlock"]:has(.table-row-anchor)) {{
        border: 1px solid {t_border} !important;
        border-radius: 7px !important;
        overflow: hidden !important;
        background: {t_surface} !important;
        gap: 0px !important;
    }}

    div[data-testid="stHorizontalBlock"]:has(.table-row-anchor) {{
        border-bottom: 1px solid {t_border} !important;
        padding: 0px 4px !important;
        margin: 0 !important;
        min-height: 28px !important;
        height: 28px !important;
        display: flex !important;
        align-items: center !important;
    }}

    div[data-testid="stHorizontalBlock"]:has(.table-row-anchor):last-child {{
        border-bottom: none !important;
    }}

    /* Alternating Zebra Rows (White / Light Gray) */
    div[data-testid="stHorizontalBlock"]:has(.row-white) {{
        background-color: #ffffff !important;
    }}

    div[data-testid="stHorizontalBlock"]:has(.row-gray) {{
        background-color: #f8fafc !important;
    }}

    div[data-testid="stHorizontalBlock"]:has(.table-row-anchor) div[data-testid="stColumn"]:not(:last-child) {{
        border-right: 1px solid {t_border} !important;
    }}

    div[data-testid="stHorizontalBlock"]:has(.table-row-anchor) div[data-testid="stColumn"] {{
        padding-left: 8px !important;
        padding-right: 8px !important;
        display: flex !important;
        align-items: center !important;
    }}

    div[data-testid="stHorizontalBlock"]:has(.table-row-anchor) div[data-testid="stColumn"]:first-child,
    div[data-testid="stHorizontalBlock"]:has(.table-header-anchor) div[data-testid="stColumn"]:first-child {{
        padding-left: 1px !important;
        padding-right: 1px !important;
        justify-content: center !important;
    }}

    /* Compact View Action Icon Button */
    .view-btn-container div[data-testid="stButton"] button {{
        padding: 0px !important;
        min-height: 20px !important;
        height: 20px !important;
        width: 100% !important;
        font-size: 0.74rem !important;
        border-radius: 4px !important;
        line-height: 1 !important;
        border: 1px solid {t_border} !important;
        background: {t_surface} !important;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03) !important;
    }}

    .view-btn-container div[data-testid="stButton"] button:hover {{
        border-color: #94a3b8 !important;
        color: #0284c7 !important;
    }}

    /* Compact global buttons & inputs */
    div[data-testid="stButton"] button {{
        padding: 1px 6px !important;
        min-height: 24px !important;
        font-size: 0.73rem !important;
        border-radius: 4px !important;
    }}

    div[data-testid="stTextInput"] input {{
        min-height: 28px !important;
        height: 28px !important;
        padding: 2px 8px !important;
        font-size: 0.76rem !important;
    }}

    div[data-testid="stRadio"] {{
        padding: 0 !important;
        margin: 0 !important;
    }}

    .app-footer {{
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        height: 24px;
        background-color: {t_surface};
        border-top: 1px solid {t_border};
        color: {t_subtext};
        text-align: right;
        padding: 2px 16px;
        font-size: 0.65rem;
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
        st.markdown("<div style='height: 80px;'></div>", unsafe_allow_html=True)
        st.markdown(
            f"""
            <div style="background:{t_surface}; border:1px solid {t_border}; border-radius:8px; padding:18px 20px;">
                <h4 style="margin-bottom:2px; font-size:1.05rem; color:{t_text};">🔐 Enterprise Case Portal</h4>
                <p style="color:{t_subtext}; font-size:0.75rem; margin-bottom:10px;">Sign in with administrative credentials. Sessions persist for 1 hour.</p>
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
insufficient_path = csv_path.parent / ".insufficient_records.json"

def load_json_file(file_path: Path) -> dict:
    if file_path.exists():
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

error_log = load_json_file(errors_path)
insufficient_log = load_json_file(insufficient_path)

def open_inspector_tab(filename: str):
    """Sets the selected doc, stages redirection to TAB_INS, and reruns cleanly."""
    st.session_state.selected_doc = filename
    st.session_state.tab_redirect_target = TAB_INS
    st.rerun()

def clear_artifacts_only(filename):
    stem = get_base_filename(filename)
    for art in [
        structured_dir / f"{stem}.json",
        emails_dir / f"{stem}_email.txt",
        summaries_dir / f"{stem}_summary.txt"
    ]:
        if art.exists():
            art.unlink()

    for p in [manifest_path, errors_path, insufficient_path]:
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if filename in data:
                    del data[filename]
                    with open(p, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2)
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

def get_file_status_label(filename, errors_dict, insufficient_dict):
    if filename in errors_dict:
        return "⚠️ Errored"
    if filename in insufficient_dict:
        return "📦 Insufficient Data"

    stem = get_base_filename(filename)
    json_file = structured_dir / f"{stem}.json"
    if json_file.exists():
        return "✅ Processed"
    return "⏳ Unprocessed"

# -------------------------------------------------------------
# SIDEBAR NAVIGATION
# -------------------------------------------------------------
with st.sidebar:
    st.markdown(
        f"""
        <div style="margin-bottom: 8px;">
            <div style="font-size: 1.05rem; font-weight: 800; color: {t_text};">⚡ AI Case Engine</div>
            <div style="font-size: 0.68rem; color: {t_subtext};">Session active (1h TTL) &bull; <b>{AUTH_USER}</b></div>
        </div>
        """,
        unsafe_allow_html=True
    )

    current_page = st.radio(
        "Navigation",
        options=PAGE_OPTIONS,
        key="sidebar_page_selector"
    )

    st.markdown("<hr style='margin: 8px 0; border: none; border-top: 1px solid " + t_border + ";'>", unsafe_allow_html=True)
    
    if st.button("Log Out", key="sidebar_logout_btn", use_container_width=True):
        cookie_manager.delete("auth_session")
        st.session_state.authenticated = False
        time.sleep(0.2)
        st.rerun()

# -------------------------------------------------------------
# COMMON TABLE COMPONENT: BOXED HEADER, VERTICAL LINES & ZEBRA ROWS
# -------------------------------------------------------------
def render_common_dashboard_table(
    df_subset: pd.DataFrame, 
    table_key: str, 
    columns_config: list, 
    enable_view_action: bool = True
):
    if df_subset.empty:
        st.info("No records found in this view.")
        return

    # Tracking sort state per-table
    sort_col_key = f"{table_key}_sort_col"
    sort_asc_key = f"{table_key}_sort_asc"

    if sort_col_key not in st.session_state:
        st.session_state[sort_col_key] = columns_config[0]["field"]
    if sort_asc_key not in st.session_state:
        st.session_state[sort_asc_key] = True

    active_sort_col = st.session_state[sort_col_key]
    active_sort_asc = st.session_state[sort_asc_key]

    # Sort dataframe safely
    if active_sort_col in df_subset.columns:
        sorted_df = df_subset.sort_values(
            by=active_sort_col, 
            ascending=active_sort_asc, 
            na_position="last"
        ).copy()
    else:
        sorted_df = df_subset.copy()

    # Pagination state
    page_size_options = [5, 10, 20]
    page_state_key = f"{table_key}_current_page"
    size_state_key = f"{table_key}_pg_size"

    if size_state_key not in st.session_state:
        st.session_state[size_state_key] = 5

    page_size = st.session_state[size_state_key]
    total_records = len(sorted_df)
    total_pages = max(1, (total_records + page_size - 1) // page_size)

    if page_state_key not in st.session_state or st.session_state[page_state_key] > total_pages:
        st.session_state[page_state_key] = 1

    current_p = st.session_state[page_state_key]
    start_idx = (current_p - 1) * page_size
    end_idx = min(start_idx + page_size, total_records)
    page_df = sorted_df.iloc[start_idx:end_idx].copy()

    # Proportions
    proportions = [0.55] if enable_view_action else []
    proportions.extend([cfg["width"] for cfg in columns_config])

    # 1. CONTINUOUS BOXED HEADER
    header_cols = st.columns(proportions)
    h_idx = 0

    if enable_view_action:
        with header_cols[h_idx]:
            st.markdown(
                '<div class="table-header-anchor"></div>', 
                unsafe_allow_html=True
            )
        h_idx += 1
    else:
        with header_cols[0]:
            st.markdown('<div class="table-header-anchor"></div>', unsafe_allow_html=True)

    for cfg in columns_config:
        field = cfg["field"]
        header_text = cfg["header"]

        if active_sort_col == field:
            indicator = " ▲" if active_sort_asc else " ▼"
        else:
            indicator = ""

        with header_cols[h_idx]:
            st.markdown('<div class="header-sort-btn">', unsafe_allow_html=True)
            if st.button(f"{header_text}{indicator}", key=f"hbtn_{table_key}_{field}", help=f"Sort by {header_text}", use_container_width=True):
                if st.session_state[sort_col_key] == field:
                    st.session_state[sort_asc_key] = not st.session_state[sort_asc_key]
                else:
                    st.session_state[sort_col_key] = field
                    st.session_state[sort_asc_key] = True
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        h_idx += 1

    # 2. DATA ROWS CONTAINER: VERTICAL LINES, ZEBRA STRIPING, ZERO EXTRA GAPS
    with st.container(height=265):
        for idx, (_, row) in enumerate(page_df.iterrows()):
            row_cols = st.columns(proportions)
            row_col_idx = 0

            fname = str(row.get("file_name", ""))
            row_bg_class = "row-white" if (idx % 2 == 0) else "row-gray"

            if enable_view_action:
                with row_cols[row_col_idx]:
                    st.markdown(f'<div class="table-row-anchor {row_bg_class}"></div>', unsafe_allow_html=True)
                    st.markdown('<div class="view-btn-container">', unsafe_allow_html=True)
                    if st.button("👁️", key=f"vbtn_{table_key}_{fname}_{idx}", help=f"Inspect details for {fname}"):
                        open_inspector_tab(fname)
                    st.markdown('</div>', unsafe_allow_html=True)
                row_col_idx += 1
            else:
                with row_cols[0]:
                    st.markdown(f'<div class="table-row-anchor {row_bg_class}"></div>', unsafe_allow_html=True)

            for cfg in columns_config:
                val = row.get(cfg["field"], "N/A")
                with row_cols[row_col_idx]:
                    if cfg.get("is_badge", False):
                        is_esc = bool(val)
                        badge_text = "🚨 Escalated" if is_esc else "🟢 Standard"
                        st.markdown(f"<span class='table-cell-text' style='font-weight:600;'>{badge_text}</span>", unsafe_allow_html=True)
                    elif cfg.get("is_mono", False):
                        st.markdown(f"<span class='table-cell-text' style='font-weight:600; color:{t_text}; font-family:monospace;' title='{val}'>{val}</span>", unsafe_allow_html=True)
                    elif cfg.get("is_latency", False):
                        latency_str = f"{val:.2f}s" if isinstance(val, (int, float)) else str(val)
                        st.markdown(f"<span class='table-cell-text' style='color:{t_subtext}; font-family:monospace;'>{latency_str}</span>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<span class='table-cell-text' title='{val}'>{val}</span>", unsafe_allow_html=True)
                row_col_idx += 1

    # 3. PAGINATION BAR SITUATED STRICTLY BELOW TABLE
    c_prev, c_info, c_next, c_size = st.columns([0.8, 5.4, 0.8, 1.8])

    with c_prev:
        if st.button("◀ Prev", key=f"{table_key}_p_prev", disabled=(current_p <= 1), use_container_width=True):
            st.session_state[page_state_key] -= 1
            st.rerun()

    with c_info:
        st.markdown(
            f"<div style='text-align:center; padding-top:4px; font-size:0.72rem; color:{t_subtext};'>"
            f"Showing <b>{start_idx + 1}–{end_idx}</b> of <b>{total_records}</b> records &nbsp;|&nbsp; Page <b>{current_p}/{total_pages}</b>"
            f"</div>",
            unsafe_allow_html=True
        )

    with c_next:
        if st.button("Next ▶", key=f"{table_key}_p_next", disabled=(current_p >= total_pages), use_container_width=True):
            st.session_state[page_state_key] += 1
            st.rerun()

    with c_size:
        new_size = st.selectbox(
            "Rows/Page",
            options=page_size_options,
            index=page_size_options.index(page_size),
            key=f"{table_key}_psel",
            label_visibility="collapsed"
        )
        if new_size != page_size:
            st.session_state[size_state_key] = new_size
            st.session_state[page_state_key] = 1
            st.rerun()

# Shared column schemas for primary complaint tables
PRIMARY_CASE_COLUMNS = [
    {"field": "file_name", "header": "Document Name", "width": 3.0, "is_mono": True},
    {"field": "customer_name", "header": "Customer", "width": 2.2},
    {"field": "complaint_category", "header": "Category", "width": 2.2},
    {"field": "case_status", "header": "Status", "width": 1.1},
    {"field": "escalation_required", "header": "Priority", "width": 1.2, "is_badge": True},
    {"field": "latency_seconds", "header": "Latency", "width": 1.0, "is_latency": True},
]

# =============================================================
# PAGE 1: MAIN DASHBOARD
# =============================================================
if current_page == PAGE_MAIN:
    st.markdown('<div class="dashboard-page-title">📊 Customer Case Processing Dashboard</div>', unsafe_allow_html=True)

    has_report = csv_path.exists()
    has_errors = bool(error_log)
    has_insufficient = bool(insufficient_log)

    if has_report or has_errors or has_insufficient:
        df_report = pd.read_csv(csv_path) if has_report else pd.DataFrame()
        
        if not df_report.empty and "file_name" in df_report.columns:
            valid_report_df = df_report[~df_report["file_name"].isin(insufficient_log.keys())]
        else:
            valid_report_df = df_report

        all_files = valid_report_df["file_name"].tolist() if not valid_report_df.empty and "file_name" in valid_report_df else []
        all_inspectable = list(dict.fromkeys(all_files + list(insufficient_log.keys())))

        if all_inspectable and (not st.session_state.selected_doc or st.session_state.selected_doc not in all_inspectable):
            st.session_state.selected_doc = all_inspectable[0]

        total_cases = len(valid_report_df)
        escalations_needed = int(valid_report_df["escalation_required"].sum()) if not valid_report_df.empty and "escalation_required" in valid_report_df else 0
        active_pending = int(valid_report_df["case_status"].isin(["Open", "In Progress"]).sum()) if not valid_report_df.empty and "case_status" in valid_report_df else 0
        num_errored = len(error_log)
        num_insufficient = len(insufficient_log)

        # KPI Metrics with explicit gap
        kpi_col1, kpi_col2, kpi_col3, kpi_col4, kpi_col5 = st.columns(5)
        kpi_col1.metric("Processed Cases", total_cases)
        kpi_col2.metric("Escalations Needed", escalations_needed)
        kpi_col3.metric("Active / Pending", active_pending)
        kpi_col4.metric("Failed / Errored", num_errored, delta=f"{num_errored} Errors" if num_errored > 0 else None, delta_color="inverse")
        kpi_col5.metric("Others / Insufficient", num_insufficient)

        # Search Bar & Navigation Tabs (Single Compact Band)
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
                horizontal=True,
                label_visibility="collapsed",
                key="active_tab_selector"
            )

        filtered_df = valid_report_df.copy()
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
                st.caption(f"Showing all processed cases ({len(filtered_df)} total) &bull; Click column headers to sort &bull; Click 👁️ to inspect")
            with col_dl:
                if not filtered_df.empty:
                    st.download_button(
                        label="📥 Export CSV",
                        data=filtered_df.to_csv(index=False).encode("utf-8"),
                        file_name="final_report.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
            render_common_dashboard_table(filtered_df, "all_cases", PRIMARY_CASE_COLUMNS, enable_view_action=True)

        elif active_tab == TAB_ESC:
            st.caption("🚨 Priority Escalation Queue &bull; Click column headers to sort &bull; Click 👁️ to inspect")
            df_escalated = filtered_df[filtered_df["escalation_required"] == True] if not filtered_df.empty and "escalation_required" in filtered_df else pd.DataFrame()
            render_common_dashboard_table(df_escalated, "esc_cases", PRIMARY_CASE_COLUMNS, enable_view_action=True)

        elif active_tab == TAB_ACT:
            st.caption("⏳ Active Work Queue &bull; Click column headers to sort &bull; Click 👁️ to inspect")
            df_active = filtered_df[filtered_df["case_status"].isin(["Open", "In Progress"])] if not filtered_df.empty and "case_status" in filtered_df else pd.DataFrame()
            render_common_dashboard_table(df_active, "act_cases", PRIMARY_CASE_COLUMNS, enable_view_action=True)

        elif active_tab == TAB_ERR:
            st.caption("⚠️ Document Processing Exceptions &bull; Parser & Execution Failures")
            if not error_log:
                st.success("Zero exceptions registered. All ingested documents processed cleanly.")
            else:
                col_clear_err, _ = st.columns([2, 8])
                with col_clear_err:
                    if st.button("Clear Error Log", use_container_width=True):
                        if errors_path.exists():
                            errors_path.unlink()
                        st.rerun()

                err_df = pd.DataFrame([
                    {"file_name": k, "reason": v} for k, v in error_log.items()
                ])
                err_columns = [
                    {"field": "file_name", "header": "Document Name", "width": 3.5, "is_mono": True},
                    {"field": "reason", "header": "Exception Reason", "width": 6.5},
                ]
                render_common_dashboard_table(err_df, "err_cases", err_columns, enable_view_action=False)

        elif active_tab == TAB_OTH:
            st.caption("📦 Other Documents &bull; Flagged as Insufficient, Absurd, or Incomplete Content")
            if not insufficient_log:
                st.info("No documents currently flagged as insufficient.")
            else:
                col_clear_oth, _ = st.columns([2, 8])
                with col_clear_oth:
                    if st.button("Clear Insufficient Log", use_container_width=True):
                        if insufficient_path.exists():
                            insufficient_path.unlink()
                        st.rerun()

                oth_rows = []
                for fname, reason in insufficient_log.items():
                    oth_rows.append({
                        "file_name": fname,
                        "status": "Insufficient / Absurd Data",
                        "explanation": reason if isinstance(reason, str) else "The document content does not contain sufficient intelligible details to process or draft a response."
                    })

                oth_df = pd.DataFrame(oth_rows)
                oth_columns = [
                    {"field": "file_name", "header": "Document Name", "width": 3.0, "is_mono": True},
                    {"field": "status", "header": "Assessment Status", "width": 2.5},
                    {"field": "explanation", "header": "Observation Details", "width": 4.5},
                ]
                render_common_dashboard_table(oth_df, "oth_cases", oth_columns, enable_view_action=True)

        elif active_tab == TAB_INS:
            if not all_inspectable:
                st.info("No processed artifacts available for inspection.")
            else:
                col_sel, col_stat = st.columns([5, 5])
                with col_sel:
                    selected_index = all_inspectable.index(st.session_state.selected_doc) if st.session_state.selected_doc in all_inspectable else 0
                    selected_file = st.selectbox("Inspect Document:", all_inspectable, index=selected_index, label_visibility="collapsed", key="doc_selector")
                    st.session_state.selected_doc = selected_file
                with col_stat:
                    is_file_insufficient = selected_file in insufficient_log
                    tag_display = "⚠️ (Insufficient Content)" if is_file_insufficient else "✅ (Standard Processed)"
                    st.caption(f"Viewing: **{st.session_state.selected_doc}** {tag_display}")

                if selected_file:
                    stem = get_base_filename(selected_file)
                    is_file_insufficient = selected_file in insufficient_log

                    with st.container(height=310):
                        col_json, col_text = st.columns([1, 1])
                        with col_json:
                            st.markdown(f"<span style='font-size:0.75rem; font-weight:700; color:{t_subtext};'>EXTRACTED JSON DATA</span>", unsafe_allow_html=True)
                            json_file = structured_dir / f"{stem}.json"
                            if json_file.exists():
                                with open(json_file, "r", encoding="utf-8") as f:
                                    json_content = f.read()
                                st.download_button(label="📥 JSON", data=json_content, file_name=f"{stem}.json", mime="application/json", key=f"dl_json_{stem}")
                                st.code(json_content, language="json")
                            else:
                                if is_file_insufficient:
                                    st.warning("No structured schema generated. The source document lacked required complaint fields.")
                                else:
                                    st.warning("Missing JSON artifact.")

                        with col_text:
                            st.markdown(f"<span style='font-size:0.75rem; font-weight:700; color:{t_subtext};'>CUSTOMER RESPONSE EMAIL</span>", unsafe_allow_html=True)
                            
                            if is_file_insufficient:
                                st.error("⚠️ Notice: The file does not contain sufficient or intelligible complaint data. Automated email draft generation was withheld.")
                            else:
                                email_file = emails_dir / f"{stem}_email.txt"
                                if email_file.exists():
                                    with open(email_file, "r", encoding="utf-8") as f:
                                        email_content = f.read()
                                    st.download_button(label="📥 Email (.txt)", data=email_content, file_name=f"{stem}_email.txt", mime="text/plain", key=f"dl_email_{stem}")
                                    st.info(email_content)
                                else:
                                    st.warning("Missing email artifact.")

                            st.markdown("<hr style='margin: 2px 0;'>", unsafe_allow_html=True)
                            st.markdown(f"<span style='font-size:0.75rem; font-weight:700; color:{t_subtext};'>MANAGEMENT BRIEFING MEMO</span>", unsafe_allow_html=True)
                            
                            if is_file_insufficient:
                                st.warning("Notice: Case summary memo bypassed due to insufficient document content.")
                            else:
                                summary_file = summaries_dir / f"{stem}_summary.txt"
                                if summary_file.exists():
                                    with open(summary_file, "r", encoding="utf-8") as f:
                                        summary_content = f.read()
                                    st.download_button(label="📥 Memo (.txt)", data=summary_content, file_name=f"{stem}_summary.txt", mime="text/plain", key=f"dl_sum_{stem}")
                                    st.markdown(summary_content)
                                else:
                                    st.warning("Missing summary artifact.")
    else:
        st.info("No report found yet. Select '📁 Manage & Ingest Files' in the sidebar to upload files and run the workflow.")

# =============================================================
# PAGE 2: MANAGE & INGEST FILES + EXECUTE PIPELINE
# =============================================================
elif current_page == PAGE_REPO:
    st.markdown('<div class="dashboard-page-title">📁 Document Ingestion & Storage Manager</div>', unsafe_allow_html=True)

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
        force_reprocess = st.checkbox(
            "Force Re-process All Files",
            value=False,
            help="Bypasses hash caching and runs extractions from scratch."
        )
        run_pipeline_btn = st.button("⚡ Run Batch Processing Pipeline", type="primary", use_container_width=True)

    # Execution and Redirection
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

        status_text.success("Pipeline executed successfully! Redirecting to Dashboard...")
        progress_bar.empty()
        time.sleep(0.4)
        
        st.session_state.redirect_target = PAGE_MAIN
        st.rerun()

    existing_files = sorted([f.name for f in data_dir.iterdir() if f.is_file()])

    col_rep_head, col_rep_search = st.columns([5, 5])
    with col_rep_head:
        st.markdown(f"<span style='font-size:0.85rem; font-weight:700;'>Stored Documents ({len(existing_files)})</span>", unsafe_allow_html=True)
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
        repo_rows = []
        for name in filtered_repo_files:
            file_path = data_dir / name
            size_kb = round(file_path.stat().st_size / 1024, 2) if file_path.exists() else 0.0
            status_label = get_file_status_label(name, error_log, insufficient_log)
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

        dataframe_key = f"repo_table_v_{st.session_state.repo_table_nonce}"

        selection_event = st.dataframe(
            repo_df,
            column_config=col_repo_config,
            use_container_width=True,
            hide_index=True,
            selection_mode="multi-row",
            on_select="rerun",
            height=280,
            key=dataframe_key
        )

        selected_row_indices = selection_event.selection.rows
        selected_files = [repo_df.iloc[i]["File Name"] for i in selected_row_indices] if selected_row_indices else []

        col_status_info, col_del_action = st.columns([7, 3])
        with col_status_info:
            if selected_files:
                st.caption(f"Selected **{len(selected_files)}** file(s): `{', '.join(selected_files)}`")
            else:
                st.caption("Select rows via checkboxes above to delete.")

        with col_del_action:
            delete_btn_label = f"🗑️ Delete Selected ({len(selected_files)})" if selected_files else "🗑️ Delete Selected"
            if st.button(delete_btn_label, disabled=(len(selected_files) == 0), type="primary", use_container_width=True):
                for f in selected_files:
                    delete_file_and_artifacts(f)
                
                st.session_state.repo_table_nonce += 1
                st.toast(f"Deleted {len(selected_files)} file(s) from storage.")
                time.sleep(0.3)
                st.rerun()

# =============================================================
# PAGE 3: ABOUT PAGE
# =============================================================
elif current_page == PAGE_ABOUT:
    st.markdown('<div class="dashboard-page-title">ℹ️ About Enterprise AI Case Processing Platform</div>', unsafe_allow_html=True)

    col_ab_left, col_ab_right = st.columns([6, 4])

    with col_ab_left:
        st.markdown(
            f"""
            <div style="background:{t_surface}; border:1px solid {t_border}; border-radius:6px; padding:14px 16px;">
                <b style="color:{t_text}; font-size:0.85rem;">Architecture Overview</b>
                <p style="font-size:0.77rem; color:{t_subtext}; line-height:1.45; margin-top:4px;">
                    The platform coordinates batch processing for enterprise customer grievance logs.
                    It supports heterogeneous formats (<b>PDF, Word DOCX, Plain Text</b>), applies schema-bound LLM extraction chains,
                    drafts empathetic customer emails, and prepares internal managerial memos.
                </p>
                <b style="color:{t_text}; font-size:0.80rem;">Pipeline Stages:</b>
                <ol style="font-size:0.75rem; color:{t_subtext}; line-height:1.45; padding-left:14px; margin-top:2px;">
                    <li><b>Document Loader</b>: Extracts raw text bodies and metadata from ingested files.</li>
                    <li><b>Structured Extraction Chain</b>: Binds Pydantic schemas to LLM function calling.</li>
                    <li><b>Response Email Chain</b>: Generates formal customer communications (skipped if data is insufficient).</li>
                    <li><b>Briefing Memo Chain</b>: Prepares root-cause executive summaries.</li>
                </ol>
            </div>
            """,
            unsafe_allow_html=True
        )

    with col_ab_right:
        st.markdown(
            f"""
            <div style="background:{t_surface}; border:1px solid {t_border}; border-radius:6px; padding:14px 16px;">
                <b style="color:{t_text}; font-size:0.85rem;">System Specifications</b>
                <ul style="list-style:none; padding:0; font-size:0.75rem; color:{t_subtext}; line-height:1.5; margin-top:4px;">
                    <li><b>Platform Release:</b> v1.0.0</li>
                    <li><b>Core Framework:</b> Streamlit & Python</li>
                    <li><b>LLM Framework:</b> LangChain Expression Language (LCEL)</li>
                    <li><b>Persistence:</b> Local File Manifests (SHA-256 Hashing)</li>
                    <li><b>Access Guard:</b> Administrative Session Gate</li>
                </ul>
                <hr style="border:none; border-top:1px solid {t_border}; margin:6px 0;">
                <b style="font-size:0.78rem; color:{t_text};">Deterministic Cache Strategy</b>
                <p style="font-size:0.73rem; color:{t_subtext}; margin-top:2px;">
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