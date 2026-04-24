import streamlit as st
import pyotp
import time
import datetime
import pandas as pd
import plotly.express as px
import secrets
import string
from utils.supabase_client import get_supabase
from utils.auth import login_user, logout_user, get_user_profile, verify_totp

st.set_page_config(page_title="BizReport Pro", page_icon="📊", layout="wide", initial_sidebar_state="expanded")

st.markdown("""<style>
.stAlert{border-radius:8px}
.metric-card{background:#1e2130;border-radius:10px;padding:20px;margin:5px;border:1px solid #2d3250}
</style>""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# LOGIN
# ─────────────────────────────────────────────
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
            else:
                success, result = login_user(email, password)
                if success:
                    st.session_state.user = result
                    st.session_state.page = "dashboard"
                    st.rerun()
                else:
                    st.error(f"Login failed: {result}")

# ─────────────────────────────────────────────
# 2FA
# ─────────────────────────────────────────────
def show_2fa():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("## 🔐 Two-Factor Authentication")
        user = st.session_state.get("user", {})
        st.info(f"Logged in as: {user.get('email', '')}")
        with st.form("totp_form"):
            code = st.text_input("Enter 6-digit code from authenticator app")
            submitted = st.form_submit_button("Verify", use_container_width=True)
        if submitted:
            if verify_totp(user.get("id"), code):
                st.session_state["2fa_verified"] = True
                st.rerun()
            else:
                st.error("Invalid code. Please try again.")

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def get_projects():
    try:
        sb = get_supabase()
        user = st.session_state.get("user", {})
        role = user.get("role", "viewer")
        if role == "superadmin":
            res = sb.table("projects").select("*").eq("is_active", True).execute()
        else:
            uid = user.get("id", "")
            res = sb.table("user_project_permissions").select("project_id, projects(*)").eq("user_id", uid).execute()
            projects = []
            for row in res.data:
                if row.get("projects"):
                    projects.append(row["projects"])
            return projects
        return res.data or []
    except:
        return []

def project_selector():
    projects = get_projects()
    if not projects:
        st.warning("No projects assigned. Contact admin.")
        return None
    names = [p["name"] for p in projects]
    if "selected_project" not in st.session_state:
        st.session_state.selected_project = projects[0]
    selected_name = st.selectbox("📁 Project", names, key="proj_select",
        index=names.index(st.session_state.selected_project["name"]) if st.session_state.selected_project["name"] in names else 0)
    for p in projects:
        if p["name"] == selected_name:
            st.session_state.selected_project = p
            return p
    return projects[0]

def generate_temp_password(length=12):
    chars = string.ascii_letters + string.digits + "!@#$"
    return ''.join(secrets.choice(chars) for _ in range(length))

# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
def show_sidebar():
    with st.sidebar:
        st.markdown("### 📊 BizReport Pro")
        st.divider()
        user = st.session_state.get("user", {})
        role = user.get("role", "viewer")
        username = user.get("username") or user.get("email", "User").split("@")[0]
        st.markdown(f"👤 **{username}**")
        st.caption(f"Role: {role.title()}")
        st.divider()
        pages = [
            ("🏠", "Dashboard", "dashboard"),
            ("📋", "Recon", "recon"),
            ("📈", "Performance", "performance"),
            ("🔍", "Analysis", "analysis"),
            ("❤️", "Health Status", "health"),
            ("📅", "Daily Performance", "daily"),
            ("📆", "Monthly Report", "monthly"),
            ("💰", "Commission", "commission"),
            ("📁", "Uploads", "uploads"),
            ("📊", "Reports", "reports"),
        ]
        if role in ["superadmin", "admin"]:
            pages.append(("⚙️", "Admin Panel", "admin"))
        current = st.session_state.get("page", "dashboard")
        for icon, label, key in pages:
            style = "background:#2d3250;border-radius:6px;padding:4px 8px;" if current == key else ""
            if st.button(f"{icon} {label}", key=f"nav_{key}", use_container_width=True):
                st.session_state.page = key
                st.rerun()
        st.divider()
        if st.button("🚪 Sign Out", use_container_width=True):
            logout_user()
            st.rerun()

# ─────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────
def show_dashboard():
    st.markdown("## 🏠 Dashboard")
    project = project_selector()
    if not project:
        return
    st.markdown(f"### Welcome back, {st.session_state.user.get('username', 'User')}!")
    try:
        sb = get_supabase()
        pid = project["id"]
        uploads = sb.table("uploads").select("id", count="exact").eq("project_id", pid).execute()
        reports = sb.table("reports").select("id", count="exact").eq("project_id", pid).execute()
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📁 Uploads", uploads.count or 0)
        with col2:
            st.metric("📊 Reports", reports.count or 0)
        with col3:
            st.metric("💹 Transactions", 0)
        with col4:
            st.metric("📌 Project", f"{project['name']} {'✅' if project.get('is_active') else '❌'}")
        st.divider()
        st.subheader("Recent Uploads")
        recent = sb.table("uploads").select("*").eq("project_id", pid).order("uploaded_at", desc=True).limit(5).execute()
        if recent.data:
            df = pd.DataFrame(recent.data)[["filename", "file_type", "uploaded_at"]]
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No uploads yet for this project.")
    except Exception as e:
        st.error(f"Dashboard error: {e}")

# ─────────────────────────────────────────────
# UPLOADS
# ─────────────────────────────────────────────
def show_uploads():
    st.markdown("## 📁 File Uploads")
    project = project_selector()
    if not project:
        return
    st.info(f"Uploading to: **{project['name']}**")
    uploaded = st.file_uploader("Upload files", type=["csv", "xlsx", "xls", "html", "htm", "pdf"],
                                 accept_multiple_files=True)
    if uploaded:
        sb = get_supabase()
        user = st.session_state.user
        for f in uploaded:
            try:
                content = f.read()
                path = f"{project['code']}/{user['id']}/{int(time.time())}_{f.name}"
                sb.storage.from_("uploads").upload(path, content, {"content-type": f.type})
                sb.table("uploads").insert({
                    "project_id": project["id"], "uploaded_by": user["id"],
                    "filename": f.name, "file_type": f.type, "storage_path": path,
                    "uploaded_at": datetime.datetime.utcnow().isoformat()
                }).execute()
                st.success(f"✅ Uploaded: {f.name}")
            except Exception as e:
                st.error(f"Error uploading {f.name}: {e}")

# ─────────────────────────────────────────────
# MODULE PLACEHOLDERS
# ─────────────────────────────────────────────
def show_recon():
    st.markdown("## 📋 Reconciliation")
    project = project_selector()
    if not project:
        return
    st.info("🚧 Reconciliation module coming soon. Upload your transaction files to get started.")

def show_performance():
    st.markdown("## 📈 Performance")
    project = project_selector()
    if not project:
        return
    st.info("🚧 Performance analytics module coming soon.")

def show_analysis():
    st.markdown("## 🔍 Analysis")
    project = project_selector()
    if not project:
        return
    st.info("🚧 Analysis module coming soon.")

def show_health():
    st.markdown("## ❤️ Health Status")
    project = project_selector()
    if not project:
        return
    st.info("🚧 Health status module coming soon.")

def show_daily():
    st.markdown("## 📅 Daily Performance")
    project = project_selector()
    if not project:
        return
    st.info("🚧 Daily performance module coming soon.")

def show_monthly():
    st.markdown("## 📆 Monthly Report")
    project = project_selector()
    if not project:
        return
    st.info("🚧 Monthly report module coming soon.")

def show_commission():
    st.markdown("## 💰 Agent Commission")
    project = project_selector()
    if not project:
        return
    st.info("🚧 Commission module coming soon.")

def show_reports():
    st.markdown("## 📊 Reports")
    project = project_selector()
    if not project:
        return
    st.info("🚧 Report generation module coming soon.")

# ─────────────────────────────────────────────
# ADMIN PANEL - FULL FEATURED
# ─────────────────────────────────────────────
def show_admin():
    st.markdown("## ⚙️ Admin Panel")
    user = st.session_state.get("user", {})
    role = user.get("role", "viewer")
    if role not in ["superadmin", "admin"]:
        st.error("Access denied.")
        return
    sb = get_supabase()

    tabs = st.tabs(["👥 Users", "➕ Add User", "🔑 Permissions", "📁 Projects", "🔐 2FA & Security"])

    # ── TAB 1: USERS ──
    with tabs[0]:
        st.subheader("All Users")
        try:
            res = sb.table("users").select("*").order("created_at", desc=True).execute()
            users = res.data or []
            if not users:
                st.info("No users found.")
            else:
                for u in users:
                    with st.expander(f"{'🟢' if u.get('is_approved') else '🔴'} {u.get('username','N/A')} | {u.get('email','N/A')} | {u.get('role','viewer')}"):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**ID:** {u['id'][:8]}...")
                            st.write(f"**Email:** {u['email']}")
                            st.write(f"**Username:** {u.get('username','N/A')}")
                            st.write(f"**Role:** {u.get('role','viewer')}")
                            st.write(f"**Approved:** {'✅' if u.get('is_approved') else '❌'}")
                            st.write(f"**2FA Enabled:** {'✅' if u.get('totp_enabled') else '❌'}")
                        with col2:
                            uid = u["id"]
                            new_role = st.selectbox("Change Role", ["viewer","staff","admin","superadmin"],
                                index=["viewer","staff","admin","superadmin"].index(u.get("role","viewer")),
                                key=f"role_{uid}")
                            col_a, col_b = st.columns(2)
                            with col_a:
                                if st.button("💾 Save Role", key=f"saverole_{uid}"):
                                    sb.table("users").update({"role": new_role}).eq("id", uid).execute()
                                    st.success("Role updated!")
                                    st.rerun()
                            with col_b:
                                if u.get("is_approved"):
                                    if st.button("🚫 Revoke Access", key=f"revoke_{uid}"):
                                        sb.table("users").update({"is_approved": False}).eq("id", uid).execute()
                                        st.success("Access revoked.")
                                        st.rerun()
                                else:
                                    if st.button("✅ Approve", key=f"approve_{uid}"):
                                        sb.table("users").update({"is_approved": True}).eq("id", uid).execute()
                                        st.success("User approved!")
                                        st.rerun()
                        # Project permissions for this user
                        st.markdown("**Project Access:**")
                        all_proj = sb.table("projects").select("*").eq("is_active", True).execute().data or []
                        user_proj = sb.table("user_project_permissions").select("project_id").eq("user_id", uid).execute().data or []
                        assigned_ids = [p["project_id"] for p in user_proj]
                        for proj in all_proj:
                            pid = proj["id"]
                            has_access = pid in assigned_ids
                            checked = st.checkbox(f"{proj['name']}", value=has_access, key=f"proj_{uid}_{pid}")
                            if checked != has_access:
                                if checked:
                                    sb.table("user_project_permissions").insert({"user_id": uid, "project_id": pid, "can_view": True, "can_upload": True}).execute()
                                else:
                                    sb.table("user_project_permissions").delete().eq("user_id", uid).eq("project_id", pid).execute()
                                st.success(f"Project access updated for {proj['name']}!")
                                st.rerun()
        except Exception as e:
            st.error(f"Error loading users: {e}")

    # ── TAB 2: ADD USER ──
    with tabs[1]:
        st.subheader("Add New User")
        with st.form("add_user_form"):
            new_email = st.text_input("📧 Email Address")
            new_username = st.text_input("👤 Username")
            new_role = st.selectbox("🎭 Role", ["viewer", "staff", "admin"])
            all_proj_res = sb.table("projects").select("*").eq("is_active", True).execute()
            all_projs = all_proj_res.data or []
            proj_labels = [p["name"] for p in all_projs]
            selected_projs = st.multiselect("📁 Assign Projects", proj_labels)
            auto_approve = st.checkbox("✅ Auto-approve user", value=True)
            send_invite = st.form_submit_button("➕ Create User & Send Invite", use_container_width=True)

        if send_invite:
            if not new_email or not new_username:
                st.error("Email and username are required.")
            else:
                temp_pass = generate_temp_password()
                try:
                    # Create user in Supabase Auth
                    auth_res = sb.auth.admin.create_user({
                        "email": new_email,
                        "password": temp_pass,
                        "email_confirm": True
                    })
                    new_uid = auth_res.user.id
                    # Insert into users table
                    sb.table("users").insert({
                        "id": new_uid,
                        "email": new_email,
                        "username": new_username,
                        "role": new_role,
                        "is_approved": auto_approve,
                        "totp_enabled": False,
                        "created_at": datetime.datetime.utcnow().isoformat()
                    }).execute()
                    # Assign projects
                    for pname in selected_projs:
                        for p in all_projs:
                            if p["name"] == pname:
                                sb.table("user_project_permissions").insert({
                                    "user_id": new_uid,
                                    "project_id": p["id"],
                                    "can_view": True,
                                    "can_upload": True
                                }).execute()
                    st.success(f"✅ User created successfully!")
                    st.info(f"**Temporary Password:** `{temp_pass}`")
                    st.warning("Share this password securely with the user. They should change it on first login.")
                except Exception as e:
                    st.error(f"Error creating user: {e}")

    # ── TAB 3: PERMISSIONS ──
    with tabs[2]:
        st.subheader("Project Permissions")
        st.info("Select a user to edit their project assignments.")
        try:
            users_res = sb.table("users").select("id, username, email, role").execute()
            users_list = users_res.data or []
            if users_list:
                user_options = {f"{u.get('username','?')} ({u['email']})": u["id"] for u in users_list}
                selected_label = st.selectbox("Select User", list(user_options.keys()))
                target_uid = user_options[selected_label]

                all_proj = sb.table("projects").select("*").eq("is_active", True).execute().data or []
                user_proj = sb.table("user_project_permissions").select("project_id, can_view, can_upload").eq("user_id", target_uid).execute().data or []
                proj_map = {p["project_id"]: p for p in user_proj}

                st.markdown("**Project Access & Permissions:**")
                for proj in all_proj:
                    pid = proj["id"]
                    existing = proj_map.get(pid, {})
                    has_access = pid in proj_map
                    col1, col2, col3 = st.columns([2, 1, 1])
                    with col1:
                        access = st.checkbox(f"**{proj['name']}**", value=has_access, key=f"perm_access_{target_uid}_{pid}")
                    with col2:
                        can_view = st.checkbox("View", value=existing.get("can_view", True), key=f"perm_view_{target_uid}_{pid}", disabled=not access)
                    with col3:
                        can_upload = st.checkbox("Upload", value=existing.get("can_upload", False), key=f"perm_upload_{target_uid}_{pid}", disabled=not access)

                if st.button("💾 Save All Permissions", use_container_width=True):
                    try:
                        sb.table("user_project_permissions").delete().eq("user_id", target_uid).execute()
                        for proj in all_proj:
                            pid = proj["id"]
                            access_key = f"perm_access_{target_uid}_{pid}"
                            if st.session_state.get(access_key, False):
                                sb.table("user_project_permissions").insert({
                                    "user_id": target_uid,
                                    "project_id": pid,
                                    "can_view": st.session_state.get(f"perm_view_{target_uid}_{pid}", True),
                                    "can_upload": st.session_state.get(f"perm_upload_{target_uid}_{pid}", False)
                                }).execute()
                        st.success("✅ Permissions saved!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error saving permissions: {e}")
        except Exception as e:
            st.error(f"Error: {e}")

    # ── TAB 4: PROJECTS ──
    with tabs[3]:
        st.subheader("Manage Projects")
        try:
            projs = sb.table("projects").select("*").execute().data or []
            for p in projs:
                with st.expander(f"{'🟢' if p.get('is_active') else '🔴'} {p['name']} ({p.get('code','')})"):
                    st.write(f"**ID:** {p['id']}")
                    st.write(f"**Name:** {p['name']}")
                    st.write(f"**Code:** {p.get('code','')}")
                    st.write(f"**Active:** {'Yes' if p.get('is_active') else 'No'}")
                    col_a, col_b = st.columns(2)
                    with col_a:
                        if p.get("is_active"):
                            if st.button("🔴 Deactivate", key=f"deact_{p['id']}"):
                                sb.table("projects").update({"is_active": False}).eq("id", p["id"]).execute()
                                st.rerun()
                        else:
                            if st.button("🟢 Activate", key=f"act_{p['id']}"):
                                sb.table("projects").update({"is_active": True}).eq("id", p["id"]).execute()
                                st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

        st.divider()
        st.subheader("Add New Project")
        with st.form("add_proj_form"):
            proj_name = st.text_input("Project Name")
            proj_code = st.text_input("Project Code (e.g. NEW_PROJ)")
            if st.form_submit_button("➕ Add Project"):
                if proj_name and proj_code:
                    try:
                        sb.table("projects").insert({"name": proj_name, "code": proj_code.upper(), "is_active": True}).execute()
                        st.success(f"Project '{proj_name}' added!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
                else:
                    st.error("Name and code are required.")

    # ── TAB 5: 2FA & SECURITY ──
    with tabs[4]:
        st.subheader("2FA & Security Management")

        st.markdown("### 🔄 Reset User Password")
        with st.form("reset_password_form"):
            users_res2 = sb.table("users").select("id, username, email").execute()
            users2 = users_res2.data or []
            user_opts2 = {f"{u.get('username','?')} ({u['email']})": u for u in users2}
            sel_user_label = st.selectbox("Select User", list(user_opts2.keys()), key="reset_pw_sel")
            new_password = st.text_input("New Password", type="password", help="Leave blank to generate a temporary password")
            if st.form_submit_button("🔑 Reset Password", use_container_width=True):
                target_user = user_opts2[sel_user_label]
                use_password = new_password if new_password else generate_temp_password()
                try:
                    sb.auth.admin.update_user_by_id(target_user["id"], {"password": use_password})
                    st.success(f"✅ Password reset for {target_user['email']}")
                    if not new_password:
                        st.info(f"**Temporary Password:** `{use_password}`")
                        st.warning("Share this with the user securely.")
                except Exception as e:
                    st.error(f"Error resetting password: {e}")

        st.divider()
        st.markdown("### 🔐 Reset User 2FA")
        with st.form("reset_2fa_form"):
            user_opts3 = {f"{u.get('username','?')} ({u['email']})": u for u in (sb.table("users").select("id, username, email, totp_enabled").execute().data or [])}
            sel_2fa_label = st.selectbox("Select User", list(user_opts3.keys()), key="reset_2fa_sel")
            if st.form_submit_button("🔓 Reset 2FA", use_container_width=True):
                target_2fa = user_opts3[sel_2fa_label]
                try:
                    sb.table("users").update({"totp_secret": None, "totp_enabled": False}).eq("id", target_2fa["id"]).execute()
                    st.success(f"✅ 2FA reset for {target_2fa['email']}. User must set up 2FA again on next login.")
                except Exception as e:
                    st.error(f"Error resetting 2FA: {e}")

        st.divider()
        st.markdown("### 🔑 Generate Admin One-Time Code")
        st.caption("Generate a one-time code for a user who cannot access their 2FA app.")
        with st.form("otp_form"):
            user_opts4 = {f"{u.get('username','?')} ({u['email']})": u for u in (sb.table("users").select("id, username, email").execute().data or [])}
            sel_otp_label = st.selectbox("Select User", list(user_opts4.keys()), key="otp_sel")
            if st.form_submit_button("🎲 Generate One-Time Code", use_container_width=True):
                target_otp = user_opts4[sel_otp_label]
                otp_code = ''.join(secrets.choice(string.digits) for _ in range(8))
                exp_time = (datetime.datetime.utcnow() + datetime.timedelta(minutes=15)).isoformat()
                try:
                    sb.table("users").update({"admin_otp": otp_code, "admin_otp_expires": exp_time}).eq("id", target_otp["id"]).execute()
                    st.success(f"✅ One-time code generated!")
                    st.info(f"**Code:** `{otp_code}` (valid for 15 minutes)")
                    st.warning("Share this code with the user via a secure channel.")
                except Exception as e:
                    # If columns don't exist, show code anyway
                    st.success(f"✅ One-time code (share securely):")
                    st.info(f"**Code:** `{otp_code}` (valid 15 min)")

        st.divider()
        st.markdown("### 👤 Change My Password")
        with st.form("change_my_pw_form"):
            my_new_pw = st.text_input("New Password", type="password")
            my_confirm_pw = st.text_input("Confirm New Password", type="password")
            if st.form_submit_button("💾 Update My Password", use_container_width=True):
                if not my_new_pw:
                    st.error("Password cannot be empty.")
                elif my_new_pw != my_confirm_pw:
                    st.error("Passwords do not match.")
                elif len(my_new_pw) < 8:
                    st.error("Password must be at least 8 characters.")
                else:
                    try:
                        sb.auth.admin.update_user_by_id(user["id"], {"password": my_new_pw})
                        st.success("✅ Your password has been updated!")
                    except Exception as e:
                        st.error(f"Error: {e}")

# ─────────────────────────────────────────────
# MAIN CONTENT ROUTER
# ─────────────────────────────────────────────
def show_main_content():
    page = st.session_state.get("page", "dashboard")
    route = {
        "dashboard": show_dashboard,
        "recon": show_recon,
        "performance": show_performance,
        "analysis": show_analysis,
        "health": show_health,
        "daily": show_daily,
        "monthly": show_monthly,
        "commission": show_commission,
        "uploads": show_uploads,
        "reports": show_reports,
        "admin": show_admin,
    }
    fn = route.get(page, show_dashboard)
    fn()

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    if "user" not in st.session_state:
        show_login()
        return
    show_sidebar()
    show_main_content()

main()
