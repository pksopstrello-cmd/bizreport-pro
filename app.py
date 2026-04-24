import streamlit as st
import pyotp
import time
from utils.supabase_client import get_supabase
from utils.auth import login_user, logout_user, get_user_profile, check_permission, verify_totp, generate_totp_secret, get_totp_uri

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
    .main-header { font-size: 2rem; font-weight: bold; color: #1f77b4; }
    .sub-header { font-size: 1rem; color: #666; }
    .login-box { max-width: 400px; margin: auto; }
    .stAlert { border-radius: 8px; }
</style>
""", unsafe_allow_html=True)


def show_login():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("## 📊 BizReport Pro")
        st.markdown("**Business Intelligence Platform**")
        st.divider()

        with st.form("login_form"):
            email = st.text_input("📧 Email", placeholder="Enter your email")
            password = st.text_input("🔒 Password", type="password", placeholder="Enter your password")
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
                st.error("Invalid credentials. Please try again.")
                return

            # Get user profile
            profile = get_user_profile(user.id)

            if not profile:
                st.error("User profile not found. Please contact your administrator.")
                return

            if not profile.get("is_approved", False):
                st.error("Your account is pending approval. Please contact your administrator.")
                return

            # Check if 2FA is enabled
            if profile.get("totp_enabled", False) and profile.get("totp_secret"):
                st.session_state["pending_2fa_user"] = user
                st.session_state["pending_2fa_profile"] = profile
                st.session_state["show_2fa"] = True
                st.rerun()
            else:
                st.session_state["user"] = user
                st.session_state["profile"] = profile
                st.session_state["logged_in"] = True
                st.rerun()


def show_2fa():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("## 🔐 Two-Factor Authentication")
        st.info("Enter the 6-digit code from your authenticator app or the one-time code from your admin.")

        with st.form("totp_form"):
            code = st.text_input("Verification Code", placeholder="Enter 6-digit code", max_chars=8)
            submitted = st.form_submit_button("Verify", use_container_width=True)

        if submitted and code:
            profile = st.session_state.get("pending_2fa_profile", {})
            user = st.session_state.get("pending_2fa_user")

            totp_valid = verify_totp(profile.get("totp_secret", ""), code)

            temp_valid = False
            if profile.get("temp_code") and profile.get("temp_code_exp"):
                import datetime
                now = datetime.datetime.now(datetime.timezone.utc)
                try:
                    exp = datetime.datetime.fromisoformat(str(profile.get("temp_code_exp", "")).replace("Z", "+00:00"))
                    if code == profile.get("temp_code") and now < exp:
                        temp_valid = True
                        supabase = get_supabase()
                        supabase.table("profiles").update({"temp_code": None, "temp_code_exp": None}).eq("id", user.id).execute()
                except Exception:
                    pass

            if totp_valid or temp_valid:
                st.session_state["user"] = user
                st.session_state["profile"] = profile
                st.session_state["logged_in"] = True
                for k in ["pending_2fa_user", "pending_2fa_profile", "show_2fa"]:
                    st.session_state.pop(k, None)
                st.rerun()
            else:
                st.error("Invalid verification code.")

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

        pages = {
            "🏠 Dashboard": "dashboard",
            "🔍 Recon": "recon",
            "📈 Performance": "performance",
            "📉 Analysis": "analysis",
            "💚 Health Status": "health",
            "📅 Daily Report": "daily",
            "📆 Monthly Report": "monthly",
            "💰 Commission": "commission",
            "📁 Uploads": "uploads",
            "📋 Reports": "reports",
        }

        if role in ["superadmin", "admin"]:
            pages["⚙️ Admin Panel"] = "admin"

        for label, page_key in pages.items():
            if st.sidebar.button(label, key=f"nav_{page_key}", use_container_width=True):
                st.session_state["current_page"] = page_key

        st.divider()
        if st.sidebar.button("🚪 Logout", use_container_width=True):
            logout_user()
            st.rerun()


def show_main_content():
    page = st.session_state.get("current_page", "dashboard")
    profile = st.session_state.get("profile", {})
    role = profile.get("role", "viewer")

    try:
        if page == "dashboard":
            from pages.dashboard import show_dashboard
            show_dashboard()
        elif page == "recon":
            from pages.recon import show_recon
            show_recon()
        elif page == "performance":
            from pages.performance import show_performance
            show_performance()
        elif page == "analysis":
            from pages.analysis import show_analysis
            show_analysis()
        elif page == "health":
            from pages.health import show_health
            show_health()
        elif page == "daily":
            from pages.daily import show_daily
            show_daily()
        elif page == "monthly":
            from pages.monthly import show_monthly
            show_monthly()
        elif page == "commission":
            from pages.commission import show_commission
            show_commission()
        elif page == "uploads":
            from pages.uploads import show_uploads
            show_uploads()
        elif page == "reports":
            from pages.reports import show_reports
            show_reports()
        elif page == "admin" and role in ["superadmin", "admin"]:
            from pages.admin import show_admin
            show_admin()
        else:
            st.warning("Page not found or access denied.")
    except Exception as e:
        st.error(f"Error loading page: {str(e)}")
        st.exception(e)


def main():
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False
    if "current_page" not in st.session_state:
        st.session_state["current_page"] = "dashboard"

    if st.session_state.get("show_2fa"):
        show_2fa()
    elif not st.session_state.get("logged_in"):
        show_login()
    else:
        show_sidebar()
        show_main_content()


if __name__ == "__main__":
    main()
