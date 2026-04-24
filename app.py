import streamlit as st
import pyotp
import time
import datetime
import pandas as pd
import plotly.express as px
from utils.supabase_client import get_supabase
from utils.auth import login_user, logout_user, get_user_profile, verify_totp

st.set_page_config(page_title="BizReport Pro", page_icon="📊", layout="wide", initial_sidebar_state="expanded")

st.markdown("""<style>.stAlert{border-radius:8px}</style>""", unsafe_allow_html=True)

def show_login():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("## 📊 BizReport Pro")
        st.markdown("**Business Intelligence Platform**")
        st.divider()
        with st.form("login_form"):
            email = st.text_input("📧 Email")
            password = st.text_input("🔒 Password", type="password")
            submitted = st.form_submit_button("Sign In", use_container_width=True)
        if submitted:
            if not email or not password:
                st.error("Please enter both email and password.")
                return
            with st.spinner("Signing in..."):
                user, error = login_user(email, password)
            if error:
                st.error(f"Login failed: {error}")
                return
            if user is None:
                st.error("Invalid credentials.")
                return
            profile = get_user_profile(user.id)
            if not profile:
                st.error("Profile not found. Contact administrator.")
                return
            if not profile.get("is_approved", False):
                st.error("Account pending approval.")
                return
            if profile.get("totp_enabled") and profile.get("totp_secret"):
                st.session_state.update({"pending_2fa_user": user, "pending_2fa_profile": profile, "show_2fa": True})
                st.rerun()
            else:
                st.session_state.update({"user": user, "profile": profile, "logged_in": True})
                st.rerun()

def show_2fa():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("## 🔐 Two-Factor Authentication")
        with st.form("totp_form"):
            code = st.text_input("Verification Code", max_chars=8)
            submitted = st.form_submit_button("Verify", use_container_width=True)
        if submitted and code:
            profile = st.session_state.get("pending_2fa_profile", {})
            user = st.session_state.get("pending_2fa_user")
            totp_valid = verify_totp(profile.get("totp_secret", ""), code)
            temp_valid = False
            if profile.get("temp_code") and profile.get("temp_code_exp"):
                try:
                    now = datetime.datetime.now(datetime.timezone.utc)
                    exp = datetime.datetime.fromisoformat(str(profile.get("temp_code_exp", "")).replace("Z", "+00:00"))
                    if code == profile.get("temp_code") and now < exp:
                        temp_valid = True
                        get_supabase().table("profiles").update({"temp_code": None, "temp_code_exp": None}).eq("id", user.id).execute()
                except Exception:
                    pass
            if totp_valid or temp_valid:
                st.session_state.update({"user": user, "profile": profile, "logged_in": True})
                for k in ["pending_2fa_user", "pending_2fa_profile", "show_2fa"]:
                    st.session_state.pop(k, None)
                st.rerun()
            else:
                st.error("Invalid code.")
        if st.button("← Back to Login"):
            for k in ["pending_2fa_user", "pending_2fa_profile", "show_2fa"]:
                st.session_state.pop(k, None)
            st.rerun()

def show_sidebar():
    profile = st.session_state.get("profile", {})
    role = profile.get("role", "viewer")
    full_name = profile.get("full_name") or profile.get("username") or "User"
    with st.sidebar:
        st.markdown(f"### 👤 {full_name}")
        st.caption(f"Role: **{role.upper()}**")
        st.divider()
        st.markdown("### 📊 Navigation")
        pages = {"🏠 Dashboard":"dashboard","🔍 Recon":"recon","📈 Performance":"performance","📉 Analysis":"analysis","💚 Health":"health","📅 Daily":"daily","📆 Monthly":"monthly","💰 Commission":"commission","📁 Uploads":"uploads","📋 Reports":"reports"}
        if role in ["superadmin","admin"]:
            pages["⚙️ Admin"]="admin"
        for label, key in pages.items():
            if st.sidebar.button(label, key=f"nav_{key}", use_container_width=True):
                st.session_state["current_page"] = key
                st.rerun()
        st.divider()
        if st.sidebar.button("🚪 Logout", use_container_width=True):
            logout_user()
            st.rerun()

def get_projects():
    try:
        return get_supabase().table("projects").select("*").execute().data or []
    except Exception:
        return []

def project_selector():
    projects = get_projects()
    if not projects:
        st.info("No projects found.")
        return None
    names = [p["name"] for p in projects]
    sel = st.selectbox("📁 Select Project", names)
    return next((p for p in projects if p["name"] == sel), None)

def show_dashboard():
    st.title("🏠 Dashboard")
    profile = st.session_state.get("profile", {})
    full_name = profile.get("full_name") or profile.get("username") or "User"
    st.markdown(f"Welcome back, **{full_name}**!")
    st.divider()
    project = project_selector()
    if not project:
        return
    st.divider()
    col1, col2, col3, col4 = st.columns(4)
    try:
        s = get_supabase()
        nu = len(s.table("uploads").select("id").eq("project_id", project["id"]).execute().data or [])
        nr = len(s.table("reports").select("id").eq("project_id", project["id"]).execute().data or [])
        nt = len(s.table("transactions").select("id").eq("project_id", project["id"]).execute().data or [])
    except Exception:
        nu = nr = nt = 0
    with col1: st.metric("📁 Uploads", nu)
    with col2: st.metric("📋 Reports", nr)
    with col3: st.metric("💳 Transactions", nt)
    with col4: st.metric("📊 Project", project["name"], delta="Active")
    st.divider()
    st.info("Use the left menu to navigate modules.")
    try:
        recent = get_supabase().table("uploads").select("*").eq("project_id", project["id"]).order("created_at", desc=True).limit(5).execute()
        if recent.data:
            df = pd.DataFrame(recent.data)
            cols = [c for c in ["filename","file_type","uploaded_by","created_at"] if c in df.columns]
            if cols:
                st.markdown("### 🕐 Recent Uploads")
                st.dataframe(df[cols], use_container_width=True)
    except Exception:
        pass

def show_recon():
    st.title("🔍 Reconciliation")
    project = project_selector()
    if not project: return
    st.divider()
    st.info("View uploaded reconciliation files for the selected project.")
    try:
        res = get_supabase().table("uploads").select("*").eq("project_id", project["id"]).order("created_at", desc=True).execute()
        if res.data:
            df = pd.DataFrame(res.data)
            cols = [c for c in ["filename","file_type","uploaded_by","created_at"] if c in df.columns]
            st.dataframe(df[cols], use_container_width=True)
        else:
            st.info("No files uploaded yet.")
    except Exception as e:
        st.warning(f"Error: {str(e)}")

def show_performance():
    st.title("📈 Performance")
    project = project_selector()
    if not project: return
    st.divider()
    try:
        res = get_supabase().table("transactions").select("*").eq("project_id", project["id"]).order("created_at", desc=True).limit(100).execute()
        if res.data:
            df = pd.DataFrame(res.data)
            st.dataframe(df, use_container_width=True)
            if "amount" in df.columns and "created_at" in df.columns:
                df["created_at"] = pd.to_datetime(df["created_at"])
                st.plotly_chart(px.line(df, x="created_at", y="amount", title="Transactions Over Time"), use_container_width=True)
        else:
            st.info("No transaction data available.")
    except Exception as e:
        st.warning(f"Error: {str(e)}")

def show_analysis():
    st.title("📉 Analysis")
    project = project_selector()
    if not project: return
    st.divider()
    try:
        res = get_supabase().table("transactions").select("*").eq("project_id", project["id"]).execute()
        if res.data:
            df = pd.DataFrame(res.data)
            st.dataframe(df, use_container_width=True)
            if "amount" in df.columns:
                c1,c2,c3=st.columns(3)
                with c1: st.metric("Total", f"{df['amount'].sum():,.2f}")
                with c2: st.metric("Average", f"{df['amount'].mean():,.2f}")
                with c3: st.metric("Count", len(df))
        else:
            st.info("No data available.")
    except Exception as e:
        st.warning(f"Error: {str(e)}")

def show_health():
    st.title("💚 Health Status")
    project = project_selector()
    if not project: return
    st.divider()
    c1,c2,c3=st.columns(3)
    with c1:
        try: get_supabase().table("projects").select("id").limit(1).execute(); st.success("✅ DB: Connected")
        except: st.error("❌ DB: Error")
    with c2: st.success("✅ App: Running")
    with c3: st.info(f"🕐 {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    try:
        s=get_supabase()
        st.metric("Uploads", len(s.table("uploads").select("id").eq("project_id",project["id"]).execute().data or []))
        st.metric("Reports", len(s.table("reports").select("id").eq("project_id",project["id"]).execute().data or []))
    except Exception as e:
        st.warning(str(e))

def show_daily():
    st.title("📅 Daily Report")
    project = project_selector()
    if not project: return
    st.divider()
    d = st.date_input("Select Date", value=datetime.date.today())
    try:
        s=datetime.datetime.combine(d, datetime.time.min).isoformat()
        e=datetime.datetime.combine(d, datetime.time.max).isoformat()
        res = get_supabase().table("transactions").select("*").eq("project_id", project["id"]).gte("created_at", s).lte("created_at", e).execute()
        if res.data:
            df=pd.DataFrame(res.data)
            st.dataframe(df, use_container_width=True)
            if "amount" in df.columns: st.metric("Daily Total", f"{df['amount'].sum():,.2f}")
        else: st.info(f"No data for {d}.")
    except Exception as ex:
        st.warning(f"Error: {str(ex)}")

def show_monthly():
    st.title("📆 Monthly Report")
    project = project_selector()
    if not project: return
    st.divider()
    c1,c2=st.columns(2)
    with c1: year = st.number_input("Year", min_value=2020, max_value=2030, value=datetime.date.today().year)
    with c2: month = st.selectbox("Month", list(range(1,13)), index=datetime.date.today().month-1)
    try:
        s=f"{year}-{month:02d}-01"
        e=f"{year+1}-01-01" if month==12 else f"{year}-{month+1:02d}-01"
        res = get_supabase().table("transactions").select("*").eq("project_id", project["id"]).gte("created_at", s).lt("created_at", e).execute()
        if res.data:
            df=pd.DataFrame(res.data)
            st.dataframe(df, use_container_width=True)
            if "amount" in df.columns:
                c1,c2=st.columns(2)
                with c1: st.metric("Total", f"{df['amount'].sum():,.2f}")
                with c2: st.metric("Count", len(df))
        else: st.info(f"No data for {year}/{month:02d}.")
    except Exception as ex:
        st.warning(f"Error: {str(ex)}")

def show_commission():
    st.title("💰 Agent Commission")
    project = project_selector()
    if not project: return
    st.divider()
    try:
        res = get_supabase().table("transactions").select("*").eq("project_id", project["id"]).execute()
        if res.data:
            df=pd.DataFrame(res.data)
            if "agent" in df.columns and "amount" in df.columns:
                rate = st.slider("Commission Rate (%)", 1, 20, 5) / 100
                cdf = df.groupby("agent")["amount"].sum().reset_index()
                cdf["commission"] = cdf["amount"] * rate
                cdf.columns = ["Agent","Total","Commission"]
                st.dataframe(cdf, use_container_width=True)
                st.metric("Total Commission", f"{cdf['Commission'].sum():,.2f}")
            else:
                st.dataframe(df, use_container_width=True)
                st.info("Need 'agent' and 'amount' columns for commission calc.")
        else: st.info("No transaction data.")
    except Exception as ex:
        st.warning(f"Error: {str(ex)}")

def show_uploads():
    st.title("📁 File Uploads")
    project = project_selector()
    if not project: return
    st.divider()
    st.markdown("### 📤 Upload File")
    uf = st.file_uploader("Choose file (CSV, Excel, HTML, PDF)", type=["csv","xlsx","xls","html","htm","pdf"])
    if uf:
        st.info(f"📄 {uf.name} ({uf.size:,} bytes)")
        if st.button("✅ Confirm Upload", type="primary"):
            try:
                profile = st.session_state.get("profile", {})
                ft = uf.name.split(".")[-1].lower()
                content = uf.read()
                get_supabase().table("uploads").insert({
                    "project_id": project["id"],
                    "filename": uf.name,
                    "file_type": ft,
                    "file_size": uf.size,
                    "uploaded_by": profile.get("full_name") or profile.get("username") or "Unknown",
                    "file_data": content.decode("utf-8", errors="replace") if ft in ["csv","html","htm"] else f"[Binary: {uf.name}]"
                }).execute()
                st.success(f"✅ Uploaded: {uf.name}")
                st.rerun()
            except Exception as ex:
                st.error(f"Upload failed: {str(ex)}")
    st.divider()
    st.markdown("### 📂 Uploaded Files")
    try:
        res = get_supabase().table("uploads").select("*").eq("project_id", project["id"]).order("created_at", desc=True).execute()
        if res.data:
            df=pd.DataFrame(res.data)
            cols=[c for c in ["filename","file_type","file_size","uploaded_by","created_at"] if c in df.columns]
            st.dataframe(df[cols], use_container_width=True)
        else: st.info("No files uploaded yet.")
    except Exception as ex:
        st.warning(f"Error: {str(ex)}")

def show_reports():
    st.title("📋 Reports")
    project = project_selector()
    if not project: return
    st.divider()
    rtype = st.selectbox("Report Type", ["Summary","Transaction Detail","Upload Log"])
    if st.button("🔄 Generate Report"):
        try:
            profile = st.session_state.get("profile",{})
            s=get_supabase()
            nu=len(s.table("uploads").select("id").eq("project_id",project["id"]).execute().data or [])
            nt=len(s.table("transactions").select("*").eq("project_id",project["id"]).execute().data or [])
            html=f"""<!DOCTYPE html><html><head><title>{rtype} - {project["name"]}</title>
<style>body{{font-family:Arial;padding:20px}}h1{{color:#1f77b4}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ddd;padding:8px}}</style>
</head><body><h1>📊 {rtype} — {project["name"]}</h1>
<p>Generated: {datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")} by {profile.get("full_name","Unknown")}</p>
<table><tr><th>Metric</th><th>Value</th></tr><tr><td>Uploads</td><td>{nu}</td></tr><tr><td>Transactions</td><td>{nt}</td></tr></table>
</body></html>"""
            s.table("reports").insert({"project_id":project["id"],"report_type":rtype,"generated_by":profile.get("full_name","Unknown"),"content":html}).execute()
            st.success("✅ Report generated!")
            st.download_button("⬇️ Download HTML", html.encode(), f"report_{datetime.date.today()}.html", "text/html")
        except Exception as ex:
            st.error(f"Error: {str(ex)}")
    st.divider()
    st.markdown("### 📂 Previous Reports")
    try:
        res=get_supabase().table("reports").select("*").eq("project_id",project["id"]).order("created_at",desc=True).execute()
        if res.data:
            df=pd.DataFrame(res.data)
            cols=[c for c in ["report_type","generated_by","created_at"] if c in df.columns]
            st.dataframe(df[cols], use_container_width=True)
        else: st.info("No reports yet.")
    except Exception as ex:
        st.warning(f"Error: {str(ex)}")

def show_admin():
    st.title("⚙️ Admin Panel")
    profile=st.session_state.get("profile",{})
    role=profile.get("role","viewer")
    if role not in ["superadmin","admin"]:
        st.error("Access denied.")
        return
    tab1,tab2,tab3,tab4=st.tabs(["👥 Users","🔑 Permissions","📁 Projects","🔐 2FA"])
    with tab1:
        st.markdown("### 👥 Users")
        try:
            s=get_supabase()
            res=s.table("profiles").select("*").execute()
            if res.data:
                df=pd.DataFrame(res.data)
                cols=[c for c in ["username","full_name","role","is_approved","totp_enabled"] if c in df.columns]
                st.dataframe(df[cols], use_container_width=True)
                ul=[f"{u.get('full_name',u.get('username','?'))} ({u.get('id','')[:8]})" for u in res.data]
                sel=st.selectbox("Select User",ul)
                idx=ul.index(sel)
                u=res.data[idx]
                nr=st.selectbox("Role",["viewer","staff","admin","superadmin"],index=["viewer","staff","admin","superadmin"].index(u.get("role","viewer")))
                ap=st.checkbox("Approved",value=u.get("is_approved",False))
                if st.button("💾 Update"):
                    s.table("profiles").update({"role":nr,"is_approved":ap}).eq("id",u["id"]).execute()
                    st.success("Updated!")
                    st.rerun()
        except Exception as ex: st.error(str(ex))
    with tab2:
        st.info("Roles: superadmin > admin > staff > viewer")
        st.markdown("""| Role | Uploads | Admin |
|------|---------|-------|
| Viewer | ❌ | ❌ |
| Staff | ✅ | ❌ |
| Admin | ✅ | ✅ |
| Superadmin | ✅ | ✅ |""")
    with tab3:
        st.markdown("### 📁 Projects")
        try:
            s=get_supabase()
            res=s.table("projects").select("*").execute()
            if res.data:
                df=pd.DataFrame(res.data)
                cols=[c for c in ["name","code","description","is_active"] if c in df.columns]
                st.dataframe(df[cols], use_container_width=True)
            if role=="superadmin":
                with st.form("add_proj"):
                    n=st.text_input("Name"); c=st.text_input("Code"); d=st.text_area("Description")
                    if st.form_submit_button("Add"):
                        if n and c:
                            s.table("projects").insert({"name":n,"code":c,"description":d,"is_active":True}).execute()
                            st.success(f"Added: {n}"); st.rerun()
        except Exception as ex: st.error(str(ex))
    with tab4:
        st.markdown("### 🔐 One-Time 2FA Code")
        try:
            s=get_supabase()
            res=s.table("profiles").select("*").execute()
            if res.data:
                ul=[f"{u.get('full_name',u.get('username','?'))} ({u.get('id','')[:8]})" for u in res.data]
                sel=st.selectbox("User",ul,key="2fa_sel")
                tu=res.data[ul.index(sel)]
                if st.button("🔑 Generate"):
                    import secrets
                    code=str(secrets.randbelow(1000000)).zfill(6)
                    exp=(datetime.datetime.utcnow()+datetime.timedelta(minutes=30)).isoformat()
                    s.table("profiles").update({"temp_code":code,"temp_code_exp":exp}).eq("id",tu["id"]).execute()
                    st.success(f"Code: **{code}** (30 min)")
        except Exception as ex: st.error(str(ex))

def show_main_content():
    page=st.session_state.get("current_page","dashboard")
    role=st.session_state.get("profile",{}).get("role","viewer")
    try:
        if page=="dashboard": show_dashboard()
        elif page=="recon": show_recon()
        elif page=="performance": show_performance()
        elif page=="analysis": show_analysis()
        elif page=="health": show_health()
        elif page=="daily": show_daily()
        elif page=="monthly": show_monthly()
        elif page=="commission": show_commission()
        elif page=="uploads": show_uploads()
        elif page=="reports": show_reports()
        elif page=="admin" and role in ["superadmin","admin"]: show_admin()
        else: st.warning("Page not found or access denied.")
    except Exception as e:
        st.error(f"Error: {str(e)}")
        st.exception(e)

def main():
    if "logged_in" not in st.session_state: st.session_state["logged_in"]=False
    if "current_page" not in st.session_state: st.session_state["current_page"]="dashboard"
    if st.session_state.get("show_2fa"): show_2fa()
    elif not st.session_state.get("logged_in"): show_login()
    else: show_sidebar(); show_main_content()

if __name__=="__main__": main()
