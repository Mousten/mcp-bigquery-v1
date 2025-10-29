"""Authentication UI and logic using Supabase."""
import streamlit as st
from typing import Optional, Dict, Any
import logging
from supabase import create_client, Client
from datetime import datetime

logger = logging.getLogger(__name__)


class AuthManager:
    """Manages authentication with Supabase."""
    
    def __init__(self, supabase_url: str, supabase_key: str):
        """Initialize auth manager.
        
        Args:
            supabase_url: Supabase project URL
            supabase_key: Supabase anonymous key
        """
        self.supabase: Client = create_client(supabase_url, supabase_key)
    
    def sign_in_with_password(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """Sign in with email and password.
        
        Args:
            email: User email
            password: User password
            
        Returns:
            Session data if successful, None otherwise
        """
        try:
            response = self.supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if response and response.session:
                return {
                    "user": response.user.model_dump(),
                    "session": response.session.model_dump(),
                    "access_token": response.session.access_token,
                    "refresh_token": response.session.refresh_token,
                    "expires_at": response.session.expires_at
                }
            return None
        except Exception as e:
            logger.error(f"Sign in error: {e}")
            raise
    
    def sign_in_with_otp(self, email: str) -> bool:
        """Send magic link to email.
        
        Args:
            email: User email
            
        Returns:
            True if OTP sent successfully, False otherwise
        """
        try:
            self.supabase.auth.sign_in_with_otp({
                "email": email
            })
            return True
        except Exception as e:
            logger.error(f"OTP error: {e}")
            raise
    
    def sign_out(self) -> None:
        """Sign out the current user."""
        try:
            self.supabase.auth.sign_out()
        except Exception as e:
            logger.error(f"Sign out error: {e}")
    
    def get_session(self) -> Optional[Dict[str, Any]]:
        """Get current session.
        
        Returns:
            Session data if available, None otherwise
        """
        try:
            response = self.supabase.auth.get_session()
            if response:
                return {
                    "access_token": response.access_token,
                    "refresh_token": response.refresh_token,
                    "expires_at": response.expires_at,
                    "user": response.user.model_dump() if response.user else None
                }
            return None
        except Exception as e:
            logger.error(f"Get session error: {e}")
            return None
    
    def refresh_session(self, refresh_token: str) -> Optional[Dict[str, Any]]:
        """Refresh session with refresh token.
        
        Args:
            refresh_token: Refresh token
            
        Returns:
            New session data if successful, None otherwise
        """
        try:
            response = self.supabase.auth.refresh_session(refresh_token)
            if response and response.session:
                return {
                    "user": response.user.model_dump(),
                    "session": response.session.model_dump(),
                    "access_token": response.session.access_token,
                    "refresh_token": response.session.refresh_token,
                    "expires_at": response.session.expires_at
                }
            return None
        except Exception as e:
            logger.error(f"Refresh session error: {e}")
            return None


def render_login_ui(auth_manager: AuthManager) -> None:
    """Render the login UI.
    
    Args:
        auth_manager: AuthManager instance
    """
    st.title("🔐 Sign In")
    st.markdown("Sign in to access BigQuery Insights")
    
    # Create tabs for different auth methods
    tab1, tab2 = st.tabs(["Email & Password", "Magic Link"])
    
    with tab1:
        st.subheader("Sign in with email and password")
        with st.form("password_login_form"):
            email = st.text_input("Email", placeholder="you@example.com")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Sign In", use_container_width=True)
            
            if submit:
                if not email or not password:
                    st.error("Please enter both email and password")
                else:
                    with st.spinner("Signing in..."):
                        try:
                            session_data = auth_manager.sign_in_with_password(email, password)
                            if session_data:
                                # Store in session state
                                st.session_state.authenticated = True
                                st.session_state.user = session_data["user"]
                                st.session_state.access_token = session_data["access_token"]
                                st.session_state.refresh_token = session_data["refresh_token"]
                                st.session_state.expires_at = session_data["expires_at"]
                                st.success("✅ Signed in successfully!")
                                st.rerun()
                            else:
                                st.error("Sign in failed. Please check your credentials.")
                        except Exception as e:
                            st.error(f"Sign in error: {str(e)}")
    
    with tab2:
        st.subheader("Sign in with magic link")
        st.info("We'll send a magic link to your email. Click the link to sign in.")
        with st.form("magic_link_form"):
            email = st.text_input("Email", placeholder="you@example.com", key="magic_email")
            submit = st.form_submit_button("Send Magic Link", use_container_width=True)
            
            if submit:
                if not email:
                    st.error("Please enter your email")
                else:
                    with st.spinner("Sending magic link..."):
                        try:
                            success = auth_manager.sign_in_with_otp(email)
                            if success:
                                st.success("✅ Magic link sent! Check your email inbox.")
                            else:
                                st.error("Failed to send magic link. Please try again.")
                        except Exception as e:
                            st.error(f"Error sending magic link: {str(e)}")


def check_auth_status(auth_manager: AuthManager) -> bool:
    """Check if user is authenticated and refresh token if needed.
    
    Args:
        auth_manager: AuthManager instance
        
    Returns:
        True if authenticated, False otherwise
    """
    if not st.session_state.get("authenticated"):
        return False
    
    # Check if token is expired
    expires_at = st.session_state.get("expires_at")
    if expires_at:
        # Convert to timestamp for comparison
        now = datetime.now().timestamp()
        if now >= expires_at:
            # Try to refresh
            refresh_token = st.session_state.get("refresh_token")
            if refresh_token:
                try:
                    session_data = auth_manager.refresh_session(refresh_token)
                    if session_data:
                        st.session_state.user = session_data["user"]
                        st.session_state.access_token = session_data["access_token"]
                        st.session_state.refresh_token = session_data["refresh_token"]
                        st.session_state.expires_at = session_data["expires_at"]
                        return True
                except Exception as e:
                    logger.error(f"Token refresh failed: {e}")
                    # Clear session
                    for key in ["authenticated", "user", "access_token", "refresh_token", "expires_at"]:
                        st.session_state.pop(key, None)
                    return False
            else:
                return False
    
    return True


def sign_out(auth_manager: AuthManager) -> None:
    """Sign out the current user.
    
    Args:
        auth_manager: AuthManager instance
    """
    try:
        auth_manager.sign_out()
    except Exception as e:
        logger.error(f"Sign out error: {e}")
    finally:
        # Clear session state
        for key in ["authenticated", "user", "access_token", "refresh_token", "expires_at",
                    "current_session", "chat_sessions", "messages"]:
            st.session_state.pop(key, None)
