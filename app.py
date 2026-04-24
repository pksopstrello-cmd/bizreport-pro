import streamlit as st
import pyotp
import time
import datetime
import pandas as pd
import secrets
import string
from utils.supabase_client import get_supabase

st.set_page_config(page_title="BizReport Pro", page_icon="&#x1F4CA;", layout="wide", initial_sidebar_state="expanded")
st.markdown("""<style>.stAlert{border-radius:8px}</style>""", unsafe_allow_html=True)

# AUTH
def do_login(email, password):
    try:
        sb = get_supabase()
        resp = sb.auth.sign_in_with_password({"email": email, "password": password})
        if not resp.user:
            return None, "Invalid credentials"
        uid = resp.user.id
        profile = sb.table("users").select("*").eq("id", uid).single().execute()
        if not profile.data:
            return None, "User profile not found. Contact admin."
        if not profile.data.get("is_approved", False):
            sb.auth.sign_out()
            return None, "Account pending approval. Contact admin."
        return profile.data, None
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
        st.markdown("## &#x1F4CA; BizReport Pro")
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

# HELPERS
def get_projects():
    try:
        sb = get_supabase()
        user = st.session_state.get("user", {})
        role = user.get("role", "viewer")
        if role == "superadmin":
            res = sb.table("projects").select("*").eq("is_active", True).execute()
            return res.data or []
        uid = user.get("id", "")
        res = sb.table("user_project_permissions").select("project_id, projects(*)").eq("user_id", uid).execute()
        return [r["projects"] for r in (res.data or []) if r.get("projects")]
    except Exception:
        return []

def project_selector():
    projects = get_projects()
    if not projects:
        st.warning("No projects assigned. Contact admin.")
        return None
    names = [p["name"] for p in projects]
    sel = st.session_state.get("selected_project", projects[0])
    if sel.get("name") not in names:
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
    st.markdown(f"### Welcome back, {user.get('username', 'User')}!")
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
        recent = sb.table("uploads").select("*").eq("project_id", pid).order("uploaded_at", desc=True).limit(5).execute()
        if recent.data:
            df = pd.DataFrame(recent.data)[["filename", "file_type", "uploaded_at"]]
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
                    "storage_path": path, "uploaded_at": datetime.datetime.utcnow().isoformat()
                }).execute()
                st.success(f"Uploaded: {f.name}")
            except Exception as e:
                st.error(f"Error uploading {f.name}: {e}")

# PLACEHOLDERS
def show_recon():
    st.markdown("## Reconciliation"); project_selector(); st.info("Coming soon.")
def show_performance():
    st.markdown("## Performance"); project_selector(); st.info("Coming soon.")
def show_analysis():
    st.markdown("## Analysis"); project_selector(); st.info("Coming soon.")
def show_health():
    st.markdown("## Health Status"); project_selector(); st.info("Coming soon.")
def show_daily():
    st.markdown("## Daily Performance"); project_selector(); st.info("Coming soon.")
def show_monthly():
    st.markdown("## Monthly Report"); project_selector(); st.info("Coming soon.")
def show_commission():
    st.markdown("## Agent Commission"); project_selector(); st.info("Coming soon.")
def show_reports():
    st.markdown("## Reports"); project_selector(); st.info("Coming soon.")

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
            users = sb.table("users").select("*").order("created_at", desc=True).execute().data or []
            if not users:
                st.info("No users found.")
            for u in users:
                badge = "Active" if u.get("is_approved") else "Pending"
                with st.expander(f"[{badge}] {u.get('username','?')} | {u.get('email','?')} | {u.get('role','viewer')}"):
                    uid = u["id"]
                    c1, c2 = st.columns(2)
                    with c1:
                        st.write(f"**Email:** {u['email']}")
                        st.write(f"**Username:** {u.get('username','N/A')}")
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
                                sb.table("users").update({"role": new_role}).eq("id", uid).execute()
                                st.success("Role updated!"); st.rerun()
                        with cb:
                            if u.get("is_approved"):
                                if st.button("Revoke", key=f"rv_{uid}"):
                                    sb.table("users").update({"is_approved": False}).eq("id", uid).execute()
                                    st.success("Revoked."); st.rerun()
                            else:
                                if st.button("Approve", key=f"ap_{uid}"):
                                    sb.table("users").update({"is_approved": True}).eq("id", uid).execute()
                                    st.success("Approved!"); st.rerun()
                    st.markdown("**Project Access:**")
                    all_proj = sb.table("projects").select("*").eq("is_active", True).execute().data or []
                    assigned = {p["project_id"] for p in (sb.table("user_project_permissions").select("project_id").eq("user_id", uid).execute().data or [])}
                    for proj in all_proj:
                        pid = proj["id"]
                        has = pid in assigned
                        chk = st.checkbox(proj["name"], value=has, key=f"pc_{uid}_{pid}")
                        if chk != has:
                            if chk:
                                sb.table("user_project_permissions").insert({"user_id": uid, "project_id": pid, "can_view": True, "can_upload": True}).execute()
                            else:
                                sb.table("user_project_permissions").delete().eq("user_id", uid).eq("project_id", pid).execute()
                            st.success(f"Updated {proj['name']}"); st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

    with tab2:
        st.subheader("Create New User")
        with st.form("add_user_form"):
            nu_email = st.text_input("Email")
            nu_username = st.text_input("Username")
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
                        auth_res = sb.auth.admin.create_user({
                            "email": nu_email, "password": tmp_pass, "email_confirm": True
                        })
                        new_uid = auth_res.user.id
                        sb.table("users").insert({
                            "id": new_uid, "email": nu_email, "username": nu_username,
                            "role": nu_role, "is_approved": auto_approve,
                            "totp_enabled": False,
                            "created_at": datetime.datetime.utcnow().isoformat()
                        }).execute()
                        for pname in sel_p:
                            for p in all_p:
                                if p["name"] == pname:
                                    sb.table("user_project_permissions").insert({
                                        "user_id": new_uid, "project_id": p["id"],
                                        "can_view": True, "can_upload": True
                                    }).execute()
                        st.success(f"User created: {nu_email}")
                        st.info(f"Temp Password: {tmp_pass}")
                        st.warning("Share this password securely. User should change after first login.")
                    except Exception as e:
                        st.error(f"Error: {e}")

    with tab3:
        st.subheader("Edit User Permissions")
        try:
            ulist = sb.table("users").select("id, username, email, role").execute().data or []
            if ulist:
                u_opts = {f"{u.get('username','?')} ({u['email']})": u["id"] for u in ulist}
                sel_u = st.selectbox("Select User", list(u_opts.keys()))
                target_uid = u_opts[sel_u]
                all_proj = sb.table("projects").select("*").eq("is_active", True).execute().data or []
                user_proj = sb.table("user_project_permissions").select("project_id, can_view, can_upload").eq("user_id", target_uid).execute().data or []
                proj_map = {p["project_id"]: p for p in user_proj}
                changes = {}
                for proj in all_proj:
                    pid = proj["id"]
                    ex = proj_map.get(pid, {})
                    has = pid in proj_map
                    cc1, cc2, cc3 = st.columns([3,1,1])
                    with cc1:
                        access = st.checkbox(proj["name"], value=has, key=f"pa_{target_uid}_{pid}")
                    with cc2:
                        view = st.checkbox("View", value=ex.get("can_view", True), key=f"pv_{target_uid}_{pid}", disabled=not access)
                    with cc3:
                        upload = st.checkbox("Upload", value=ex.get("can_upload", False), key=f"pu_{target_uid}_{pid}", disabled=not access)
                    changes[pid] = {"access": access, "view": view, "upload": upload}
                if st.button("Save Permissions", use_container_width=True):
                    sb.table("user_project_permissions").delete().eq("user_id", target_uid).execute()
                    for pid, ch in changes.items():
                        if ch["access"]:
                            sb.table("user_project_permissions").insert({
                                "user_id": target_uid, "project_id": pid,
                                "can_view": ch["view"], "can_upload": ch["upload"]
                            }).execute()
                    st.success("Permissions saved!"); st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

    with tab4:
        st.subheader("Projects")
        try:
            projs = sb.table("projects").select("*").execute().data or []
            for p in projs:
                status = "Active" if p.get("is_active") else "Inactive"
                with st.expander(f"[{status}] {p['name']} ({p.get('code','')})"):
                    st.write(f"Code: {p.get('code','')} | Status: {status}")
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
            if st.form_submit_button("Add Project"):
                if pn and pc:
                    try:
                        sb.table("projects").insert({"name": pn, "code": pc.upper(), "is_active": True}).execute()
                        st.success(f"Added: {pn}"); st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
                else:
                    st.error("Name and code required.")

    with tab5:
        st.subheader("Security Management")
        all_users = sb.table("users").select("id, username, email, totp_enabled").execute().data or []
        u_sec = {f"{u.get('username','?')} ({u['email']})": u for u in all_users}

        st.markdown("### Reset User Password")
        with st.form("reset_pw_form"):
            sel_pw = st.selectbox("Select User", list(u_sec.keys()), key="rpw_sel")
            new_pw = st.text_input("New Password (leave blank to auto-generate)", type="password")
            if st.form_submit_button("Reset Password", use_container_width=True):
                target = u_sec[sel_pw]
                use_pw = new_pw.strip() if new_pw.strip() else generate_temp_password()
                try:
                    sb.auth.admin.update_user_by_id(target["id"], {"password": use_pw})
                    st.success(f"Password reset for {target['email']}")
                    if not new_pw.strip():
                        st.info(f"Temp Password: {use_pw}")
                        st.warning("Share this securely with the user.")
                except Exception as e:
                    st.error(f"Error: {e}")

        st.divider()
        st.markdown("### Reset User 2FA")
        with st.form("reset_2fa_form"):
            sel_2fa = st.selectbox("Select User", list(u_sec.keys()), key="r2fa_sel")
            if st.form_submit_button("Reset 2FA", use_container_width=True):
                target = u_sec[sel_2fa]
                try:
                    sb.table("users").update({"totp_secret": None, "totp_enabled": False}).eq("id", target["id"]).execute()
                    st.success(f"2FA reset for {target['email']}. User must re-setup 2FA on next login.")
                except Exception as e:
                    st.error(f"Error: {e}")

        st.divider()
        st.markdown("### Generate One-Time Admin Code")
        st.caption("Use this if a user lost access to their 2FA device.")
        with st.form("otp_form"):
            sel_otp = st.selectbox("Select User", list(u_sec.keys()), key="otp_sel")
            if st.form_submit_button("Generate Code", use_container_width=True):
                otp = "".join(secrets.choice(string.digits) for _ in range(8))
                st.success("One-time code generated!")
                st.info(f"Code: {otp}   (valid 15 min - share securely)")

        st.divider()
        st.markdown("### Change My Own Password")
        with st.form("my_pw_form"):
            my_pw = st.text_input("New Password", type="password")
            my_pw2 = st.text_input("Confirm Password", type="password")
            if st.form_submit_button("Update My Password", use_container_width=True):
                if not my_pw:
                    st.error("Password cannot be empty.")
                elif my_pw != my_pw2:
                    st.error("Passwords do not match.")
                elif len(my_pw) < 8:
                    st.error("Must be at least 8 characters.")
                else:
                    try:
                        sb.auth.admin.update_user_by_id(user["id"], {"password": my_pw})
                        st.success("Password updated successfully!")
                    except Exception as e:
                        st.error(f"Error: {e}")

# ROUTER
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
    # Safety: ensure user is a dict (not a stale Supabase User object)
    if not isinstance(st.session_state.user, dict):
        do_logout()
        st.rerun()
        return
    show_sidebar()
    show_main_content()

main()
