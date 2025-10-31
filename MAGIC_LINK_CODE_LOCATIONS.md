# Magic Link Fix - Exact Code Locations

This document shows the EXACT locations in the code where changes need to be made to fix the magic link authentication issue.

---

## File 1: `streamlit_app/auth.py`

### Location: Add new function after line 240 (end of file)

**Current code ends at line 240:**
```python
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
```

**Add this NEW FUNCTION after line 240:**

```python


def handle_magic_link_callback(auth_manager: AuthManager) -> bool:
    """Handle magic link callback by extracting tokens from URL.
    
    When a user clicks a magic link in their email, Supabase redirects them
    back to the application with authentication tokens in the URL. This function
    detects the callback, extracts the tokens, and establishes a session.
    
    Supported flows:
    - PKCE flow: code parameter (recommended)
    - Token hash flow: token_hash parameter
    
    Args:
        auth_manager: AuthManager instance
        
    Returns:
        True if callback was handled and session established, False otherwise
    """
    try:
        # Skip if already authenticated (avoid duplicate processing)
        if st.session_state.get("authenticated"):
            # Still clear URL params to avoid confusion
            if 'code' in st.query_params or 'token_hash' in st.query_params or 'token' in st.query_params:
                st.query_params.clear()
            return False
        
        # Method 1: PKCE Code Exchange Flow (Recommended)
        if 'code' in st.query_params:
            logger.info("Magic link callback detected (PKCE code)")
            code = st.query_params['code']
            
            try:
                # Exchange code for session
                response = auth_manager.supabase.auth.exchange_code_for_session(code)
                
                if response and response.session:
                    # Store in session state
                    st.session_state.authenticated = True
                    st.session_state.user = response.user.model_dump()
                    st.session_state.access_token = response.session.access_token
                    st.session_state.refresh_token = response.session.refresh_token
                    st.session_state.expires_at = response.session.expires_at
                    
                    # Clear URL parameters
                    st.query_params.clear()
                    
                    logger.info(f"Magic link authentication successful for user: {response.user.email}")
                    return True
                else:
                    logger.error("Failed to exchange code for session")
                    st.error("❌ Authentication failed. Please try again.")
                    st.query_params.clear()
                    return False
                    
            except Exception as e:
                logger.error(f"Code exchange error: {e}", exc_info=True)
                st.error(f"❌ Authentication error: {str(e)}")
                st.query_params.clear()
                return False
        
        # Method 2: Token Hash Verification Flow
        elif 'token_hash' in st.query_params or 'token' in st.query_params:
            logger.info("Magic link callback detected (token hash)")
            token_hash = st.query_params.get('token_hash') or st.query_params.get('token')
            token_type = st.query_params.get('type', 'magiclink')
            
            try:
                # Verify OTP token
                response = auth_manager.supabase.auth.verify_otp({
                    'token_hash': token_hash,
                    'type': token_type
                })
                
                if response and response.session:
                    # Store in session state
                    st.session_state.authenticated = True
                    st.session_state.user = response.user.model_dump()
                    st.session_state.access_token = response.session.access_token
                    st.session_state.refresh_token = response.session.refresh_token
                    st.session_state.expires_at = response.session.expires_at
                    
                    # Clear URL parameters
                    st.query_params.clear()
                    
                    logger.info(f"Magic link authentication successful for user: {response.user.email}")
                    return True
                else:
                    logger.error("Failed to verify OTP token")
                    st.error("❌ Authentication failed. Please try again.")
                    st.query_params.clear()
                    return False
                    
            except Exception as e:
                logger.error(f"Token verification error: {e}", exc_info=True)
                st.error(f"❌ Authentication error: {str(e)}")
                st.query_params.clear()
                return False
        
        # No callback parameters detected
        return False
        
    except Exception as e:
        logger.error(f"Callback handler error: {e}", exc_info=True)
        return False
```

**Summary for File 1:**
- **Action:** Add new function `handle_magic_link_callback()`
- **Location:** After line 240 (end of file)
- **Lines added:** ~90 lines

---

## File 2: `streamlit_app/app.py`

### Change 1: Update imports (Line 12)

**Current code (line 12):**
```python
from streamlit_app.auth import AuthManager, render_login_ui, check_auth_status, sign_out
```

**Change to:**
```python
from streamlit_app.auth import AuthManager, render_login_ui, check_auth_status, sign_out, handle_magic_link_callback
```

**Summary for Change 1:**
- **Action:** Add `handle_magic_link_callback` to imports
- **Location:** Line 12
- **Lines changed:** 1 line

---

### Change 2: Add callback handler invocation (After Line 54)

**Current code (lines 49-63):**
```python
    # Configure page
    st.set_page_config(
        page_title=config.app_title,
        page_icon=config.app_icon,
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Initialize session state
    init_session_state()
    
    # Initialize auth manager
    auth_manager = AuthManager(config.supabase_url, config.supabase_key)
    
    # Check authentication status
    if not check_auth_status(auth_manager):
        # Show login UI
        render_login_ui(auth_manager)
        return
    
    # User is authenticated - show main app
    render_main_app(config, auth_manager)
```

**Change to (add code between lines 54 and 56):**
```python
    # Configure page
    st.set_page_config(
        page_title=config.app_title,
        page_icon=config.app_icon,
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Initialize session state
    init_session_state()
    
    # Initialize auth manager
    auth_manager = AuthManager(config.supabase_url, config.supabase_key)
    
    # Handle magic link callback
    # This must run BEFORE check_auth_status() to capture tokens from URL
    callback_handled = handle_magic_link_callback(auth_manager)
    if callback_handled:
        # Callback was handled and session established
        # Show success message and rerun to display main app
        st.success("✅ Successfully signed in with magic link!")
        st.rerun()
        return
    
    # Check authentication status
    if not check_auth_status(auth_manager):
        # Show login UI
        render_login_ui(auth_manager)
        return
    
    # User is authenticated - show main app
    render_main_app(config, auth_manager)
```

**Summary for Change 2:**
- **Action:** Add callback handler invocation before auth check
- **Location:** After line 54, before line 56
- **Lines added:** 7 lines

---

## Complete Changes Summary

| File | Location | Action | Lines |
|------|----------|--------|-------|
| `streamlit_app/auth.py` | After line 240 | Add `handle_magic_link_callback()` function | +90 |
| `streamlit_app/app.py` | Line 12 | Update imports | 1 modified |
| `streamlit_app/app.py` | After line 54 | Add callback handler call | +7 |
| **TOTAL** | | | **1 modified, 97 added** |

---

## Line-by-Line Changes for `streamlit_app/app.py`

### Before (Lines 10-20):
```python
 10: sys.path.insert(0, str(Path(__file__).parent.parent))
 11: 
 12: from streamlit_app.config import StreamlitConfig
 13: from streamlit_app.auth import AuthManager, render_login_ui, check_auth_status, sign_out
 14: from streamlit_app.session_manager import SessionManager, init_session_state
 15: from streamlit_app.chat_ui import render_chat_interface
 16: 
 17: # Configure logging
 18: logging.basicConfig(
 19:     level=logging.INFO,
 20:     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
```

### After (Lines 10-20):
```python
 10: sys.path.insert(0, str(Path(__file__).parent.parent))
 11: 
 12: from streamlit_app.config import StreamlitConfig
 13: from streamlit_app.auth import AuthManager, render_login_ui, check_auth_status, sign_out, handle_magic_link_callback  # ← CHANGED
 14: from streamlit_app.session_manager import SessionManager, init_session_state
 15: from streamlit_app.chat_ui import render_chat_interface
 16: 
 17: # Configure logging
 18: logging.basicConfig(
 19:     level=logging.INFO,
 20:     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
```

---

### Before (Lines 49-63):
```python
 49:     # Configure page
 50:     st.set_page_config(
 51:         page_title=config.app_title,
 52:         page_icon=config.app_icon,
 53:         layout="wide",
 54:         initial_sidebar_state="expanded"
 55:     )
 56:     
 57:     # Initialize session state
 58:     init_session_state()
 59:     
 60:     # Initialize auth manager
 61:     auth_manager = AuthManager(config.supabase_url, config.supabase_key)
 62:     
 63:     # Check authentication status
 64:     if not check_auth_status(auth_manager):
 65:         # Show login UI
 66:         render_login_ui(auth_manager)
 67:         return
 68:     
 69:     # User is authenticated - show main app
 70:     render_main_app(config, auth_manager)
```

### After (Lines 49-70):
```python
 49:     # Configure page
 50:     st.set_page_config(
 51:         page_title=config.app_title,
 52:         page_icon=config.app_icon,
 53:         layout="wide",
 54:         initial_sidebar_state="expanded"
 55:     )
 56:     
 57:     # Initialize session state
 58:     init_session_state()
 59:     
 60:     # Initialize auth manager
 61:     auth_manager = AuthManager(config.supabase_url, config.supabase_key)
 62:     
 63:     # Handle magic link callback                                            ← NEW
 64:     # This must run BEFORE check_auth_status() to capture tokens from URL  ← NEW
 65:     callback_handled = handle_magic_link_callback(auth_manager)            ← NEW
 66:     if callback_handled:                                                    ← NEW
 67:         # Callback was handled and session established                      ← NEW
 68:         # Show success message and rerun to display main app                ← NEW
 69:         st.success("✅ Successfully signed in with magic link!")            ← NEW
 70:         st.rerun()                                                          ← NEW
 71:         return                                                               ← NEW
 72:     
 73:     # Check authentication status
 74:     if not check_auth_status(auth_manager):
 75:         # Show login UI
 76:         render_login_ui(auth_manager)
 77:         return
 78:     
 79:     # User is authenticated - show main app
 80:     render_main_app(config, auth_manager)
```

---

## Verification Commands

After making changes, verify with these commands:

```bash
# 1. Check that function was added to auth.py
grep -n "def handle_magic_link_callback" streamlit_app/auth.py

# Expected output:
# 243:def handle_magic_link_callback(auth_manager: AuthManager) -> bool:

# 2. Check that import was updated in app.py
grep -n "handle_magic_link_callback" streamlit_app/app.py

# Expected output:
# 12:from streamlit_app.auth import ... handle_magic_link_callback
# 65:    callback_handled = handle_magic_link_callback(auth_manager)

# 3. Count total lines added
wc -l streamlit_app/auth.py streamlit_app/app.py

# Expected: auth.py should have ~330 lines (was 240, added ~90)
#           app.py should have ~237 lines (was 230, added ~7)

# 4. Test syntax
python3 -m py_compile streamlit_app/auth.py
python3 -m py_compile streamlit_app/app.py

# Expected: No output means syntax is correct
```

---

## Testing Checklist

After making code changes:

- [ ] Code syntax is valid (no Python errors)
- [ ] Function `handle_magic_link_callback` exists in `auth.py`
- [ ] Function is imported in `app.py`
- [ ] Function is called before `check_auth_status()`
- [ ] Start app: `streamlit run streamlit_app/app.py`
- [ ] Request magic link
- [ ] Click link in email
- [ ] Verify auto-login works
- [ ] Check browser console for errors
- [ ] Check Streamlit logs for "Magic link callback detected"

---

## Troubleshooting

### Error: `NameError: name 'handle_magic_link_callback' is not defined`
**Cause:** Function not imported in `app.py`  
**Fix:** Add `handle_magic_link_callback` to line 12 imports

### Error: `AttributeError: 'SyncAuthClient' has no attribute 'exchange_code_for_session'`
**Cause:** Supabase Python client version too old  
**Fix:** Update supabase: `pip install --upgrade supabase`

### Still redirects to login page
**Cause:** Supabase redirect URL not configured  
**Fix:** Add your app URL to Supabase Dashboard → Auth → Redirect URLs

### Error: "Invalid code"
**Cause:** Code already used or expired  
**Fix:** Request new magic link, click within 60 seconds

### No callback detected in logs
**Cause:** URL doesn't have code/token parameters  
**Fix:** Check Supabase configuration, may need to enable PKCE flow

---

## Quick Copy-Paste Guide

### For `streamlit_app/auth.py` - Append to end of file:

```python


def handle_magic_link_callback(auth_manager: AuthManager) -> bool:
    """Handle magic link callback by extracting tokens from URL."""
    try:
        if st.session_state.get("authenticated"):
            if 'code' in st.query_params or 'token_hash' in st.query_params or 'token' in st.query_params:
                st.query_params.clear()
            return False
        
        if 'code' in st.query_params:
            logger.info("Magic link callback detected (PKCE code)")
            code = st.query_params['code']
            try:
                response = auth_manager.supabase.auth.exchange_code_for_session(code)
                if response and response.session:
                    st.session_state.authenticated = True
                    st.session_state.user = response.user.model_dump()
                    st.session_state.access_token = response.session.access_token
                    st.session_state.refresh_token = response.session.refresh_token
                    st.session_state.expires_at = response.session.expires_at
                    st.query_params.clear()
                    logger.info(f"Magic link auth successful: {response.user.email}")
                    return True
                else:
                    st.error("❌ Authentication failed. Please try again.")
                    st.query_params.clear()
                    return False
            except Exception as e:
                logger.error(f"Code exchange error: {e}", exc_info=True)
                st.error(f"❌ Authentication error: {str(e)}")
                st.query_params.clear()
                return False
        
        elif 'token_hash' in st.query_params or 'token' in st.query_params:
            logger.info("Magic link callback detected (token hash)")
            token_hash = st.query_params.get('token_hash') or st.query_params.get('token')
            token_type = st.query_params.get('type', 'magiclink')
            try:
                response = auth_manager.supabase.auth.verify_otp({
                    'token_hash': token_hash,
                    'type': token_type
                })
                if response and response.session:
                    st.session_state.authenticated = True
                    st.session_state.user = response.user.model_dump()
                    st.session_state.access_token = response.session.access_token
                    st.session_state.refresh_token = response.session.refresh_token
                    st.session_state.expires_at = response.session.expires_at
                    st.query_params.clear()
                    logger.info(f"Magic link auth successful: {response.user.email}")
                    return True
                else:
                    st.error("❌ Authentication failed. Please try again.")
                    st.query_params.clear()
                    return False
            except Exception as e:
                logger.error(f"Token verification error: {e}", exc_info=True)
                st.error(f"❌ Authentication error: {str(e)}")
                st.query_params.clear()
                return False
        
        return False
    except Exception as e:
        logger.error(f"Callback handler error: {e}", exc_info=True)
        return False
```

### For `streamlit_app/app.py` - Line 12:
Replace the import line with:
```python
from streamlit_app.auth import AuthManager, render_login_ui, check_auth_status, sign_out, handle_magic_link_callback
```

### For `streamlit_app/app.py` - After line 61:
Insert these lines:
```python
    
    # Handle magic link callback
    callback_handled = handle_magic_link_callback(auth_manager)
    if callback_handled:
        st.success("✅ Successfully signed in with magic link!")
        st.rerun()
        return
```

---

**That's it! Three simple changes to fix magic link authentication.**
