import streamlit as st
import pyotp
import time
import datetime
import pandas as pd
import numpy as np
import io
import secrets
import string
from utils.supabase_client import get_supabase

st.set_page_config(page_title="BizReport Pro", page_icon="&#x1F4CA;", layout="wide", initial_sidebar_state="expanded")
st.markdown("""<style>
.stAlert{border-radius:8px}
.summary-table thead tr th{background-color:#f0a500!important;color:white!important;font-weight:bold;}
.rop-col{background-color:#f0a500!important;color:white!important;}
</style>""", unsafe_allow_html=True)

# ── TABLE MAP ─────────────────────────────
# profiles   : id, username, full_name, role, is_approved, is_active, totp_secret, totp_enabled, temp_code, temp_code_exp
# projects   : id, name, code, description, is_active
# permissions: id, user_id, project_id, module, can_view, can_upload, can_download
# uploads    : id, project_id, uploaded_by, filename, original_filename, file_type, file_size, file_url, module, description, created_at
# reports    : id, project_id, generated_by, title, report_type, report_date, summary_data, html_content, file_url, created_at
# ─────────────────────────────────────────

# COMMISSION RATES (JP JW INR & PredictGo VF-INR)
COMMISSION_RATES = {
    "smilepayz":       {"dp": 5.50, "wd": 3.0,   "wd_fixed": 6},
    "apluspay-wake":   {"dp": 5.20, "wd": 3.2,   "wd_fixed": 6},
    "yfrdnqpay-wake":  {"dp": 5.30, "wd": 3.0,   "wd_fixed": 6},
    "paypay-wake":     {"dp": 5.20, "wd": 3.0,   "wd_fixed": 6},
    "apluspay":        {"dp": 4.60, "wd": 3.2,   "wd_fixed": 6},
    "simplypay":       {"dp": 4.80, "wd": 3.0,   "wd_fixed": 6},
    "oxpay":           {"dp": 5.00, "wd": 2.5,   "wd_fixed": 6},
    "okpay":           {"dp": 4.50, "wd": 3.0,   "wd_fixed": 6},
    "paypay":          {"dp": 4.80, "wd": 2.5,   "wd_fixed": 6},
    "expay":           {"dp": 4.50, "wd": 2.5,   "wd_fixed": 6},
    "kingpay":         {"dp": 4.50, "wd": 2.5,   "wd_fixed": 0},
    "vvpay":           {"dp": 4.20, "wd": 2.5,   "wd_fixed": 6},
    "kingpaywd":       {"dp": 0,    "wd": 2.0,   "wd_fixed": 6},
}

def do_login(email, password):
    try:
        sb = get_supabase()
        resp = sb.auth.sign_in_with_password({"email": email, "password": password})
        if not resp.user:
            return None, "Invalid credentials"
        uid = resp.user.id
        profile = sb.table("profiles").select("*").eq("id", uid).single().execute()
        if not profile.data:
            return None, "User profile not found. Contact admin."
        if not profile.data.get("is_approved", False):
            sb.auth.sign_out()
            return None, "Account pending approval. Contact admin."
        p = dict(profile.data)
        p["email"] = resp.user.email
        return p, None
    except Exception as e:
        return None, str(e)

def do_logout():
    try:
        get_supabase().auth.sign_out()
    except Exception:
        pass
    for k in list(st.session_state.keys()):
        del st.session_state[k]

def generate_temp_password(length=12):
    chars = string.ascii_letters + string.digits + "!@#$"
    return "".join(secrets.choice(chars) for _ in range(length))

# LOGIN
def show_login():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("## BizReport Pro")
        st.markdown("**Business Intelligence Platform**")
        st.divider()
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign In", use_container_width=True)
        if submitted:
            if not email or not password:
                st.error("Please enter both email and password.")
            else:
                user, err = do_login(email, password)
                if err:
                    st.error(f"Login failed: {err}")
                elif user:
                    st.session_state.user = user
                    st.session_state.page = "dashboard"
                    st.rerun()

# PROJECT HELPERS
def get_projects():
    try:
        sb = get_supabase()
        user = st.session_state.get("user", {})
        role = user.get("role", "viewer")
        if role == "superadmin":
            res = sb.table("projects").select("*").eq("is_active", True).execute()
            return res.data or []
        uid = user.get("id", "")
        res = sb.table("permissions").select("project_id").eq("user_id", uid).execute()
        proj_ids = list({r["project_id"] for r in (res.data or []) if r.get("project_id")})
        if not proj_ids:
            return []
        projs = sb.table("projects").select("*").in_("id", proj_ids).eq("is_active", True).execute()
        return projs.data or []
    except Exception:
        return []

def project_selector():
    projects = get_projects()
    if not projects:
        st.warning("No projects assigned. Contact admin.")
        return None
    names = [p["name"] for p in projects]
    sel = st.session_state.get("selected_project", projects[0])
    if not isinstance(sel, dict) or sel.get("name") not in names:
        sel = projects[0]
    idx = names.index(sel["name"])
    chosen = st.selectbox("Project", names, index=idx, key="proj_select")
    for p in projects:
        if p["name"] == chosen:
            st.session_state.selected_project = p
            return p
    return projects[0]

# SIDEBAR
def show_sidebar():
    with st.sidebar:
        st.markdown("### BizReport Pro")
        st.divider()
        user = st.session_state.get("user", {})
        role = user.get("role", "viewer")
        name = user.get("username") or user.get("email", "User").split("@")[0]
        st.markdown(f"User: **{name}**")
        st.caption(f"Role: {role.title()}")
        st.divider()
        pages = [
            ("Dashboard", "dashboard"),
            ("Recon", "recon"),
            ("Performance", "performance"),
            ("Analysis", "analysis"),
            ("Health Status", "health"),
            ("Daily Performance", "daily"),
            ("Monthly Report", "monthly"),
            ("Commission", "commission"),
            ("Uploads", "uploads"),
            ("Reports", "reports"),
        ]
        if role in ["superadmin", "admin"]:
            pages.append(("Admin Panel", "admin"))
        for label, key in pages:
            if st.button(label, key=f"nav_{key}", use_container_width=True):
                st.session_state.page = key
                st.rerun()
        st.divider()
        if st.button("Sign Out", use_container_width=True):
            do_logout()
            st.rerun()

# DASHBOARD
def show_dashboard():
    st.markdown("## Dashboard")
    project = project_selector()
    if not project:
        return
    user = st.session_state.user
    name = user.get("full_name") or user.get("username", "User")
    st.markdown(f"### Welcome back, {name}!")
    try:
        sb = get_supabase()
        pid = project["id"]
        uploads = sb.table("uploads").select("id", count="exact").eq("project_id", pid).execute()
        reports = sb.table("reports").select("id", count="exact").eq("project_id", pid).execute()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Uploads", uploads.count or 0)
        c2.metric("Reports", reports.count or 0)
        c3.metric("Transactions", 0)
        c4.metric("Project", project["name"])
        st.divider()
        st.subheader("Recent Uploads")
        recent = sb.table("uploads").select("*").eq("project_id", pid).order("created_at", desc=True).limit(5).execute()
        if recent.data:
            df = pd.DataFrame(recent.data)[["filename", "file_type", "created_at"]]
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No uploads yet for this project.")
    except Exception as e:
        st.error(f"Dashboard error: {e}")

# UPLOADS
def show_uploads():
    st.markdown("## File Uploads")
    project = project_selector()
    if not project:
        return
    st.info(f"Uploading to: {project['name']}")
    uploaded = st.file_uploader("Upload files", type=["csv","xlsx","xls","html","htm","pdf"], accept_multiple_files=True)
    if uploaded:
        sb = get_supabase()
        user = st.session_state.user
        for f in uploaded:
            try:
                content = f.read()
                path = f"{project.get('code','PROJ')}/{user['id']}/{int(time.time())}_{f.name}"
                sb.storage.from_("uploads").upload(path, content, {"content-type": f.type or "application/octet-stream"})
                sb.table("uploads").insert({
                    "project_id": project["id"], "uploaded_by": user["id"],
                    "filename": f.name, "file_type": f.type,
                    "file_url": path, "created_at": datetime.datetime.utcnow().isoformat()
                }).execute()
                st.success(f"Uploaded: {f.name}")
            except Exception as e:
                st.error(f"Error uploading {f.name}: {e}")

# ─────────────────────────────────────────────────────────────
# DAILY PERFORMANCE HELPERS
# ─────────────────────────────────────────────────────────────

def parse_time_to_seconds(t):
    """Convert HH:MM:SS or MM:SS string to total seconds."""
    if pd.isna(t) or t == "-" or t == "":
        return None
    try:
        t = str(t).strip()
        parts = t.split(":")
        if len(parts) == 3:
            return int(parts[0])*3600 + int(parts[1])*60 + int(parts[2])
        elif len(parts) == 2:
            return int(parts[0])*60 + int(parts[1])
    except:
        pass
    return None

def seconds_to_hhmmss(s):
    """Convert seconds to HH:MM:SS string."""
    if s is None or pd.isna(s):
        return "-"
    s = int(s)
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    return f"{h:02d}:{m:02d}:{sec:02d}"

def compute_pt_bucket(seconds):
    """Classify processing time into bucket."""
    if seconds is None:
        return None
    if seconds <= 60: return "le1min"
    elif seconds <= 180: return "1to3min"
    elif seconds <= 300: return "3to5min"
    elif seconds <= 600: return "5to10min"
    elif seconds <= 900: return "10to15min"
    elif seconds <= 1800: return "15to30min"
    elif seconds <= 3600: return "30to60min"
    else: return "gt1hr"

def build_deposit_summary(df):
    """
    Build deposit summary table from raw uploaded CSV/Excel.
    Expected columns (flexible matching):
    Agent Group, DP Count, DP Amount, ROP Count, ROP Amount,
    Processing Time (Auto), Status (success/fail), Created Payment Failed, Failed Payment
    Returns a summary DataFrame.
    """
    if df is None or df.empty:
        return None
    
    df.columns = [str(c).strip() for c in df.columns]
    col_map = {c.lower().replace(" ","_"): c for c in df.columns}
    
    # Try to identify key columns by common names
    def find_col(*candidates):
        for c in candidates:
            k = c.lower().replace(" ","_")
            if k in col_map: return col_map[k]
            # partial match
            for ck, cv in col_map.items():
                if c.lower() in ck: return cv
        return None
    
    agent_col = find_col("agent_group","agent group","agent","team","group")
    count_col = find_col("dp_count","dp count","count","transaction_count")
    amount_col = find_col("dp_amount","dp amount","amount","transaction_amount")
    rop_count_col = find_col("rop_count","rop count","rop count")
    rop_amount_col = find_col("rop_amount","rop amount","rop amount")
    pt_col = find_col("processing_time","processing time","pt","auto_pt","avg_pt")
    status_col = find_col("status","transaction_status")
    fail_amount_col = find_col("fail_amount","failed_amount","fail amount")
    failed_agent_col = find_col("failed_agent","failed agent")
    cpf_col = find_col("create_payment_failed","create payment failed","cpf")
    failed_payment_col = find_col("failed_payment","failed payment")
    
    if agent_col is None:
        return None
    
    summary_rows = []
    groups = df.groupby(agent_col) if agent_col else [(None, df)]
    
    for group_name, grp in groups:
        row = {"Agent Group": group_name}
        
        cnt = grp[count_col].sum() if count_col else len(grp)
        amt = grp[amount_col].sum() if amount_col else 0
        row["DP Count"] = int(cnt)
        row["DP Amount"] = float(amt)
        
        rop_c = grp[rop_count_col].sum() if rop_count_col else 0
        rop_a = grp[rop_amount_col].sum() if rop_amount_col else 0
        row["ROP Count"] = int(rop_c)
        row["ROP Amount"] = float(rop_a)
        
        # Processing time stats
        if pt_col:
            pt_seconds = grp[pt_col].apply(parse_time_to_seconds).dropna()
            if len(pt_seconds) > 0:
                row["Avg PT"] = seconds_to_hhmmss(pt_seconds.mean())
                row["Min PT"] = seconds_to_hhmmss(pt_seconds.min())
                row["Max PT"] = seconds_to_hhmmss(pt_seconds.max())
                # PT distribution buckets
                buckets = pt_seconds.apply(compute_pt_bucket).value_counts()
                row["<=1 Min"] = buckets.get("le1min", 0)
                row["1-3 Mins"] = buckets.get("1to3min", 0)
                row["3-5 Mins"] = buckets.get("3to5min", 0)
                row["5-10 Mins"] = buckets.get("5to10min", 0)
                row["10-15 Mins"] = buckets.get("10to15min", 0)
                row["15-30 Mins"] = buckets.get("15to30min", 0)
                row["30-60 Mins"] = buckets.get("30to60min", 0)
                row[">1 Hr"] = buckets.get("gt1hr", 0)
            else:
                for b in ["Avg PT","Min PT","Max PT","<=1 Min","1-3 Mins","3-5 Mins","5-10 Mins","10-15 Mins","15-30 Mins","30-60 Mins",">1 Hr"]:
                    row[b] = "-"
        
        fail_amt = grp[fail_amount_col].sum() if fail_amount_col else 0
        failed_ag = grp[failed_agent_col].nunique() if failed_agent_col else 0
        cpf_cnt = grp[cpf_col].sum() if cpf_col else 0
        failed_pay = grp[failed_payment_col].sum() if failed_payment_col else 0
        row["Fail Amount"] = float(fail_amt)
        row["Failed Agent"] = int(failed_ag)
        row["Create Payment Failed"] = int(cpf_cnt)
        row["Failed Payment"] = int(failed_pay)
        
        # Success rate
        total_cnt = row["DP Count"]
        fail_cnt = int(failed_pay)
        if total_cnt > 0:
            row["Success Rate"] = f"{((total_cnt - fail_cnt) / total_cnt * 100):.2f}%"
        else:
            row["Success Rate"] = "-"
        
        summary_rows.append(row)
    
    if not summary_rows:
        return None
    
    result = pd.DataFrame(summary_rows)
    
    # Add contribution columns
    total_count = result["DP Count"].sum()
    total_amount = result["DP Amount"].sum()
    if total_count > 0:
        result["Count Contribution%"] = (result["DP Count"] / total_count * 100).apply(lambda x: f"{x:.2f}%")
    if total_amount > 0:
        result["Amount Contribution%"] = (result["DP Amount"] / total_amount * 100).apply(lambda x: f"{x:.2f}%")
    
    return result

def build_withdraw_summary(df):
    """Build withdraw summary table from raw uploaded CSV/Excel."""
    if df is None or df.empty:
        return None
    
    df.columns = [str(c).strip() for c in df.columns]
    col_map = {c.lower().replace(" ","_"): c for c in df.columns}
    
    def find_col(*candidates):
        for c in candidates:
            k = c.lower().replace(" ","_")
            if k in col_map: return col_map[k]
            for ck, cv in col_map.items():
                if c.lower() in ck: return cv
        return None
    
    agent_col = find_col("agent_group","agent group","agent","team","group")
    count_col = find_col("wd_count","wd count","withdraw_count","count","transaction_count")
    amount_col = find_col("wd_amount","wd amount","withdraw_amount","amount","transaction_amount")
    rwd_count_col = find_col("rwd_count","rwd count")
    rwd_amount_col = find_col("rwd_amount","rwd amount")
    pt_col = find_col("processing_time","processing time","pt","auto_pt","avg_pt")
    fail_amount_col = find_col("fail_amount","failed_amount","fail amount")
    failed_payment_col = find_col("failed_payment","failed payment")
    
    if agent_col is None:
        return None
    
    summary_rows = []
    for group_name, grp in df.groupby(agent_col):
        row = {"Agent Group": group_name}
        
        cnt = grp[count_col].sum() if count_col else len(grp)
        amt = grp[amount_col].sum() if amount_col else 0
        row["WD Count"] = int(cnt)
        row["WD Amount"] = float(amt)
        
        rwd_c = grp[rwd_count_col].sum() if rwd_count_col else 0
        rwd_a = grp[rwd_amount_col].sum() if rwd_amount_col else 0
        row["RWD Count"] = int(rwd_c)
        row["RWD Amount"] = float(rwd_a)
        
        if pt_col:
            pt_seconds = grp[pt_col].apply(parse_time_to_seconds).dropna()
            if len(pt_seconds) > 0:
                row["Avg PT"] = seconds_to_hhmmss(pt_seconds.mean())
                row["Min PT"] = seconds_to_hhmmss(pt_seconds.min())
                row["Max PT"] = seconds_to_hhmmss(pt_seconds.max())
                buckets = pt_seconds.apply(compute_pt_bucket).value_counts()
                row["<=1 Min"] = buckets.get("le1min", 0)
                row["1-3 Mins"] = buckets.get("1to3min", 0)
                row["3-5 Mins"] = buckets.get("3to5min", 0)
                row["5-10 Mins"] = buckets.get("5to10min", 0)
                row["10-15 Mins"] = buckets.get("10to15min", 0)
                row["15-30 Mins"] = buckets.get("15to30min", 0)
                row["30-60 Mins"] = buckets.get("30to60min", 0)
                row[">1 Hr"] = buckets.get("gt1hr", 0)
            else:
                for b in ["Avg PT","Min PT","Max PT","<=1 Min","1-3 Mins","3-5 Mins","5-10 Mins","10-15 Mins","15-30 Mins","30-60 Mins",">1 Hr"]:
                    row[b] = "-"
        
        fail_amt = grp[fail_amount_col].sum() if fail_amount_col else 0
        failed_pay = grp[failed_payment_col].sum() if failed_payment_col else 0
        row["Fail Amount"] = float(fail_amt)
        row["Failed Payment"] = int(failed_pay)
        
        total_cnt = row["WD Count"]
        fail_cnt = int(failed_pay)
        if total_cnt > 0:
            row["Success Rate"] = f"{((total_cnt - fail_cnt) / total_cnt * 100):.2f}%"
        else:
            row["Success Rate"] = "-"
        
        summary_rows.append(row)
    
    if not summary_rows:
        return None
    
    result = pd.DataFrame(summary_rows)
    total_count = result["WD Count"].sum()
    total_amount = result["WD Amount"].sum()
    if total_count > 0:
        result["Count Contribution%"] = (result["WD Count"] / total_count * 100).apply(lambda x: f"{x:.2f}%")
    if total_amount > 0:
        result["Amount Contribution%"] = (result["WD Amount"] / total_amount * 100).apply(lambda x: f"{x:.2f}%")
    
    return result

def load_uploaded_file(file_obj):
    """Parse an uploaded file (CSV or Excel) into a DataFrame."""
    try:
        name = file_obj.name.lower()
        if name.endswith(".csv"):
            return pd.read_csv(file_obj)
        elif name.endswith((".xlsx", ".xls")):
            return pd.read_excel(file_obj)
        else:
            return None
    except Exception as e:
        st.error(f"Could not parse file: {e}")
        return None

def display_summary_table(df, title, color="#f0a500"):
    """Display a summary dataframe with professional styling."""
    if df is None or df.empty:
        st.info("No data to display.")
        return
    st.markdown(f"**{title}**")
    # Format numeric columns
    display_df = df.copy()
    for col in display_df.columns:
        if display_df[col].dtype in [float, np.float64]:
            display_df[col] = display_df[col].apply(lambda x: f"{x:,.2f}" if pd.notna(x) else "-")
        elif display_df[col].dtype in [int, np.int64]:
            display_df[col] = display_df[col].apply(lambda x: f"{x:,}" if pd.notna(x) else "-")
    st.dataframe(display_df, use_container_width=True, height=500)

# ─────────────────────────────────────────────────────────────
# DAILY PERFORMANCE
# ─────────────────────────────────────────────────────────────
def show_daily():
    st.markdown("## Daily Performance")
    project = project_selector()
    if not project:
        return
    
    proj_code = project.get("code", "")
    proj_name = project.get("name", "")
    
    # Only show sub-tabs for JP JW INR and PredictGo VF-INR
    if proj_code == "JP_JW_INR":
        dp_label = "JP-JWINR (Deposit)"
        wd_label = "DP-JWINR (Withdraw)"
        dp_title = "JP-JWINR Agent Deposit Data"
        wd_title = "JP-JWINR Agent Withdraw Data"
    elif proj_code == "PREDICTGO_VF_INR":
        dp_label = "PG-VFINR (Deposit)"
        wd_label = "PG-VFINR (Withdraw)"
        dp_title = "PredictGo VF-INR Agent Deposit Data"
        wd_title = "PredictGo VF-INR Agent Withdraw Data"
    else:
        st.info(f"Daily Performance for **{proj_name}** - Upload your data file below.")
        uploaded = st.file_uploader("Upload daily data file (CSV or Excel)", type=["csv","xlsx","xls"])
        if uploaded:
            df = load_uploaded_file(uploaded)
            if df is not None:
                st.dataframe(df, use_container_width=True)
        return
    
    sub_tabs = st.tabs([dp_label, wd_label])
    
    # ── DEPOSIT TAB ──
    with sub_tabs[0]:
        st.markdown(f"### {dp_title}")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            date_from = st.date_input("Date From", value=datetime.date.today().replace(day=1), key="dp_date_from")
            date_to = st.date_input("Date To", value=datetime.date.today(), key="dp_date_to")
        with col2:
            st.markdown("**Upload Deposit File**")
            dp_file = st.file_uploader("Upload CSV/Excel", type=["csv","xlsx","xls"], key="dp_upload")
        
        if dp_file:
            df_raw = load_uploaded_file(dp_file)
            if df_raw is not None:
                st.success(f"File loaded: {len(df_raw)} rows")
                
                # Store in session for commission calculation
                st.session_state["dp_data_raw"] = df_raw
                st.session_state["dp_project"] = proj_code
                
                # Build and display summary
                summary = build_deposit_summary(df_raw)
                if summary is not None:
                    date_str = f"{date_from.strftime('%Y-%m-%d')} - {date_to.strftime('%Y-%m-%d')}"
                    st.markdown(f"**{dp_title} ({date_str})**")
                    
                    # Add totals row
                    numeric_cols = summary.select_dtypes(include=[np.number]).columns
                    total_row = {}
                    for c in summary.columns:
                        if c == "Agent Group":
                            total_row[c] = "Total/Average"
                        elif c in numeric_cols:
                            total_row[c] = summary[c].sum()
                        elif c in ["Avg PT","Min PT","Max PT"]:
                            total_row[c] = "-"
                        elif c.endswith("%"):
                            total_row[c] = "100.00%"
                        elif c == "Success Rate":
                            # Recalculate overall
                            try:
                                total_dp = summary["DP Count"].sum()
                                total_fail = summary["Failed Payment"].sum()
                                total_row[c] = f"{((total_dp - total_fail) / total_dp * 100):.2f}%" if total_dp > 0 else "-"
                            except:
                                total_row[c] = "-"
                        else:
                            total_row[c] = "-"
                    
                    display_df = pd.concat([summary, pd.DataFrame([total_row])], ignore_index=True)
                    display_summary_table(display_df, "")
                    
                    # Download button
                    csv_buf = io.StringIO()
                    display_df.to_csv(csv_buf, index=False)
                    st.download_button("Download Summary CSV", csv_buf.getvalue(), f"deposit_summary_{date_from}.csv", "text/csv")
                else:
                    st.warning("Could not build summary. Please check your file has the required columns (Agent Group, DP Count, DP Amount, etc.)")
                    st.markdown("**Raw Data Preview:**")
                    st.dataframe(df_raw.head(20), use_container_width=True)
        else:
            st.info("Upload a deposit data file (CSV or Excel) to generate the summary table.")
            st.markdown("**Expected columns:** Agent Group, DP Count, DP Amount, ROP Count, ROP Amount, Processing Time, Status, Fail Amount, Failed Payment")
    
    # ── WITHDRAW TAB ──
    with sub_tabs[1]:
        st.markdown(f"### {wd_title}")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            wd_date_from = st.date_input("Date From", value=datetime.date.today().replace(day=1), key="wd_date_from")
            wd_date_to = st.date_input("Date To", value=datetime.date.today(), key="wd_date_to")
        with col2:
            st.markdown("**Upload Withdraw File**")
            wd_file = st.file_uploader("Upload CSV/Excel", type=["csv","xlsx","xls"], key="wd_upload")
        
        if wd_file:
            df_raw_wd = load_uploaded_file(wd_file)
            if df_raw_wd is not None:
                st.success(f"File loaded: {len(df_raw_wd)} rows")
                
                # Store for commission calculation
                st.session_state["wd_data_raw"] = df_raw_wd
                st.session_state["wd_project"] = proj_code
                
                summary_wd = build_withdraw_summary(df_raw_wd)
                if summary_wd is not None:
                    date_str = f"{wd_date_from.strftime('%Y-%m-%d')} - {wd_date_to.strftime('%Y-%m-%d')}"
                    st.markdown(f"**{wd_title} ({date_str})**")
                    
                    numeric_cols = summary_wd.select_dtypes(include=[np.number]).columns
                    total_row = {}
                    for c in summary_wd.columns:
                        if c == "Agent Group":
                            total_row[c] = "Total/Average"
                        elif c in numeric_cols:
                            total_row[c] = summary_wd[c].sum()
                        elif c in ["Avg PT","Min PT","Max PT"]:
                            total_row[c] = "-"
                        elif c.endswith("%"):
                            total_row[c] = "100.00%"
                        elif c == "Success Rate":
                            try:
                                total_wd = summary_wd["WD Count"].sum()
                                total_fail = summary_wd["Failed Payment"].sum()
                                total_row[c] = f"{((total_wd - total_fail) / total_wd * 100):.2f}%" if total_wd > 0 else "-"
                            except:
                                total_row[c] = "-"
                        else:
                            total_row[c] = "-"
                    
                    display_df_wd = pd.concat([summary_wd, pd.DataFrame([total_row])], ignore_index=True)
                    display_summary_table(display_df_wd, "")
                    
                    csv_buf_wd = io.StringIO()
                    display_df_wd.to_csv(csv_buf_wd, index=False)
                    st.download_button("Download Summary CSV", csv_buf_wd.getvalue(), f"withdraw_summary_{wd_date_from}.csv", "text/csv")
                else:
                    st.warning("Could not build summary. Please check your file has the required columns.")
                    st.markdown("**Raw Data Preview:**")
                    st.dataframe(df_raw_wd.head(20), use_container_width=True)
        else:
            st.info("Upload a withdraw data file (CSV or Excel) to generate the summary table.")
            st.markdown("**Expected columns:** Agent Group, WD Count, WD Amount, RWD Count, RWD Amount, Processing Time, Status, Fail Amount, Failed Payment")

# ─────────────────────────────────────────────────────────────
# COMMISSION CALCULATION HELPER
# ─────────────────────────────────────────────────────────────
def compute_commission(dp_summary, wd_summary):
    """
    Compute commission for each agent group.
    DP Commission = DP Amount * dp_rate%
    WD Commission = WD Count * wd_fixed_INR + WD Amount * wd_rate%
    Total = DP Commission + WD Commission
    """
    rows = []
    
    # Get all agent groups from both summaries
    agents = set()
    if dp_summary is not None:
        agents.update(dp_summary["Agent Group"].str.lower().str.strip().tolist())
    if wd_summary is not None:
        agents.update(wd_summary["Agent Group"].str.lower().str.strip().tolist())
    # Remove totals row
    agents = {a for a in agents if "total" not in str(a).lower() and "average" not in str(a).lower()}
    
    for agent in sorted(agents):
        row = {"Agent Group": agent.title()}
        
        # DP data
        dp_count = 0
        dp_amount = 0.0
        if dp_summary is not None:
            mask = dp_summary["Agent Group"].str.lower().str.strip() == agent
            if mask.any():
                dp_row = dp_summary[mask].iloc[0]
                dp_count = int(dp_row.get("DP Count", 0))
                try:
                    dp_amount = float(str(dp_row.get("DP Amount", 0)).replace(",",""))
                except:
                    dp_amount = 0.0
        
        # WD data
        wd_count = 0
        wd_amount = 0.0
        if wd_summary is not None:
            mask_wd = wd_summary["Agent Group"].str.lower().str.strip() == agent
            if mask_wd.any():
                wd_row = wd_summary[mask_wd].iloc[0]
                wd_count = int(wd_row.get("WD Count", 0))
                try:
                    wd_amount = float(str(wd_row.get("WD Amount", 0)).replace(",",""))
                except:
                    wd_amount = 0.0
        
        row["DP Count"] = dp_count
        row["DP Amount"] = dp_amount
        row["WD Count"] = wd_count
        row["WD Amount"] = wd_amount
        
        # Find commission rates
        rates = COMMISSION_RATES.get(agent.lower().strip(), None)
        if rates is None:
            # Try partial match
            for k, v in COMMISSION_RATES.items():
                if k in agent.lower() or agent.lower() in k:
                    rates = v
                    break
        
        if rates:
            dp_rate = rates["dp"]
            wd_rate = rates["wd"]
            wd_fixed = rates.get("wd_fixed", 0)
            
            dp_commission = dp_amount * dp_rate / 100
            wd_commission = (wd_amount * wd_rate / 100) + (wd_count * wd_fixed)
            total_commission = dp_commission + wd_commission
            
            row["DP Rate%"] = f"{dp_rate}%"
            row["WD Rate%"] = f"{wd_rate}% + {wd_fixed} INR/txn" if wd_fixed > 0 else f"{wd_rate}%"
            row["DP Commission (INR)"] = round(dp_commission, 2)
            row["WD Commission (INR)"] = round(wd_commission, 2)
            row["Total Commission (INR)"] = round(total_commission, 2)
        else:
            row["DP Rate%"] = "N/A"
            row["WD Rate%"] = "N/A"
            row["DP Commission (INR)"] = 0.0
            row["WD Commission (INR)"] = 0.0
            row["Total Commission (INR)"] = 0.0
        
        rows.append(row)
    
    if not rows:
        return None
    
    result = pd.DataFrame(rows)
    # Add totals
    total_row = {
        "Agent Group": "TOTAL",
        "DP Count": result["DP Count"].sum(),
        "DP Amount": result["DP Amount"].sum(),
        "WD Count": result["WD Count"].sum(),
        "WD Amount": result["WD Amount"].sum(),
        "DP Rate%": "-",
        "WD Rate%": "-",
        "DP Commission (INR)": result["DP Commission (INR)"].sum(),
        "WD Commission (INR)": result["WD Commission (INR)"].sum(),
        "Total Commission (INR)": result["Total Commission (INR)"].sum(),
    }
    result = pd.concat([result, pd.DataFrame([total_row])], ignore_index=True)
    return result

# ─────────────────────────────────────────────────────────────
# REPORTS MODULE
# ─────────────────────────────────────────────────────────────
def show_reports():
    st.markdown("## Reports")
    project = project_selector()
    if not project:
        return
    
    proj_code = project.get("code", "")
    proj_name = project.get("name", "")
    
    # Only show Commission sub-tab for JP JW INR and PredictGo VF-INR
    if proj_code in ["JP_JW_INR", "PREDICTGO_VF_INR"]:
        report_tabs = st.tabs(["Commission Report Summary", "All Reports"])
        
        with report_tabs[0]:
            st.markdown(f"### Commission Report Summary — {proj_name}")
            st.info("This report computes agent commissions based on Deposit and Withdraw data. Upload both files or use data from the Daily Performance tab.")
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Deposit Data**")
                dp_file_r = st.file_uploader("Upload Deposit CSV/Excel", type=["csv","xlsx","xls"], key="r_dp_upload")
            with col2:
                st.markdown("**Withdraw Data**")
                wd_file_r = st.file_uploader("Upload Withdraw CSV/Excel", type=["csv","xlsx","xls"], key="r_wd_upload")
            
            date_from_r = st.date_input("Period From", value=datetime.date.today().replace(day=1), key="r_date_from")
            date_to_r = st.date_input("Period To", value=datetime.date.today(), key="r_date_to")
            
            if st.button("Generate Commission Report", use_container_width=True, type="primary"):
                dp_raw = None
                wd_raw = None
                
                if dp_file_r:
                    dp_raw = load_uploaded_file(dp_file_r)
                elif st.session_state.get("dp_project") == proj_code:
                    dp_raw = st.session_state.get("dp_data_raw")
                
                if wd_file_r:
                    wd_raw = load_uploaded_file(wd_file_r)
                elif st.session_state.get("wd_project") == proj_code:
                    wd_raw = st.session_state.get("wd_data_raw")
                
                if dp_raw is None and wd_raw is None:
                    st.warning("Please upload at least one file (Deposit or Withdraw data).")
                else:
                    dp_summary = build_deposit_summary(dp_raw) if dp_raw is not None else None
                    wd_summary = build_withdraw_summary(wd_raw) if wd_raw is not None else None
                    
                    commission_df = compute_commission(dp_summary, wd_summary)
                    
                    if commission_df is not None:
                        date_str = f"{date_from_r.strftime('%Y-%m-%d')} to {date_to_r.strftime('%Y-%m-%d')}"
                        st.markdown(f"### Commission Summary — {proj_name} ({date_str})")
                        
                        # Highlight totals row
                        def highlight_totals(row):
                            if row["Agent Group"] == "TOTAL":
                                return ["background-color: #f0a500; color: white; font-weight: bold"] * len(row)
                            return [""] * len(row)
                        
                        # Format numeric columns for display
                        display_comm = commission_df.copy()
                        for c in ["DP Amount", "WD Amount", "DP Commission (INR)", "WD Commission (INR)", "Total Commission (INR)"]:
                            if c in display_comm.columns:
                                display_comm[c] = display_comm[c].apply(lambda x: f"{float(x):,.2f}" if str(x).replace(".","").replace(",","").isdigit() or isinstance(x, (int, float)) else x)
                        
                        st.dataframe(display_comm.style.apply(highlight_totals, axis=1), use_container_width=True)
                        
                        # Commission rates reference
                        st.divider()
                        st.markdown("**Commission Rates Reference:**")
                        rates_data = []
                        for i, (team, r) in enumerate(COMMISSION_RATES.items(), 1):
                            wd_str = f"{r['wd']}% + {r['wd_fixed']} INR" if r['wd_fixed'] > 0 else f"{r['wd']}%"
                            dp_str = f"{r['dp']}%" if r['dp'] > 0 else "-"
                            total_dp = r['dp']
                            total_wd_pct = r['wd']
                            total_str = f"{total_dp + total_wd_pct}% + {r['wd_fixed']} INR" if r['wd_fixed'] > 0 else f"{total_dp + total_wd_pct}%"
                            rates_data.append({"Sn": i, "Team": team.title(), "DP Commission%": dp_str, "WD Commission%": wd_str, "Total Commission": total_str})
                        st.dataframe(pd.DataFrame(rates_data), use_container_width=True)
                        
                        # Download
                        csv_buf_c = io.StringIO()
                        commission_df.to_csv(csv_buf_c, index=False)
                        st.download_button("Download Commission Report CSV", csv_buf_c.getvalue(), f"commission_{proj_code}_{date_from_r}.csv", "text/csv")
                    else:
                        st.error("Could not compute commission. Check that your files have Agent Group column.")
        
        with report_tabs[1]:
            st.subheader("All Reports")
            try:
                sb = get_supabase()
                pid = project["id"]
                reports = sb.table("reports").select("*").eq("project_id", pid).order("created_at", desc=True).execute()
                if reports.data:
                    for r in reports.data:
                        with st.expander(f"{r.get('title','Report')} — {r.get('report_date','')[:10]}"):
                            st.write(f"Type: {r.get('report_type','')} | Created: {r.get('created_at','')[:10]}")
                            if r.get("html_content"):
                                st.download_button("Download HTML", r["html_content"], f"report_{r['id'][:8]}.html", "text/html", key=f"dl_{r['id']}")
                else:
                    st.info("No reports saved yet.")
            except Exception as e:
                st.error(f"Error: {e}")
    else:
        st.info(f"Reports for **{proj_name}** — coming soon.")

# PLACEHOLDERS
def show_recon():
    st.markdown("## Reconciliation"); project_selector(); st.info("Coming soon.")
def show_performance():
    st.markdown("## Performance"); project_selector(); st.info("Coming soon.")
def show_analysis():
    st.markdown("## Analysis"); project_selector(); st.info("Coming soon.")
def show_health():
    st.markdown("## Health Status"); project_selector(); st.info("Coming soon.")
def show_monthly():
    st.markdown("## Monthly Report"); project_selector(); st.info("Coming soon.")
def show_commission():
    st.markdown("## Agent Commission")
    project = project_selector()
    if not project:
        return
    proj_code = project.get("code", "")
    st.info("Commission rates are defined. Use the **Reports** tab > **Commission Report Summary** to generate a full commission report by uploading your Deposit and Withdraw data files.")
    st.markdown("**Current Commission Rates:**")
    rates_data = []
    for i, (team, r) in enumerate(COMMISSION_RATES.items(), 1):
        wd_str = f"{r['wd']}% + {r['wd_fixed']} INR" if r['wd_fixed'] > 0 else f"{r['wd']}%"
        dp_str = f"{r['dp']}%" if r['dp'] > 0 else "-"
        total_str = f"{r['dp'] + r['wd']}% + {r['wd_fixed']} INR" if r['wd_fixed'] > 0 else f"{r['dp'] + r['wd']}%"
        rates_data.append({"#": i, "Team": team.title(), "DP Commission%": dp_str, "WD Commission%": wd_str, "Total Commission": total_str})
    st.dataframe(pd.DataFrame(rates_data), use_container_width=True)

# ADMIN PANEL
def show_admin():
    st.markdown("## Admin Panel")
    user = st.session_state.get("user", {})
    role = user.get("role", "viewer")
    if role not in ["superadmin", "admin"]:
        st.error("Access denied.")
        return
    sb = get_supabase()
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Users", "Add User", "Permissions", "Projects", "Security"])

    with tab1:
        st.subheader("All Users")
        try:
            users = sb.table("profiles").select("*").order("created_at", desc=True).execute().data or []
            if not users:
                st.info("No users found.")
            for u in users:
                status = "Active" if u.get("is_approved") else "Pending"
                with st.expander(f"[{status}] {u.get('username','?')} | {u.get('full_name','?')} | {u.get('role','viewer')}"):
                    uid = u["id"]
                    c1, c2 = st.columns(2)
                    with c1:
                        st.write(f"**Username:** {u.get('username','N/A')}")
                        st.write(f"**Full Name:** {u.get('full_name','N/A')}")
                        st.write(f"**Role:** {u.get('role','viewer')}")
                        st.write(f"**Approved:** {'Yes' if u.get('is_approved') else 'No'}")
                        st.write(f"**2FA:** {'Enabled' if u.get('totp_enabled') else 'Disabled'}")
                    with c2:
                        new_role = st.selectbox("Role", ["viewer","staff","admin","superadmin"],
                            index=["viewer","staff","admin","superadmin"].index(u.get("role","viewer")),
                            key=f"role_{uid}")
                        ca, cb = st.columns(2)
                        with ca:
                            if st.button("Save Role", key=f"sr_{uid}"):
                                sb.table("profiles").update({"role": new_role}).eq("id", uid).execute()
                                st.success("Role updated!"); st.rerun()
                        with cb:
                            if u.get("is_approved"):
                                if st.button("Revoke", key=f"rv_{uid}"):
                                    sb.table("profiles").update({"is_approved": False}).eq("id", uid).execute()
                                    st.success("Revoked."); st.rerun()
                            else:
                                if st.button("Approve", key=f"ap_{uid}"):
                                    sb.table("profiles").update({"is_approved": True}).eq("id", uid).execute()
                                    st.success("Approved!"); st.rerun()
                    st.markdown("**Project Access:**")
                    all_proj = sb.table("projects").select("*").eq("is_active", True).execute().data or []
                    assigned = {p["project_id"] for p in (sb.table("permissions").select("project_id").eq("user_id", uid).execute().data or [])}
                    for proj in all_proj:
                        pid = proj["id"]
                        has = pid in assigned
                        chk = st.checkbox(proj["name"], value=has, key=f"pc_{uid}_{pid}")
                        if chk != has:
                            if chk:
                                sb.table("permissions").insert({"user_id": uid, "project_id": pid, "module": "all", "can_view": True, "can_upload": True, "can_download": True}).execute()
                            else:
                                sb.table("permissions").delete().eq("user_id", uid).eq("project_id", pid).execute()
                            st.success(f"Updated {proj['name']}"); st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

    with tab2:
        st.subheader("Create New User")
        with st.form("add_user_form"):
            nu_email = st.text_input("Email")
            nu_username = st.text_input("Username")
            nu_fullname = st.text_input("Full Name")
            nu_role = st.selectbox("Role", ["viewer","staff","admin"])
            all_p = sb.table("projects").select("*").eq("is_active", True).execute().data or []
            sel_p = st.multiselect("Assign Projects", [p["name"] for p in all_p])
            auto_approve = st.checkbox("Auto-approve user", value=True)
            if st.form_submit_button("Create User", use_container_width=True):
                if not nu_email or not nu_username:
                    st.error("Email and username required.")
                else:
                    tmp_pass = generate_temp_password()
                    try:
                        auth_res = sb.auth.admin.create_user({"email": nu_email, "password": tmp_pass, "email_confirm": True})
                        new_uid = auth_res.user.id
                        sb.table("profiles").insert({"id": new_uid, "username": nu_username, "full_name": nu_fullname or nu_username, "role": nu_role, "is_approved": auto_approve, "is_active": True, "totp_enabled": False}).execute()
                        for pname in sel_p:
                            for p in all_p:
                                if p["name"] == pname:
                                    sb.table("permissions").insert({"user_id": new_uid, "project_id": p["id"], "module": "all", "can_view": True, "can_upload": True, "can_download": True}).execute()
                        st.success(f"User created: {nu_email}")
                        st.info(f"Temp Password: {tmp_pass}")
                        st.warning("Share this password securely. User should change after first login.")
                    except Exception as e:
                        st.error(f"Error: {e}")

    with tab3:
        st.subheader("Edit User Permissions")
        try:
            ulist = sb.table("profiles").select("id, username, full_name, role").execute().data or []
            if ulist:
                u_opts = {f"{u.get('username','?')} - {u.get('full_name','?')}": u["id"] for u in ulist}
                sel_u = st.selectbox("Select User", list(u_opts.keys()))
                target_uid = u_opts[sel_u]
                all_proj = sb.table("projects").select("*").eq("is_active", True).execute().data or []
                user_perms = sb.table("permissions").select("project_id, can_view, can_upload, can_download").eq("user_id", target_uid).execute().data or []
                proj_map = {p["project_id"]: p for p in user_perms}
                changes = {}
                for proj in all_proj:
                    pid = proj["id"]
                    ex = proj_map.get(pid, {})
                    has = pid in proj_map
                    cc1, cc2, cc3, cc4 = st.columns([3,1,1,1])
                    with cc1:
                        access = st.checkbox(proj["name"], value=has, key=f"pa_{target_uid}_{pid}")
                    with cc2:
                        view = st.checkbox("View", value=ex.get("can_view", True), key=f"pv_{target_uid}_{pid}", disabled=not access)
                    with cc3:
                        upload = st.checkbox("Upload", value=ex.get("can_upload", False), key=f"pu_{target_uid}_{pid}", disabled=not access)
                    with cc4:
                        download = st.checkbox("Download", value=ex.get("can_download", False), key=f"pd_{target_uid}_{pid}", disabled=not access)
                    changes[pid] = {"access": access, "view": view, "upload": upload, "download": download}
                if st.button("Save Permissions", use_container_width=True):
                    sb.table("permissions").delete().eq("user_id", target_uid).execute()
                    for pid, ch in changes.items():
                        if ch["access"]:
                            sb.table("permissions").insert({"user_id": target_uid, "project_id": pid, "module": "all", "can_view": ch["view"], "can_upload": ch["upload"], "can_download": ch["download"]}).execute()
                    st.success("Permissions saved!"); st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

    with tab4:
        st.subheader("Projects")
        try:
            projs = sb.table("projects").select("*").order("created_at").execute().data or []
            for p in projs:
                status = "Active" if p.get("is_active") else "Inactive"
                with st.expander(f"[{status}] {p['name']} ({p.get('code','')})"):
                    st.write(f"Description: {p.get('description','')} | Code: {p.get('code','')} | Status: {status}")
                    if p.get("is_active"):
                        if st.button("Deactivate", key=f"dact_{p['id']}"):
                            sb.table("projects").update({"is_active": False}).eq("id", p["id"]).execute(); st.rerun()
                    else:
                        if st.button("Activate", key=f"act_{p['id']}"):
                            sb.table("projects").update({"is_active": True}).eq("id", p["id"]).execute(); st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")
        st.divider()
        st.subheader("Add New Project")
        with st.form("add_proj_form"):
            pn = st.text_input("Project Name")
            pc = st.text_input("Project Code (e.g. NEW_PROJ)")
            pd_desc = st.text_input("Description (optional)")
            if st.form_submit_button("Add Project"):
                if pn and pc:
                    try:
                        sb.table("projects").insert({"name": pn, "code": pc.upper(), "description": pd_desc, "is_active": True}).execute()
                        st.success(f"Added: {pn}"); st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
                else:
                    st.error("Name and code required.")

    with tab5:
        st.subheader("Security Management")
        all_users_raw = sb.table("profiles").select("id, username, full_name, totp_enabled").execute().data or []
        u_sec = {f"{u.get('username','?')} ({u.get('full_name','?')})": u for u in all_users_raw}
        st.markdown("### Reset User Password")
        with st.form("reset_pw_form"):
            sel_pw = st.selectbox("Select User", list(u_sec.keys()), key="rpw_sel")
            new_pw = st.text_input("New Password (blank = auto-generate)", type="password")
            if st.form_submit_button("Reset Password", use_container_width=True):
                target = u_sec[sel_pw]
                use_pw = new_pw.strip() if new_pw.strip() else generate_temp_password()
                try:
                    sb.auth.admin.update_user_by_id(target["id"], {"password": use_pw})
                    st.success(f"Password reset for {target.get('username', target['id'])}")
                    if not new_pw.strip():
                        st.info(f"Temp Password: {use_pw}")
                        st.warning("Share this securely.")
                except Exception as e:
                    st.error(f"Error: {e}")
        st.divider()
        st.markdown("### Reset User 2FA")
        with st.form("reset_2fa_form"):
            sel_2fa = st.selectbox("Select User", list(u_sec.keys()), key="r2fa_sel")
            if st.form_submit_button("Reset 2FA", use_container_width=True):
                target = u_sec[sel_2fa]
                try:
                    sb.table("profiles").update({"totp_secret": None, "totp_enabled": False}).eq("id", target["id"]).execute()
                    st.success(f"2FA reset. User must re-setup on next login.")
                except Exception as e:
                    st.error(f"Error: {e}")
        st.divider()
        st.markdown("### Generate One-Time Code")
        with st.form("otp_form"):
            sel_otp = st.selectbox("Select User", list(u_sec.keys()), key="otp_sel")
            if st.form_submit_button("Generate Code", use_container_width=True):
                target = u_sec[sel_otp]
                otp = "".join(secrets.choice(string.digits) for _ in range(8))
                exp = (datetime.datetime.utcnow() + datetime.timedelta(minutes=15)).isoformat()
                try:
                    sb.table("profiles").update({"temp_code": otp, "temp_code_exp": exp}).eq("id", target["id"]).execute()
                except Exception:
                    pass
                st.info(f"Code: {otp}   (valid 15 min - share securely)")
        st.divider()
        st.markdown("### Change My Password")
        with st.form("my_pw_form"):
            my_pw = st.text_input("New Password", type="password")
            my_pw2 = st.text_input("Confirm", type="password")
            if st.form_submit_button("Update Password", use_container_width=True):
                if not my_pw: st.error("Cannot be empty.")
                elif my_pw != my_pw2: st.error("Passwords do not match.")
                elif len(my_pw) < 8: st.error("Min 8 characters.")
                else:
                    try:
                        sb.auth.admin.update_user_by_id(user["id"], {"password": my_pw})
                        st.success("Password updated!")
                    except Exception as e:
                        st.error(f"Error: {e}")

# ROUTER + MAIN
def show_main_content():
    routes = {
        "dashboard": show_dashboard, "recon": show_recon,
        "performance": show_performance, "analysis": show_analysis,
        "health": show_health, "daily": show_daily,
        "monthly": show_monthly, "commission": show_commission,
        "uploads": show_uploads, "reports": show_reports,
        "admin": show_admin,
    }
    routes.get(st.session_state.get("page", "dashboard"), show_dashboard)()

def main():
    if "user" not in st.session_state:
        show_login()
        return
    if not isinstance(st.session_state.user, dict):
        do_logout(); st.rerun(); return
    show_sidebar()
    show_main_content()

main()
