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

# ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ TABLE MAP ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
# profiles   : id, username, full_name, role, is_approved, is_active, totp_secret, totp_enabled, temp_code, temp_code_exp
# projects   : id, name, code, description, is_active
# permissions: id, user_id, project_id, module, can_view, can_upload, can_download
# uploads    : id, project_id, uploaded_by, filename, original_filename, file_type, file_size, file_url, module, description, created_at
# reports    : id, project_id, generated_by, title, report_type, report_date, summary_data, html_content, file_url, created_at
# ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ

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
                    "filename": f.name, "original_filename": f.name, "file_type": f.type, "file_size": f.size,
                    "file_url": path, "created_at": datetime.datetime.utcnow().isoformat()
                }).execute()
                st.success(f"Uploaded: {f.name}")
            except Exception as e:
                st.error(f"Error uploading {f.name}: {e}")

# ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
# DAILY PERFORMANCE HELPERS
# ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ

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


# Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ
# AGENT REPORT HELPERS (shared by Daily Performance)
# Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ

@st.cache_data(ttl=300)
def load_project_file_app(project_id):
    try:
        sb = get_supabase()
        res = sb.table("uploads").select("file_url,filename,created_at").eq("project_id", project_id).order("created_at", desc=True).limit(1).execute()
        if not res.data:
            return None, "No uploaded file found for this project."
        row = res.data[0]
        file_url = row["file_url"]
        fname = row.get("filename", "file")
        raw = sb.storage.from_("uploads").download(file_url)
        if fname.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(raw), low_memory=False)
        else:
            df = pd.read_excel(io.BytesIO(raw))
        df.columns = [str(c).strip() for c in df.columns]
        return df, None
    except Exception as e:
        return None, str(e)


def _find_col_ar(df, *candidates):
    norm = {c.lower().replace(" ", "_").replace("-", "_"): c for c in df.columns}
    for cand in candidates:
        k = cand.lower().replace(" ", "_").replace("-", "_")
        if k in norm:
            return norm[k]
    return None


def _to_seconds_ar(val):
    if pd.isna(val) or val in ("", "-", "N/A", None):
        return np.nan
    s = str(val).strip()
    try:
        parts = s.split(":")
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        return float(s)
    except:
        return np.nan


def _fmt_hms_ar(sec):
    if pd.isna(sec):
        return "-"
    sec = int(sec)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"0:{m:02d}:{s:02d}"


def _fmt_num_ar(v, dec=0):
    if pd.isna(v) or v == 0:
        return "-"
    if dec == 0:
        return f"{int(v):,}"
    return f"{v:,.{dec}f}"


def _fmt_pct_ar(v):
    if pd.isna(v):
        return "-"
    return f"{v:.2f}%"


def _pt_bucket_ar(sec):
    if pd.isna(sec):
        return None
    if sec <= 60:   return "le1"
    if sec <= 180:  return "1to3"
    if sec <= 300:  return "3to5"
    if sec <= 600:  return "5to10"
    if sec <= 900:  return "10to15"
    if sec <= 1800: return "15to30"
    if sec <= 3600: return "30to60"
    return "gt1hr"


_PT_COLS_AR = ["le1", "1to3", "3to5", "5to10", "10to15", "15to30", "30to60", "gt1hr"]
_PT_LABELS_AR = ["Ã¢ÂÂ¤1 Min", "1-3 Mins", "3-5 Mins", "5-10 Mins", "10-15 Mins", "15-30 Mins", "30-60 Mins", ">1 Hr"]
_AGENTS_ORDER_AR = [
    "apluspay-wake", "expay", "kingpay", "kingpayWD", "okpay", "oxpay",
    "paypay", "paypay-wake", "simplypay", "smilepayz", "vvpay", "yfrdnqpay-wake"
]
_GROUP_MAP_AR = {
    "apluspay-wake": "KS Group", "expay": "KS Group",
    "kingpay": "Ma Group", "kingpayWD": "Ma Group",
    "okpay": "Ma Group", "oxpay": "Ma Group",
    "paypay": "JKPAY Group", "paypay-wake": "JKPAY Group",
    "simplypay": "JKPAY Group", "smilepayz": "JKPAY Group",
    "vvpay": "JKPAY Group", "yfrdnqpay-wake": "JKPAY Group",
}
_GROUPS_AR = ["KS Group", "Ma Group", "JKPAY Group"]
_SUCCESS_VALS_AR = {"success", "successful", "1", "true", "yes", "completed", "approved", "1.0"}


def compute_agent_summary_daily(df, merchant_filter, tx_type_filter):
    d = df.copy()
    col_merchant = _find_col_ar(d, "merchant", "team", "agent_team", "merchant_name", "project", "channel")
    col_type = _find_col_ar(d, "type", "transaction_type", "tx_type", "order_type")
    col_agent = _find_col_ar(d, "agent_group", "agent", "agent_name", "agentgroup", "pay_agent")
    col_amount = _find_col_ar(d, "amount", "dp_amount", "wd_amount", "order_amount", "pay_amount")
    col_status = _find_col_ar(d, "status", "transaction_status", "order_status", "result", "is_success")
    col_pt = _find_col_ar(d, "processing_time", "pt", "auto_pt", "avg_pt", "response_time", "duration")
    col_rdp = _find_col_ar(d, "rdp_count", "rop_count", "rwd_count", "mwd_count", "mdp_count", "manual_count", "is_manual", "is_rdp", "is_rwd")
    col_rdp_amt = _find_col_ar(d, "rdp_amount", "rop_amount", "rwd_amount", "mwd_amount", "mdp_amount", "manual_amount")
    col_fail_amt = _find_col_ar(d, "fail_amount", "failed_amount", "fail amount")
    col_fail_agent = _find_col_ar(d, "failed_agent", "fail_agent")
    col_cpf = _find_col_ar(d, "create_payment_failed", "cpf")
    col_fp = _find_col_ar(d, "failed_payment", "fail_payment")
    if col_merchant and merchant_filter:
        mask_m = d[col_merchant].astype(str).str.upper().isin([m.upper() for m in merchant_filter])
        d = d[mask_m]
    if col_type and tx_type_filter:
        kw = tx_type_filter.lower()
        type_series = d[col_type].astype(str).str.lower().str.strip()
        if kw == "deposit":
            mask_t = (type_series.str.startswith("dep") | (type_series == "d") | type_series.str.contains("^deposit")) & ~type_series.str.contains("revert")
        else:
            mask_t = (type_series.str.startswith("with") | type_series.str.startswith("wd") | (type_series == "w") | type_series.str.contains("^withdraw")) & ~type_series.str.contains("revert")
        d = d[mask_t]
    if d.empty:
        return None, None
    if col_rdp:
        rdp_vals = d[col_rdp].astype(str).str.lower()
        is_manual = rdp_vals.isin(["1", "true", "yes", "rdp", "rwd", "manual", "1.0"])
        if is_manual.sum() == 0:
            is_manual = d[col_rdp].fillna(0).astype(float) > 0
    else:
        is_manual = pd.Series(False, index=d.index)
    if col_pt:
        d["_pt_sec"] = d[col_pt].apply(_to_seconds_ar)
    else:
        d["_pt_sec"] = np.nan
    if col_status:
        d["_success"] = d[col_status].astype(str).str.lower().str.strip().isin(_SUCCESS_VALS_AR)
    else:
        d["_success"] = False
    if not col_agent:
        return None, None
    d["_agent_norm"] = d[col_agent].astype(str).str.strip().str.lower()
    all_count = len(d)
    all_amount = pd.to_numeric(d[col_amount], errors="coerce").sum() if col_amount else 0
    rows = []
    for agent in _AGENTS_ORDER_AR:
        mask = d["_agent_norm"] == agent.lower()
        ag = d[mask]
        ag_auto = ag[~is_manual[mask]]
        ag_manual = ag[is_manual[mask]]
        count = len(ag)
        amount = pd.to_numeric(ag[col_amount], errors="coerce").sum() if col_amount else 0
        rdp_c = int(ag_manual["_agent_norm"].count()) if len(ag_manual) > 0 else 0
        if col_rdp_amt:
            rdp_a = pd.to_numeric(ag_manual[col_rdp_amt], errors="coerce").sum()
        elif col_amount:
            rdp_a = pd.to_numeric(ag_manual[col_amount], errors="coerce").sum()
        else:
            rdp_a = 0
        rdp_a = rdp_a if rdp_c > 0 else 0
        cnt_pct = (count / all_count * 100) if all_count > 0 else 0
        amt_pct = (amount / all_amount * 100) if all_amount > 0 else 0
        auto_pt = ag_auto["_pt_sec"].dropna()
        avg_pt = auto_pt.mean() if len(auto_pt) > 0 else np.nan
        min_pt = auto_pt.min() if len(auto_pt) > 0 else np.nan
        max_pt = auto_pt.max() if len(auto_pt) > 0 else np.nan
        buckets = {b: 0 for b in _PT_COLS_AR}
        for sec in auto_pt:
            b = _pt_bucket_ar(sec)
            if b:
                buckets[b] += 1
        fail_amt = pd.to_numeric(ag[col_fail_amt], errors="coerce").sum() if col_fail_amt else 0
        fail_ag = ag[col_fail_agent].nunique() if col_fail_agent else 0
        cpf = pd.to_numeric(ag[col_cpf], errors="coerce").sum() if col_cpf else 0
        fp = pd.to_numeric(ag[col_fp], errors="coerce").sum() if col_fp else 0
        suc_rate = (ag["_success"].sum() / count * 100) if count > 0 else 0
        rows.append({
            "agent": agent, "count": count, "amount": amount,
            "rdp_c": rdp_c, "rdp_a": rdp_a, "cnt_pct": cnt_pct, "amt_pct": amt_pct,
            "avg_pt": avg_pt, "min_pt": min_pt, "max_pt": max_pt,
            **{f"pt_{b}": buckets[b] for b in _PT_COLS_AR},
            "fail_amt": fail_amt, "fail_ag": int(fail_ag), "cpf": cpf, "fp": fp,
            "suc_rate": suc_rate,
            "auto_count": len(ag_auto),
            "auto_amount": pd.to_numeric(ag_auto[col_amount], errors="coerce").sum() if col_amount else 0,
            "manual_count": len(ag_manual),
            "manual_amount": pd.to_numeric(ag_manual[col_amount], errors="coerce").sum() if col_amount else 0,
        })
    return rows, {
        "all_count": all_count, "all_amount": all_amount,
        "is_manual": is_manual, "d": d,
        "col_amount": col_amount, "col_fail_amt": col_fail_amt,
        "col_fail_agent": col_fail_agent, "col_cpf": col_cpf,
        "col_fp": col_fp, "col_rdp": col_rdp, "col_rdp_amt": col_rdp_amt,
    }


def render_agent_table_daily(rows, totals_info, title, tx_type="deposit"):
    if not rows:
        st.info(f"No data found for {title}")
        return
    is_dp = "deposit" in tx_type.lower()
    rdp_lbl = "RDP" if is_dp else "RWD"
    cnt_lbl = "DP" if is_dp else "WD"
    d = totals_info["d"]
    is_manual = totals_info["is_manual"]
    all_count = totals_info["all_count"]
    all_amount = totals_info["all_amount"]
    col_amount = totals_info["col_amount"]
    col_fail_amt = totals_info["col_fail_amt"]
    col_fail_agent = totals_info["col_fail_agent"]
    col_cpf = totals_info["col_cpf"]
    col_fp = totals_info["col_fp"]
    group_rows = {}
    for grp in _GROUPS_AR:
        members = [a for a, g in _GROUP_MAP_AR.items() if g == grp]
        grp_rows = [r for r in rows if r["agent"] in members]
        if not grp_rows:
            continue
        gc = sum(r["count"] for r in grp_rows)
        ga = sum(r["amount"] for r in grp_rows)
        grc = sum(r["rdp_c"] for r in grp_rows)
        gra = sum(r["rdp_a"] for r in grp_rows)
        g_auto_pt = []
        for ag_name in members:
            mask = d["_agent_norm"] == ag_name.lower()
            auto_mask = mask & ~is_manual
            secs = d[auto_mask]["_pt_sec"].dropna().tolist()
            g_auto_pt.extend(secs)
        group_rows[grp] = {
            "count": gc, "amount": ga, "rdp_c": grc, "rdp_a": gra,
            "cnt_pct": gc / all_count * 100 if all_count else 0,
            "amt_pct": ga / all_amount * 100 if all_amount else 0,
            "avg_pt": np.mean(g_auto_pt) if g_auto_pt else np.nan,
            "min_pt": np.min(g_auto_pt) if g_auto_pt else np.nan,
            "max_pt": np.max(g_auto_pt) if g_auto_pt else np.nan,
            **{f"pt_{b}": sum(r[f"pt_{b}"] for r in grp_rows) for b in _PT_COLS_AR},
            "fail_amt": sum(r["fail_amt"] for r in grp_rows),
            "fail_ag": sum(r["fail_ag"] for r in grp_rows),
            "cpf": sum(r["cpf"] for r in grp_rows),
            "fp": sum(r["fp"] for r in grp_rows),
            "suc_rate": sum(r["suc_rate"] * r["count"] for r in grp_rows) / gc if gc > 0 else 0,
        }
    auto_d = d[~is_manual]
    manual_d = d[is_manual]
    all_auto_pt = d[~is_manual]["_pt_sec"].dropna()
    tot_rdp_c = sum(r["rdp_c"] for r in rows)
    tot_rdp_a = sum(r["rdp_a"] for r in rows)
    tot_fail_amt = pd.to_numeric(d[col_fail_amt], errors="coerce").sum() if col_fail_amt else 0
    tot_fail_ag = d[col_fail_agent].nunique() if col_fail_agent else 0
    tot_cpf = pd.to_numeric(d[col_cpf], errors="coerce").sum() if col_cpf else 0
    tot_fp = pd.to_numeric(d[col_fp], errors="coerce").sum() if col_fp else 0
    tot_suc = d["_success"].sum()
    tot_auto_amt = pd.to_numeric(auto_d[col_amount], errors="coerce").sum() if col_amount else 0
    tot_manual_amt = pd.to_numeric(manual_d[col_amount], errors="coerce").sum() if col_amount else 0

    def make_row(label, c, a, rc, ra, cp, ap, avg, mn, mx, bkts, fa, fag, cpf, fp, sr):
        return {
            "#": "-", "Agent Group": label,
            f"Overall {cnt_lbl} Count": _fmt_num_ar(c),
            f"Overall {cnt_lbl} Amount": _fmt_num_ar(a, 2),
            f"{rdp_lbl} Count": _fmt_num_ar(rc) if rc > 0 else "-",
            f"{rdp_lbl} Amount": _fmt_num_ar(ra, 2) if ra > 0 else "-",
            f"{cnt_lbl} Count Contribution%": _fmt_pct_ar(cp),
            f"{cnt_lbl} Amount Contribution%": _fmt_pct_ar(ap),
            "Avg PT (Auto Only)": _fmt_hms_ar(avg),
            "Min PT (Auto)": _fmt_hms_ar(mn),
            "Max PT (Auto)": _fmt_hms_ar(mx),
            **{_PT_LABELS_AR[i]: _fmt_num_ar(bkts.get(_PT_COLS_AR[i], 0)) for i in range(len(_PT_COLS_AR))},
            "Fail Amount": _fmt_num_ar(fa, 2) if fa else "-",
            "Failed Agent": _fmt_num_ar(fag) if fag else "-",
            "Create Payment Failed": _fmt_num_ar(cpf) if cpf else "-",
            "Failed Payment": _fmt_num_ar(fp) if fp else "-",
            "Success Rate": _fmt_pct_ar(sr),
        }

    all_bkts = {b: sum(r[f"pt_{b}"] for r in rows) for b in _PT_COLS_AR}
    display_rows = []
    row_styles = []
    top = make_row(
        "JP AGENT", all_count, all_amount, tot_rdp_c, tot_rdp_a, 100.0, 100.0,
        all_auto_pt.mean() if len(all_auto_pt) > 0 else np.nan,
        all_auto_pt.min() if len(all_auto_pt) > 0 else np.nan,
        all_auto_pt.max() if len(all_auto_pt) > 0 else np.nan,
        all_bkts, tot_fail_amt, tot_fail_ag, tot_cpf, tot_fp,
        tot_suc / all_count * 100 if all_count > 0 else 0
    )
    display_rows.append(top)
    row_styles.append("top_total")
    for grp in _GROUPS_AR:
        if grp not in group_rows:
            continue
        g = group_rows[grp]
        gr = make_row(
            grp, g["count"], g["amount"], g["rdp_c"], g["rdp_a"],
            g["cnt_pct"], g["amt_pct"], g["avg_pt"], g["min_pt"], g["max_pt"],
            {b: g[f"pt_{b}"] for b in _PT_COLS_AR},
            g["fail_amt"], g["fail_ag"], g["cpf"], g["fp"], g["suc_rate"]
        )
        gr["#"] = str(_GROUPS_AR.index(grp) + 1)
        display_rows.append(gr)
        row_styles.append("group")
        gt = dict(gr)
        gt["Agent Group"] = f"Ã¢ÂÂ³ {grp} Total"
        gt["#"] = str(_GROUPS_AR.index(grp) + 2)
        display_rows.append(gt)
        row_styles.append("group_total")
    acct = {"#": "7", "Agent Group": "Agent_Acct_WD"}
    for k in display_rows[0]:
        if k not in ("#", "Agent Group"):
            acct[k] = "-"
    display_rows.append(acct)
    row_styles.append("normal")
    r_idx = 8
    for r in rows:
        rd = make_row(
            r["agent"], r["count"], r["amount"], r["rdp_c"], r["rdp_a"],
            r["cnt_pct"], r["amt_pct"], r["avg_pt"], r["min_pt"], r["max_pt"],
            {b: r[f"pt_{b}"] for b in _PT_COLS_AR},
            r["fail_amt"], r["fail_ag"], r["cpf"], r["fp"], r["suc_rate"]
        )
        rd["#"] = str(r_idx)
        r_idx += 1
        display_rows.append(rd)
        row_styles.append("normal")
    tot_row = make_row(
        "Total/Average", all_count, all_amount, tot_rdp_c, tot_rdp_a, 100.0, 100.0,
        all_auto_pt.mean() if len(all_auto_pt) > 0 else np.nan,
        all_auto_pt.min() if len(all_auto_pt) > 0 else np.nan,
        all_auto_pt.max() if len(all_auto_pt) > 0 else np.nan,
        all_bkts, tot_fail_amt, tot_fail_ag, tot_cpf, tot_fp,
        tot_suc / all_count * 100 if all_count > 0 else 0
    )
    tot_row["#"] = "-"
    display_rows.append(tot_row)
    row_styles.append("total")
    auto_pct_c = len(auto_d) / all_count * 100 if all_count else 0
    auto_pct_a = tot_auto_amt / all_amount * 100 if all_amount else 0
    auto_row = make_row(
        f"Ã¢ÂÂ¢ Auto (Normal {cnt_lbl})", len(auto_d), tot_auto_amt, 0, 0,
        auto_pct_c, auto_pct_a,
        all_auto_pt.mean() if len(all_auto_pt) > 0 else np.nan,
        all_auto_pt.min() if len(all_auto_pt) > 0 else np.nan,
        all_auto_pt.max() if len(all_auto_pt) > 0 else np.nan,
        all_bkts, np.nan, np.nan, np.nan, np.nan, np.nan
    )
    auto_row["#"] = "L"
    display_rows.append(auto_row)
    row_styles.append("sub")
    man_pct_c = len(manual_d) / all_count * 100 if all_count else 0
    man_pct_a = tot_manual_amt / all_amount * 100 if all_amount else 0
    man_row = make_row(
        f"Ã¢ÂÂ¢ Manual (M{cnt_lbl})", len(manual_d), tot_manual_amt, 0, 0,
        man_pct_c, man_pct_a, np.nan, np.nan, np.nan,
        {b: 0 for b in _PT_COLS_AR}, np.nan, np.nan, np.nan, np.nan,
        100.0 if len(manual_d) == 0 else np.nan
    )
    man_row["#"] = "L"
    man_row["Avg PT (Auto Only)"] = "-"
    man_row["Min PT (Auto)"] = "N/A"
    man_row["Max PT (Auto)"] = "N/A"
    display_rows.append(man_row)
    row_styles.append("sub")
    df_out = pd.DataFrame(display_rows)
    rdp_cols_styled = [f"{rdp_lbl} Count", f"{rdp_lbl} Amount"]

    def style_row(row):
        stype = row_styles[row.name] if row.name < len(row_styles) else "normal"
        base = ""
        if stype == "top_total":
            base = "background-color:#1a1a2e;color:white;font-weight:bold;"
        elif stype == "group":
            base = "background-color:#FFFACD;color:#333;font-weight:bold;"
        elif stype == "group_total":
            base = "background-color:#E8F4FD;color:#333;"
        elif stype == "total":
            base = "background-color:#FFD700;color:#333;font-weight:bold;"
        elif stype == "sub":
            base = "background-color:#2a2a3e;color:#aaa;font-style:italic;"
        styles = [base] * len(row)
        for i, col in enumerate(df_out.columns):
            if col in rdp_cols_styled:
                styles[i] = "background-color:#FF8C00;color:white;font-weight:bold;"
        return styles

    st.markdown(
        f'<div style="background:#E67E22;color:white;font-weight:bold;text-align:center;'
        f'padding:8px;border-radius:4px;margin-bottom:4px;font-size:15px;">{title}</div>',
        unsafe_allow_html=True
    )
    styled = df_out.style.apply(style_row, axis=1)
    st.dataframe(styled, use_container_width=True, hide_index=True)


# Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ
# DAILY PERFORMANCE
# Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ
def show_daily():
    st.markdown("## Daily Performance")
    project = project_selector()
    if not project:
        return

    proj_code = project.get("code", "")
    proj_name = project.get("name", "")
    proj_id = project.get("id", "")

    # Only show sub-tabs for JP JW INR and PredictGo VF-INR
    if proj_code == "JP_JW_INR":
        dp_label = "JP-JWINR (Deposit)"
        wd_label = "DP-JWINR (Withdraw)"
        dp_title = "JP-JWINR Agent Deposit Data"
        wd_title = "JP-JWINR Agent Withdraw Data"
        dp_merchants = ["JP-JWINR", "DP-JWINR"]
        wd_merchants = ["JP-JWINR", "DP-JWINR"]
    elif proj_code == "PREDICTGO_VF_INR":
        dp_label = "PG-VFINR (Deposit)"
        wd_label = "PG-VFINR (Withdraw)"
        dp_title = "PredictGo VF-INR Agent Deposit Data"
        wd_title = "PredictGo VF-INR Agent Withdraw Data"
        dp_merchants = ["VF", "VF-INR", "VFINR"]
        wd_merchants = ["VF", "VF-INR", "VFINR"]
    else:
        st.info(f"Daily Performance for **{proj_name}** - Upload your data file below.")
        uploaded = st.file_uploader("Upload daily data file (CSV or Excel)", type=["csv","xlsx","xls"])
        if uploaded:
            df = load_uploaded_file(uploaded)
            if df is not None:
                st.dataframe(df, use_container_width=True)
        return

    sub_tabs = st.tabs([dp_label, wd_label])

    # Ã¢ÂÂÃ¢ÂÂ DEPOSIT TAB Ã¢ÂÂÃ¢ÂÂ
    with sub_tabs[0]:
        col1, col2 = st.columns([3, 1])
        with col1:
            date_from = st.date_input("Date From", value=datetime.date.today().replace(day=1), key="dp_date_from")
            date_to = st.date_input("Date To", value=datetime.date.today(), key="dp_date_to")
        with col2:
            st.markdown("**Upload Deposit File** *(optional Ã¢ÂÂ auto-loads from Supabase)*")
            dp_file = st.file_uploader("Upload CSV/Excel", type=["csv","xlsx","xls"], key="dp_upload")

        df_dp = None
        if dp_file:
            df_dp = load_uploaded_file(dp_file)
            if df_dp is not None:
                st.success(f"File loaded: {len(df_dp):,} rows ÃÂ {len(df_dp.columns)} columns")
                st.session_state["dp_data_raw"] = df_dp
                st.session_state["dp_project"] = proj_code
        else:
            with st.spinner("Loading data from Supabase..."):
                df_dp, err = load_project_file_app(proj_id)
            if err:
                st.warning(f"Could not auto-load: {err}. Please upload a file manually.")
            elif df_dp is not None and not df_dp.empty:
                st.session_state["dp_data_raw"] = df_dp
                st.session_state["dp_project"] = proj_code

        if df_dp is not None and not df_dp.empty:
            date_col = _find_col_ar(df_dp, "date", "created_at", "transaction_date", "tx_date", "order_date", "create_time")
            date_label = ""
            if date_col:
                try:
                    dates = pd.to_datetime(df_dp[date_col], errors="coerce").dropna()
                    if len(dates) > 0:
                        date_label = f" ( {dates.min().strftime('%Y-%m-%d')} Ã¢ÂÂ {dates.max().strftime('%Y-%m-%d')} )"
                except:
                    pass
            res = compute_agent_summary_daily(df_dp, dp_merchants, "deposit")
            if res and res[0]:
                rows_dp, totals_dp = res
                render_agent_table_daily(rows_dp, totals_dp, f"{dp_title}{date_label}", "deposit")
                csv_buf = io.StringIO()
                pd.DataFrame(rows_dp).to_csv(csv_buf, index=False)
                st.download_button("Download Summary CSV", csv_buf.getvalue(), f"deposit_summary_{date_from}.csv", "text/csv")
            else:
                alt_m = {"JP-JWINR": ["JP-INR", "JPINR", "JP INR", "JP"], "VF": ["VF-INR", "VFINR"]}
                res2 = compute_agent_summary_daily(df_dp, [], "deposit")
                if res2 and res2[0]:
                    rows_dp, totals_dp = res2
                    render_agent_table_daily(rows_dp, totals_dp, f"{dp_title}{date_label}", "deposit")
                else:
                    st.warning(f"No deposit data found. Check your file columns.. Check your file columns.")
                    col_m = _find_col_ar(df_dp, "merchant", "team", "merchant_name", "project")
                    col_t = _find_col_ar(df_dp, "type", "transaction_type", "tx_type")
                    if col_m:
                        st.caption(f"Merchant values found: {list(df_dp[col_m].unique()[:20])}")
                    if col_t:
                        st.caption(f"Type values found: {list(df_dp[col_t].unique()[:20])}")
        else:
            st.info("Upload a deposit data file (CSV or Excel) to generate the summary table.")
            st.markdown("**Expected columns:** Agent Group, DP Count, DP Amount, ROP Count, ROP Amount, Processing Time, Status, Fail Amount, Failed Payment")

    # Ã¢ÂÂÃ¢ÂÂ WITHDRAW TAB Ã¢ÂÂÃ¢ÂÂ
    with sub_tabs[1]:
        col1, col2 = st.columns([3, 1])
        with col1:
            wd_date_from = st.date_input("Date From", value=datetime.date.today().replace(day=1), key="wd_date_from")
            wd_date_to = st.date_input("Date To", value=datetime.date.today(), key="wd_date_to")
        with col2:
            st.markdown("**Upload Withdraw File** *(optional Ã¢ÂÂ auto-loads from Supabase)*")
            wd_file = st.file_uploader("Upload CSV/Excel", type=["csv","xlsx","xls"], key="wd_upload")

        df_wd = None
        if wd_file:
            df_wd = load_uploaded_file(wd_file)
            if df_wd is not None:
                st.success(f"File loaded: {len(df_wd):,} rows ÃÂ {len(df_wd.columns)} columns")
                st.session_state["wd_data_raw"] = df_wd
                st.session_state["wd_project"] = proj_code
        else:
            with st.spinner("Loading data from Supabase..."):
                df_wd, err_wd = load_project_file_app(proj_id)
            if err_wd:
                st.warning(f"Could not auto-load: {err_wd}. Please upload a file manually.")
            elif df_wd is not None and not df_wd.empty:
                st.session_state["wd_data_raw"] = df_wd
                st.session_state["wd_project"] = proj_code

        if df_wd is not None and not df_wd.empty:
            date_col_wd = _find_col_ar(df_wd, "date", "created_at", "transaction_date", "tx_date", "order_date", "create_time")
            date_label_wd = ""
            if date_col_wd:
                try:
                    dates_wd = pd.to_datetime(df_wd[date_col_wd], errors="coerce").dropna()
                    if len(dates_wd) > 0:
                        date_label_wd = f" ( {dates_wd.min().strftime('%Y-%m-%d')} Ã¢ÂÂ {dates_wd.max().strftime('%Y-%m-%d')} )"
                except:
                    pass
            res_wd = compute_agent_summary_daily(df_wd, wd_merchants, "withdraw")
            if res_wd and res_wd[0]:
                rows_wd, totals_wd = res_wd
                render_agent_table_daily(rows_wd, totals_wd, f"{wd_title}{date_label_wd}", "withdraw")
                csv_buf_wd = io.StringIO()
                pd.DataFrame(rows_wd).to_csv(csv_buf_wd, index=False)
                st.download_button("Download Summary CSV", csv_buf_wd.getvalue(), f"withdraw_summary_{wd_date_from}.csv", "text/csv")
            else:
                alt_m_wd = {"JP-JWINR": ["JP-INR", "JPINR", "JP INR", "JP"], "VF": ["VF-INR", "VFINR"]}
                res_wd2 = compute_agent_summary_daily(df_wd, [], "withdraw")
                if res_wd2 and res_wd2[0]:
                    rows_wd, totals_wd = res_wd2
                    render_agent_table_daily(rows_wd, totals_wd, f"{wd_title}{date_label_wd}", "withdraw")
                else:
                    st.warning(f"No withdraw data found. Check your file columns.. Check your file columns.")
                    col_m_wd = _find_col_ar(df_wd, "merchant", "team", "merchant_name", "project")
                    col_t_wd = _find_col_ar(df_wd, "type", "transaction_type", "tx_type")
                    if col_m_wd:
                        st.caption(f"Merchant values: {list(df_wd[col_m_wd].unique()[:20])}")
                    if col_t_wd:
                        st.caption(f"Type values: {list(df_wd[col_t_wd].unique()[:20])}")
        else:
            st.info("Upload a withdraw data file (CSV or Excel) to generate the summary table.")
            st.markdown("**Expected columns:** Agent Group, WD Count, WD Amount, RWD Count, RWD Amount, Processing Time, Status, Fail Amount, Failed Payment")


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
            st.markdown(f"### Commission Report Summary ÃÂ¢ÃÂÃÂ {proj_name}")
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
                        st.markdown(f"### Commission Summary ÃÂ¢ÃÂÃÂ {proj_name} ({date_str})")
                        
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
                        with st.expander(f"{r.get('title','Report')} ÃÂ¢ÃÂÃÂ {r.get('report_date','')[:10]}"):
                            st.write(f"Type: {r.get('report_type','')} | Created: {r.get('created_at','')[:10]}")
                            if r.get("html_content"):
                                st.download_button("Download HTML", r["html_content"], f"report_{r['id'][:8]}.html", "text/html", key=f"dl_{r['id']}")
                else:
                    st.info("No reports saved yet.")
            except Exception as e:
                st.error(f"Error: {e}")
    else:
        st.info(f"Reports for **{proj_name}** ÃÂ¢ÃÂÃÂ coming soon.")

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
