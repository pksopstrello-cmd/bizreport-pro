import streamlit as st
import pyotp
import time
from utils.supabase_client import get_supabase


def login_user(email, password):
    """Authenticate user with email and password."""
    try:
        supabase = get_supabase()
        response = supabase.auth.sign_in_with_password({"email": email, "password": password})
        if response.user:
            return response.user, None
        return None, "Invalid credentials"
    except Exception as e:
        return None, str(e)


def logout_user():
    """Log out the current user."""
    try:
        supabase = get_supabase()
        supabase.auth.sign_out()
    except Exception:
        pass
    for key in list(st.session_state.keys()):
        del st.session_state[key]


def get_user_profile(user_id):
    """Get user profile from profiles table."""
    try:
        supabase = get_supabase()
        response = supabase.table("profiles").select("*").eq("id", user_id).single().execute()
        return response.data
    except Exception:
        return None


def check_permission(user_id, project_id, module):
    """Check if user has permission for a module on a project."""
    try:
        profile = get_user_profile(user_id)
        if not profile:
            return False
        if profile.get("role") == "superadmin":
            return True
        supabase = get_supabase()
        response = supabase.table("permissions") \
            .select("*") \
            .eq("user_id", user_id) \
            .eq("project_id", project_id) \
            .eq("module", module) \
            .eq("can_access", True) \
            .execute()
        return len(response.data) > 0
    except Exception:
        return False


def verify_totp(secret, code):
    """Verify a TOTP code."""
    try:
        totp = pyotp.TOTP(secret)
        return totp.verify(code, valid_window=1)
    except Exception:
        return False


def generate_totp_secret():
    """Generate a new TOTP secret."""
    return pyotp.random_base32()


def get_totp_uri(secret, email, issuer="BizReport Pro"):
    """Get the TOTP provisioning URI for QR code generation."""
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=email, issuer_name=issuer)


def is_approved(user_id):
    """Check if user is approved to access the system."""
    profile = get_user_profile(user_id)
    if not profile:
        return False
    return profile.get("is_approved", False)


def get_user_role(user_id):
    """Get the role of a user."""
    profile = get_user_profile(user_id)
    if not profile:
        return "viewer"
    return profile.get("role", "viewer")
