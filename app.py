import streamlit as st
import pyotp
import time
from utils.supabase_client import get_supabase
from utils.auth import login_user, verify_totp, get_user_profile, logout_user

# Page config
st.set_page_config(
    page_title="BizReport Pro",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1e3a5f 0%, #0d2137 100%);
    }
    [data-testid="stSidebar"] * { color: #ffffff !important; }
    .main-header {
        background: linear-gradient(90deg, #1e3a5f, #2d6a9f);
        padding: 1rem 2rem;
        border-radius: 10px;
        margin-bottom: 1.5rem;
        color: white;
    }
    .metric-card {
        background: #1a1f2e;
        border: 1px solid #2d4a6e;
        border-radius: 10px;
        padding: 1.2rem;
        text-align: center;
    }
    .login-container {
        max-width: 400px;
        margin: 0 auto;
        padding: 2rem;
        background: #1a1f2e;
        border-radius: 15px;
        border: 1px solid #2d4a6e;
    }
    .stButton > button {
        background: linear-gradient(90deg, #1e3a5f, #2d6a9f);
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 600;
        width: 100%;
    }
    .stButton > button:hover {
        background: linear-gradient(90deg, #2d6a9f, #1e3a5f);
    }
    div[data-testid="stSelectbox"] label,
    div[data-testid="stTextInput"] label { color: #a0b4c8 !important; }
</style>
""", unsafe_allow_html=True)

def show_login():
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    st.markdown("## 📊 BizReport Pro")
    st.markdown("##### Business Intelligence Platform")
    st.divider()

    with st.form("login_form"):
        email = st.text_input("📧 Email", placeholder="Enter your email")
        password = st.text_input("🔒 Password", type="password", placeholder="Enter your password")
        submitted = st.form_submit_button("Sign In", use_container_width=True)

        if submitted:
            if not email or not password:
                st.error("Please enter email and password.")
            else:
                with st.spinner("Signing in..."):
                    result = login_user(email, password)
                    if result["success"]:
                        st.session_state["auth_stage"] = "2fa"
                        st.session_state["temp_user"] = result["user"]
                        st.session_state["temp_session"] = result["session"]
                        st.rerun()
                    else:
                        st.error(result["error"])

    st.markdown('</div>', unsafe_allow_html=True)

def show_2fa():
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    st.markdown("## 🔐 Two-Factor Authentication")
    st.markdown("Enter the 6-digit code from your authenticator app, or the code provided by your admin.")
    st.divider()

    user = st.session_state.get("temp_user")
    if not user:
        st.session_state["auth_stage"] = "login"
        st.rerun()

    # Get user profile to check if 2FA is enabled
    profile = get_user_profile(user.id)

    with st.form("totp_form"):
        code = st.text_input("🔑 6-Digit Code", placeholder="123456", max_chars=6)
        col1, col2 = st.columns(2)
        with col1:
            verify_btn = st.form_submit_button("Verify", use_container_width=True)
        with col2:
            back_btn = st.form_submit_button("Back", use_container_width=True)

        if verify_btn:
            if not code or len(code) != 6:
                st.error("Enter a valid 6-digit code.")
            else:
                result = verify_totp(user.id, code, profile)
                if result["success"]:
                    st.session_state["authenticated"] = True
                    st.session_state["user"] = user
                    st.session_state["profile"] = profile
                    st.session_state["session"] = st.session_state["temp_session"]
                    del st.session_state["auth_stage"]
                    del st.session_state["temp_user"]
                    del st.session_state["temp_session"]
                    st.success("Login successful!")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error(result["error"])

        if back_btn:
            st.session_state["auth_stage"] = "login"
            logout_user()
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

def show_dashboard():
    user = st.session_state.get("user")
    profile = st.session_state.get("profile")

    if not user or not profile:
        st.session_state.clear()
        st.rerun()

    role = profile.get("role", "viewer")
    username = profile.get("username", "User")

    # Sidebar
    with st.sidebar:
        st.markdown(f"### 👤 {username}")
        st.markdown(f"**Role:** {role.title()}")
        st.divider()

        # Project selector
        supabase = get_supabase()
        projects_res = supabase.table("projects").select("*").eq("is_active", True).execute()
        projects = projects_res.data if projects_res.data else []

        if projects:
            project_names = [p["name"] for p in projects]
            if "selected_project" not in st.session_state:
                st.session_state["selected_project"] = projects[0]["id"]

            selected_name = st.selectbox("📁 Project", project_names)
            selected_project = next((p for p in projects if p["name"] == selected_name), projects[0])
            st.session_state["selected_project"] = selected_project["id"]
            st.session_state["selected_project_name"] = selected_project["name"]

        st.divider()
        st.markdown("**📊 Navigation**")

        pages = {
            "🏠 Dashboard": "dashboard",
            "🔄 Reconciliation": "recon",
            "📈 Performance": "performance",
            "🔍 Analysis": "analysis",
            "❤️ Health Status": "health",
            "📅 Daily Report": "daily",
            "📆 Monthly Report": "monthly",
            "💰 Agent Commission": "commission",
        }

        if role in ["superadmin", "admin", "staff"]:
            pages["📤 File Uploads"] = "uploads"
            pages["📋 Reports"] = "reports"

        if role in ["superadmin", "admin"]:
            pages["⚙️ Admin Panel"] = "admin"

        if "current_page" not in st.session_state:
            st.session_state["current_page"] = "dashboard"

        for label, page_key in pages.items():
            if st.button(label, use_container_width=True, key=f"nav_{page_key}"):
                st.session_state["current_page"] = page_key

        st.divider()
        if st.button("🚪 Sign Out", use_container_width=True):
            logout_user()
            st.session_state.clear()
            st.rerun()

    # Main content
    current_page = st.session_state.get("current_page", "dashboard")
    project_id = st.session_state.get("selected_project")
    project_name = st.session_state.get("selected_project_name", "")

    # Header
    st.markdown(f'<div class="main-header"><h2>📊 BizReport Pro</h2><p>Project: {project_name}</p></div>', unsafe_allow_html=True)

    # Route to pages
    if current_page == "dashboard":
        from pages import dashboard
        dashboard.show(project_id, project_name, profile)
    elif current_page == "recon":
        from pages import recon
        recon.show(project_id, project_name, profile)
    elif current_page == "performance":
        from pages import performance
        performance.show(project_id, project_name, profile)
    elif current_page == "analysis":
        from pages import analysis
        analysis.show(project_id, project_name, profile)
    elif current_page == "health":
        from pages import health
        health.show(project_id, project_name, profile)
    elif current_page == "daily":
        from pages import daily
        daily.show(project_id, project_name, profile)
    elif current_page == "monthly":
        from pages import monthly
        monthly.show(project_id, project_name, profile)
    elif current_page == "commission":
        from pages import commission
        commission.show(project_id, project_name, profile)
    elif current_page == "uploads":
        from pages import uploads
        uploads.show(project_id, project_name, profile)
    elif current_page == "reports":
        from pages import reports
        reports.show(project_id, project_name, profile)
    elif current_page == "admin":
        if role in ["superadmin", "admin"]:
            from pages import admin
            admin.show(profile)
        else:
            st.error("Access denied.")

# Main routing
def main():
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    auth_stage = st.session_state.get("auth_stage", "login")

    if not st.session_state["authenticated"]:
        if auth_stage == "2fa":
            show_2fa()
        else:
            show_login()
    else:
        show_dashboard()

if __name__ == "__main__":
    main()
