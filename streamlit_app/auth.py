"""Authentication UI and logic using Supabase."""
import os
import streamlit as st
from typing import Optional, Dict, Any
import logging
from supabase import create_client, Client
from datetime import datetime
import json
from streamlit.components.v1 import html

logger = logging.getLogger(__name__)

# Debug mode - can be enabled via environment variable
DEBUG_AUTH = os.getenv("DEBUG_AUTH", "false").lower() in ("true", "1", "yes")


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
    
    def sign_in_with_otp(self, email: str, redirect_to: Optional[str] = None) -> bool:
        """Send magic link to email.
        
        Args:
            email: User email
            redirect_to: URL to redirect to after clicking magic link
            
        Returns:
            True if OTP sent successfully, False otherwise
        """
        try:
            options = {"email": email}
            if redirect_to:
                options["options"] = {"email_redirect_to": redirect_to}
            
            self.supabase.auth.sign_in_with_otp(options)
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
    
    def set_session_from_tokens(self, access_token: str, refresh_token: str) -> Optional[Dict[str, Any]]:
        """Set session from access and refresh tokens.
        
        Args:
            access_token: Access token from URL
            refresh_token: Refresh token from URL
            
        Returns:
            Session data if successful, None otherwise
        """
        try:
            response = self.supabase.auth.set_session(access_token, refresh_token)
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
            logger.error(f"Set session error: {e}")
            return None


def extract_hash_params() -> Dict[str, str]:
    """Extract parameters from URL hash fragment using JavaScript.
    
    Returns:
        Dictionary of parameters from hash fragment
    """
    # JavaScript to extract hash parameters and send them back to Streamlit
    js_code = """
    <script>
    // Function to parse URL hash parameters
    function getHashParams() {
        const hash = window.location.hash.substring(1); // Remove the '#'
        const params = {};
        
        if (hash) {
            hash.split('&').forEach(function(part) {
                const item = part.split('=');
                params[item[0]] = decodeURIComponent(item[1]);
            });
        }
        
        return params;
    }
    
    // Get hash params and store in sessionStorage for Streamlit to access
    const hashParams = getHashParams();
    if (Object.keys(hashParams).length > 0) {
        sessionStorage.setItem('supabase_hash_params', JSON.stringify(hashParams));
        
        // Clear the hash from URL (for security)
        if (window.history.replaceState) {
            window.history.replaceState(null, null, window.location.pathname + window.location.search);
        }
    }
    
    // Send message to parent
    window.parent.postMessage({
        type: 'streamlit:hashParams',
        params: hashParams
    }, '*');
    </script>
    """
    
    # Execute JavaScript
    html(js_code, height=0)
    
    # Try to get params from session storage via query params
    # (This is a workaround since we can't directly access sessionStorage from Python)
    return {}


def handle_magic_link_callback(auth_manager: AuthManager) -> bool:
    """Handle magic link callback by extracting tokens from URL and establishing session.
    
    This function handles both query parameters (?access_token=...) and hash fragments 
    (#access_token=...) which Supabase may use depending on configuration.
    
    Args:
        auth_manager: AuthManager instance
        
    Returns:
        True if callback was handled (tokens found and processed), False otherwise
    """
    debug_info = {
        "timestamp": datetime.now().isoformat(),
        "query_params": {},
        "hash_params": {},
        "session_state": {},
        "callback_detected": False,
        "tokens_found": False,
        "session_created": False,
        "errors": []
    }
    
    try:
        # Extract JavaScript hash parameters (Supabase often uses hash fragments!)
        extract_hash_params()
        
        # Get query parameters
        query_params = dict(st.query_params)
        debug_info["query_params"] = {k: v[:20] + "..." if len(v) > 20 else v 
                                      for k, v in query_params.items()}
        
        if DEBUG_AUTH:
            logger.info(f"🔍 Checking for magic link callback...")
            logger.info(f"🔍 Query params keys: {list(query_params.keys())}")
            logger.info(f"🔍 Full URL query params: {query_params}")
        
        # Check for tokens in query parameters (standard approach)
        access_token = query_params.get("access_token")
        refresh_token = query_params.get("refresh_token")
        token_type = query_params.get("token_type")
        expires_in = query_params.get("expires_in")
        error = query_params.get("error")
        error_description = query_params.get("error_description")
        
        # Check for Supabase-specific hash-based auth tokens
        # Some Supabase configs use #access_token instead of ?access_token
        # We need to check session state in case JavaScript extracted them
        if "supabase_access_token" in st.session_state and not access_token:
            if DEBUG_AUTH:
                logger.info("🔍 Found tokens in session state (from hash fragment)")
            access_token = st.session_state.get("supabase_access_token")
            refresh_token = st.session_state.get("supabase_refresh_token")
            token_type = st.session_state.get("supabase_token_type")
            debug_info["hash_params"] = {"source": "session_state"}
        
        # Log current session state
        debug_info["session_state"] = {
            "authenticated": st.session_state.get("authenticated", False),
            "has_user": st.session_state.get("user") is not None,
            "has_access_token": st.session_state.get("access_token") is not None
        }
        
        # Display debug panel if enabled
        if DEBUG_AUTH:
            with st.sidebar.expander("🔍 Auth Debug Info", expanded=True):
                st.json(debug_info)
        
        # Handle authentication errors
        if error:
            error_msg = f"Magic link authentication error: {error} - {error_description}"
            logger.error(error_msg)
            debug_info["errors"].append(error_msg)
            debug_info["callback_detected"] = True
            
            st.error(f"❌ Authentication failed: {error_description or error}")
            
            if DEBUG_AUTH:
                st.warning(f"**Debug:** Error details: {error}")
            
            # Clear error parameters from URL
            st.query_params.clear()
            
            # Clear hash-based tokens from session state
            for key in ["supabase_access_token", "supabase_refresh_token", "supabase_token_type"]:
                st.session_state.pop(key, None)
            
            st.rerun()
            return True
        
        # Check if we have the required tokens
        if not access_token or not refresh_token:
            if DEBUG_AUTH and (access_token or refresh_token or "access_token" in query_params or 
                              "refresh_token" in query_params):
                logger.warning("⚠️  Incomplete token set detected")
                logger.warning(f"⚠️  access_token present: {bool(access_token)}")
                logger.warning(f"⚠️  refresh_token present: {bool(refresh_token)}")
                debug_info["errors"].append("Incomplete token set")
                
                with st.sidebar.expander("⚠️ Incomplete Tokens", expanded=True):
                    st.warning("Tokens were partially detected but incomplete")
                    st.json({
                        "access_token_present": bool(access_token),
                        "refresh_token_present": bool(refresh_token),
                        "query_params": list(query_params.keys())
                    })
            
            return False
        
        debug_info["callback_detected"] = True
        debug_info["tokens_found"] = True
        
        logger.info("✅ Magic link callback detected, processing tokens...")
        logger.info(f"✅ Access token length: {len(access_token)}")
        logger.info(f"✅ Refresh token length: {len(refresh_token)}")
        logger.info(f"✅ Token type: {token_type}")
        
        if DEBUG_AUTH:
            st.info("🔄 Processing magic link authentication...")
            st.info(f"**Access Token:** {access_token[:20]}... (length: {len(access_token)})")
            st.info(f"**Refresh Token:** {refresh_token[:20]}... (length: {len(refresh_token)})")
        
        # Exchange tokens for session
        with st.spinner("Completing authentication..."):
            try:
                logger.info("🔄 Calling set_session_from_tokens...")
                session_data = auth_manager.set_session_from_tokens(access_token, refresh_token)
                logger.info(f"🔄 set_session_from_tokens returned: {bool(session_data)}")
                
                if session_data:
                    debug_info["session_created"] = True
                    
                    # Store session in Streamlit state
                    st.session_state.authenticated = True
                    st.session_state.user = session_data["user"]
                    st.session_state.access_token = session_data["access_token"]
                    st.session_state.refresh_token = session_data["refresh_token"]
                    st.session_state.expires_at = session_data["expires_at"]
                    
                    user_email = session_data['user'].get('email', 'Unknown')
                    logger.info(f"✅ Magic link authentication successful for user: {user_email}")
                    
                    if DEBUG_AUTH:
                        st.success(f"✅ Authentication successful for: {user_email}")
                        st.json({
                            "user_id": session_data['user'].get('id'),
                            "user_email": user_email,
                            "expires_at": session_data.get('expires_at')
                        })
                    
                    # Clear tokens from URL for security
                    st.query_params.clear()
                    
                    # Clear hash-based tokens from session state
                    for key in ["supabase_access_token", "supabase_refresh_token", "supabase_token_type"]:
                        st.session_state.pop(key, None)
                    
                    # Show success message
                    st.success("✅ Successfully authenticated! Redirecting...")
                    
                    # Rerun to show authenticated interface
                    st.rerun()
                else:
                    error_msg = "set_session_from_tokens returned None"
                    logger.error(f"❌ {error_msg}")
                    debug_info["errors"].append(error_msg)
                    
                    st.error("❌ Failed to complete authentication. Please try again.")
                    
                    if DEBUG_AUTH:
                        st.error("**Debug:** Session creation returned None")
                        st.warning("This might indicate invalid or expired tokens")
                    
                    st.query_params.clear()
                    
                    # Clear hash-based tokens
                    for key in ["supabase_access_token", "supabase_refresh_token", "supabase_token_type"]:
                        st.session_state.pop(key, None)
                    
                    st.rerun()
                    
            except Exception as session_error:
                error_msg = f"Exception in set_session_from_tokens: {str(session_error)}"
                logger.error(error_msg, exc_info=True)
                debug_info["errors"].append(error_msg)
                
                st.error(f"❌ Session creation failed: {str(session_error)}")
                
                if DEBUG_AUTH:
                    st.exception(session_error)
                
                st.query_params.clear()
                
                # Clear hash-based tokens
                for key in ["supabase_access_token", "supabase_refresh_token", "supabase_token_type"]:
                    st.session_state.pop(key, None)
                
                st.rerun()
        
        return True
        
    except Exception as e:
        error_msg = f"Unexpected error in handle_magic_link_callback: {str(e)}"
        logger.error(error_msg, exc_info=True)
        debug_info["errors"].append(error_msg)
        
        st.error(f"❌ Authentication error: {str(e)}")
        
        if DEBUG_AUTH:
            st.exception(e)
            st.json(debug_info)
        
        try:
            st.query_params.clear()
        except:
            pass
        
        # Clear hash-based tokens
        for key in ["supabase_access_token", "supabase_refresh_token", "supabase_token_type"]:
            st.session_state.pop(key, None)
        
        return True


def render_login_ui(auth_manager: AuthManager) -> None:
    """Render the login UI.
    
    Args:
        auth_manager: AuthManager instance
    """
    st.title("🔐 Sign In")
    st.markdown("Sign in to access BigQuery Insights")
    
    # Show debug info if enabled
    if DEBUG_AUTH:
        with st.expander("🔍 Debug: Page Load Info", expanded=False):
            st.info("Debug mode is enabled. Set DEBUG_AUTH=false to disable.")
            st.json({
                "query_params": dict(st.query_params),
                "session_state_keys": list(st.session_state.keys()),
                "authenticated": st.session_state.get("authenticated", False),
                "has_user": st.session_state.get("user") is not None
            })
    
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
        
        # Show redirect URL configuration in debug mode
        if DEBUG_AUTH:
            redirect_url = os.getenv("STREAMLIT_APP_URL", "http://localhost:8501")
            st.warning(f"**Debug:** Redirect URL: `{redirect_url}`")
            st.caption("Set STREAMLIT_APP_URL environment variable to change this.")
        
        with st.form("magic_link_form"):
            email = st.text_input("Email", placeholder="you@example.com", key="magic_email")
            submit = st.form_submit_button("Send Magic Link", use_container_width=True)
            
            if submit:
                if not email:
                    st.error("Please enter your email")
                else:
                    with st.spinner("Sending magic link..."):
                        try:
                            # Get redirect URL - use environment variable or default to localhost
                            redirect_url = os.getenv("STREAMLIT_APP_URL", "http://localhost:8501")
                            
                            logger.info(f"📧 Sending magic link to {email}")
                            logger.info(f"📧 Redirect URL: {redirect_url}")
                            
                            success = auth_manager.sign_in_with_otp(email, redirect_to=redirect_url)
                            if success:
                                st.success("✅ Magic link sent! Check your email inbox.")
                                st.info(f"📬 Make sure to click the link to complete authentication.")
                                
                                if DEBUG_AUTH:
                                    st.info(f"**Debug:** Email sent to {email}")
                                    st.info(f"**Debug:** Link will redirect to: {redirect_url}")
                                    st.warning("**Debug:** Check that this redirect URL matches your Supabase dashboard configuration!")
                            else:
                                st.error("Failed to send magic link. Please try again.")
                                
                                if DEBUG_AUTH:
                                    st.error("**Debug:** sign_in_with_otp returned False")
                        except Exception as e:
                            error_msg = f"Error sending magic link: {str(e)}"
                            st.error(error_msg)
                            logger.error(f"📧 {error_msg}", exc_info=True)
                            
                            if DEBUG_AUTH:
                                st.exception(e)


def check_auth_status(auth_manager: AuthManager) -> bool:
    """Check if user is authenticated and refresh token if needed.
    
    This function:
    1. Checks if user is already authenticated in session state
    2. Attempts to restore session from Supabase if not in session state
    3. Refreshes expired tokens automatically
    
    Args:
        auth_manager: AuthManager instance
        
    Returns:
        True if authenticated, False otherwise
    """
    # If not authenticated in session state, try to restore from Supabase
    if not st.session_state.get("authenticated"):
        try:
            # Try to get existing session from Supabase
            session_data = auth_manager.get_session()
            if session_data and session_data.get("access_token"):
                # Restore session to state
                st.session_state.authenticated = True
                st.session_state.user = session_data.get("user")
                st.session_state.access_token = session_data["access_token"]
                st.session_state.refresh_token = session_data["refresh_token"]
                st.session_state.expires_at = session_data.get("expires_at")
                logger.info("Session restored from Supabase")
                return True
        except Exception as e:
            logger.debug(f"Could not restore session: {e}")
        
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
                        logger.info("Session refreshed successfully")
                        return True
                except Exception as e:
                    logger.error(f"Token refresh failed: {e}")
                    # Clear session
                    for key in ["authenticated", "user", "access_token", "refresh_token", "expires_at"]:
                        st.session_state.pop(key, None)
                    return False
            else:
                # No refresh token, clear session
                for key in ["authenticated", "user", "access_token", "refresh_token", "expires_at"]:
                    st.session_state.pop(key, None)
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
