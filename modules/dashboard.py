# BizReport Pro - Dashboard Module
import streamlit as st
import pandas as pd
import plotly.express as px
from utils.supabase_client import get_supabase


def show_dashboard():
    st.title("🏠 Dashboard")
    st.markdown("### Business Overview")

    profile = st.session_state.get("profile", {})
    role = profile.get("role", "viewer")
    full_name = profile.get("full_name") or profile.get("username") or "User"

    st.markdown(f"Welcome back, **{full_name}**!")
    st.divider()

    # Project selector
    try:
        supabase = get_supabase()
        projects_res = supabase.table("projects").select("*").execute()
        projects = projects_res.data or []
    except Exception:
        projects = []

    if not projects:
        st.info("No projects found. Ask your admin to set up projects.")
        return

    project_names = [p["name"] for p in projects]
    selected_project = st.selectbox("📁 Select Project", project_names)
    project = next((p for p in projects if p["name"] == selected_project), None)

    if not project:
        return

    st.divider()

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    try:
        supabase = get_supabase()
        uploads_res = supabase.table("uploads").select("id").eq("project_id", project["id"]).execute()
        reports_res = supabase.table("reports").select("id").eq("project_id", project["id"]).execute()
        tx_res = supabase.table("transactions").select("id").eq("project_id", project["id"]).execute()

        num_uploads = len(uploads_res.data or [])
        num_reports = len(reports_res.data or [])
        num_tx = len(tx_res.data or [])
    except Exception:
        num_uploads = num_reports = num_tx = 0

    with col1:
        st.metric("📁 Total Uploads", num_uploads)
    with col2:
        st.metric("📋 Reports", num_reports)
    with col3:
        st.metric("💳 Transactions", num_tx)
    with col4:
        st.metric("📊 Project", selected_project, delta="Active")

    st.divider()
    st.markdown("### 📈 Quick Summary")
    st.info("Use the navigation menu on the left to access detailed reports: Recon, Performance, Analysis, Health, Daily, Monthly, Commission, Uploads, and Reports.")

    # Recent activity
    st.markdown("### 🕐 Recent Activity")
    try:
        supabase = get_supabase()
        recent_uploads = supabase.table("uploads").select("*") \
            .eq("project_id", project["id"]) \
            .order("created_at", desc=True) \
            .limit(5) \
            .execute()

        if recent_uploads.data:
            df = pd.DataFrame(recent_uploads.data)
            cols_to_show = [c for c in ["filename", "file_type", "uploaded_by", "created_at"] if c in df.columns]
            if cols_to_show:
                st.dataframe(df[cols_to_show], use_container_width=True)
        else:
            st.info("No recent uploads for this project.")
    except Exception as e:
        st.warning(f"Could not load recent activity: {str(e)}")
