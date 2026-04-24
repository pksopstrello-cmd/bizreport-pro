import streamlit as st
import pandas as pd
import datetime
import pyotp
from utils.supabase_client import get_supabase


def show_admin():
    st.title("⚙️ Admin Panel")

    profile = st.session_state.get("profile", {})
    role = profile.get("role", "viewer")

    if role not in ["superadmin", "admin"]:
        st.error("Access denied. Admin privileges required.")
        return

    tab1, tab2, tab3, tab4 = st.tabs(["👥 Users", "🔑 Permissions", "📁 Projects", "🔐 2FA Codes"])

    # --- USERS TAB ---
    with tab1:
        st.subheader("User Management")
        try:
            supabase = get_supabase()
            res = supabase.table("profiles").select("*").execute()
            users = res.data or []
        except Exception as e:
            st.error(f"Could not load users: {e}")
            users = []

        if users:
            df = pd.DataFrame(users)
            cols = [c for c in ["id", "username", "full_name", "role", "is_approved"] if c in df.columns]
            st.dataframe(df[cols] if cols else df, use_container_width=True)

        st.divider()
        st.subheader("Update User Role / Approval")
        if users:
            user_ids = [u.get("id", "") for u in users]
            user_names = [u.get("username") or u.get("full_name") or u.get("id", "")[:8] for u in users]
            user_options = dict(zip(user_names, user_ids))

            selected_name = st.selectbox("Select User", list(user_options.keys()))
            selected_uid = user_options.get(selected_name)

            new_role = st.selectbox("Role", ["viewer", "staff", "admin", "superadmin"])
            is_approved = st.checkbox("Approved", value=True)

            if st.button("Update User"):
                try:
                    supabase = get_supabase()
                    supabase.table("profiles").update({
                        "role": new_role,
                        "is_approved": is_approved
                    }).eq("id", selected_uid).execute()
                    st.success(f"User updated: {selected_name} → {new_role}, approved={is_approved}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Update failed: {e}")

    # --- PERMISSIONS TAB ---
    with tab2:
        st.subheader("Module Permissions")
        try:
            supabase = get_supabase()
            projects = supabase.table("projects").select("*").execute().data or []
            profiles = supabase.table("profiles").select("*").execute().data or []
        except Exception as e:
            st.error(f"Could not load: {e}")
            projects = []
            profiles = []

        if not projects or not profiles:
            st.info("No projects or users found.")
        else:
            sel_proj = st.selectbox("Project", [p["name"] for p in projects], key="perm_proj")
            project = next((p for p in projects if p["name"] == sel_proj), None)

            user_names = [u.get("username") or u.get("id", "")[:8] for u in profiles]
            user_ids = [u.get("id") for u in profiles]
            user_map = dict(zip(user_names, user_ids))

            sel_user = st.selectbox("User", list(user_map.keys()), key="perm_user")
            sel_uid = user_map.get(sel_user)

            modules = ["recon", "performance", "analysis", "health", "daily", "monthly", "commission", "uploads", "reports"]
            st.write("Select modules to grant access:")

            if project and sel_uid:
                try:
                    supabase = get_supabase()
                    existing = supabase.table("permissions").select("module").eq("user_id", sel_uid).eq("project_id", project["id"]).eq("can_access", True).execute().data or []
                    existing_modules = [e["module"] for e in existing]
                except Exception:
                    existing_modules = []

                selected_modules = []
                cols = st.columns(3)
                for i, mod in enumerate(modules):
                    with cols[i % 3]:
                        if st.checkbox(mod.capitalize(), value=mod in existing_modules, key=f"perm_{mod}_{sel_uid}"):
                            selected_modules.append(mod)

                if st.button("💾 Save Permissions"):
                    try:
                        supabase = get_supabase()
                        supabase.table("permissions").delete().eq("user_id", sel_uid).eq("project_id", project["id"]).execute()
                        for mod in selected_modules:
                            supabase.table("permissions").insert({
                                "user_id": sel_uid,
                                "project_id": project["id"],
                                "module": mod,
                                "can_access": True
                            }).execute()
                        st.success(f"Permissions saved for {sel_user} on {sel_proj}!")
                    except Exception as e:
                        st.error(f"Failed: {e}")

    # --- PROJECTS TAB ---
    with tab3:
        st.subheader("Projects")
        try:
            supabase = get_supabase()
            projects = supabase.table("projects").select("*").execute().data or []
        except Exception:
            projects = []

        if projects:
            st.dataframe(pd.DataFrame(projects), use_container_width=True)

        st.divider()
        st.subheader("Add New Project")
        with st.form("add_project"):
            proj_name = st.text_input("Project Name")
            proj_code = st.text_input("Project Code (no spaces, e.g. MY_PROJECT)")
            submitted = st.form_submit_button("Add Project")

        if submitted and proj_name and proj_code:
            try:
                supabase = get_supabase()
                supabase.table("projects").insert({"name": proj_name, "code": proj_code}).execute()
                st.success(f"Project '{proj_name}' added!")
                st.rerun()
            except Exception as e:
                st.error(f"Failed: {e}")

    # --- 2FA CODES TAB ---
    with tab4:
        st.subheader("Generate One-Time Login Code")
        st.info("Generate a temporary code for a user who lost their 2FA device. Code expires in 24 hours.")

        try:
            supabase = get_supabase()
            profiles = supabase.table("profiles").select("*").execute().data or []
        except Exception:
            profiles = []

        if not profiles:
            st.info("No users found.")
        else:
            user_names = [u.get("username") or u.get("id", "")[:8] for u in profiles]
            user_ids = [u.get("id") for u in profiles]
            user_map = dict(zip(user_names, user_ids))

            sel_user = st.selectbox("Select User", list(user_map.keys()), key="2fa_user")
            sel_uid = user_map.get(sel_user)

            if st.button("🎲 Generate Code"):
                import random
                import string
                code = "".join(random.choices(string.digits, k=8))
                exp = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=24)
                try:
                    supabase = get_supabase()
                    supabase.table("profiles").update({
                        "temp_code": code,
                        "temp_code_exp": exp.isoformat()
                    }).eq("id", sel_uid).execute()
                    st.success(f"One-time code for {sel_user}:")
                    st.code(code, language=None)
                    st.warning("Share this code securely. It expires in 24 hours.")
                except Exception as e:
                    st.error(f"Failed: {e}")
