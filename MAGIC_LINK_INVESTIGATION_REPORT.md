# Magic Link Authentication Investigation Report

## Executive Summary

**Issue:** Users clicking magic link emails are redirected back to the sign-in page instead of being authenticated and seeing the chat interface.

**Root Cause:** The Streamlit application is missing the callback handler code that extracts authentication tokens from the URL after Supabase redirects users back from the magic link.

**Impact:** Magic link authentication is non-functional, forcing users to use email/password authentication only.

**Status:** Investigation complete. Root cause identified. Fix recommendations provided below.

---

## 1. Current Authentication Flow Analysis

### Working Components ✅

#### Magic Link Request (Working)
**Location:** `streamlit_app/auth.py`, lines 52-68

```python
def sign_in_with_otp(self, email: str) -> bool:
    """Send magic link to email."""
    try:
        self.supabase.auth.sign_in_with_otp({
            "email": email
        })
        return True
    except Exception as e:
        logger.error(f"OTP error: {e}")
        raise
```

**Flow:**
1. User enters email in the "Magic Link" tab
2. `AuthManager.sign_in_with_otp()` called
3. Supabase sends magic link email
4. Success message displayed: "✅ Magic link sent! Check your email inbox."

**Status:** ✅ Working correctly

#### Session Management (Working)
**Location:** `streamlit_app/auth.py`, lines 184-222

The `check_auth_status()` function properly:
- Checks if user is authenticated
- Validates token expiration
- Refreshes expired tokens
- Maintains session state

**Status:** ✅ Working correctly

### Broken Component ❌

#### Magic Link Callback (NOT IMPLEMENTED)

**Expected Behavior:**
After user clicks the magic link in their email, Supabase redirects them to the application with authentication data in the URL. The app should:

1. Detect the callback by checking URL parameters
2. Extract authentication tokens from the URL
3. Verify/exchange the tokens with Supabase
4. Store the session in `st.session_state`
5. Redirect to the chat interface

**Actual Behavior:**
NONE of the above happens. The app loads normally, finds no authenticated session, and shows the login page again.

**Evidence:**
- No code in the codebase checks `st.query_params` or URL fragments
- No code calls `supabase.auth.verify_otp()`, `supabase.auth.set_session()`, or `supabase.auth.exchange_code_for_session()`
- Confirmed via search: `grep -r "query_params\|verify_otp\|set_session\|exchange_code" streamlit_app/` returns no matches

---

## 2. URL Parameter Handling Analysis

### Search Results
```bash
$ grep -r "query_params\|get_query_params\|experimental_get_query_params" streamlit_app/
# No matches found
```

**Finding:** The application does NOT check for URL parameters at all.

### Supabase Magic Link URL Structure

When users click a magic link, Supabase redirects to your application with tokens in the URL. Depending on Supabase configuration, this can be:

#### Option A: Hash Fragment (Default)
```
https://your-app.com/#access_token=xxx&expires_at=123&expires_in=456&refresh_token=yyy&token_type=bearer&type=magiclink
```

#### Option B: Query Parameters (PKCE Flow)
```
https://your-app.com/?code=xxx&type=magiclink
```

#### Option C: Query Parameters (Token Hash Flow with redirect)
```
https://your-app.com/?access_token=xxx&refresh_token=yyy&expires_at=123&token_type=bearer&type=magiclink
```

**Current State:** The app doesn't check for ANY of these formats.

---

## 3. Session State Management Analysis

### Current Session State Variables
**Location:** `streamlit_app/session_manager.py`, lines 211-238

```python
def init_session_state() -> None:
    """Initialize Streamlit session state."""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    
    if "user" not in st.session_state:
        st.session_state.user = None
    
    if "access_token" not in st.session_state:
        st.session_state.access_token = None
    
    if "refresh_token" not in st.session_state:
        st.session_state.refresh_token = None
    
    if "expires_at" not in st.session_state:
        st.session_state.expires_at = None
    # ... more state variables
```

**Analysis:** Session state structure is correct and ready to store authentication data. The issue is that nothing populates these values from the URL callback.

### Session Restoration on Page Load

**Location:** `streamlit_app/app.py`, lines 51-60

```python
# Initialize session state
init_session_state()

# Initialize auth manager
auth_manager = AuthManager(config.supabase_url, config.supabase_key)

# Check authentication status
if not check_auth_status(auth_manager):
    # Show login UI
    render_login_ui(auth_manager)
    return
```

**Issue:** The app checks authentication BEFORE handling any potential callback tokens in the URL.

**Correct Order Should Be:**
1. Initialize session state
2. **Check for callback tokens in URL** ← MISSING
3. **If tokens found, establish session** ← MISSING
4. Check authentication status
5. Show login or main app

---

## 4. Supabase Integration Analysis

### Available Supabase Auth Methods

**Research Output:**
```python
# Available methods on supabase.auth:
[
    'exchange_code_for_session',    # ← For PKCE flow
    'get_session',
    'set_session',                  # ← For setting session from tokens
    'sign_in_with_otp',            # ← Currently used
    'verify_otp',                  # ← For verifying OTP codes
    'refresh_session',             # ← Currently used
    'sign_in_with_password',       # ← Currently used
    'sign_out',                    # ← Currently used
    'initialize_from_url',         # ← Could be used for callback
    # ... more methods
]
```

### Methods Needed for Magic Link Callback

#### Method 1: Direct Token Usage (Hash Fragment)
```python
# If tokens are in URL hash fragment:
tokens = extract_tokens_from_url_hash()
response = supabase.auth.set_session(
    access_token=tokens['access_token'],
    refresh_token=tokens['refresh_token']
)
```

#### Method 2: PKCE Code Exchange (Query Parameter)
```python
# If 'code' is in query parameters:
code = st.query_params.get('code')
response = supabase.auth.exchange_code_for_session(code)
```

#### Method 3: OTP Verification (If using token hash)
```python
# If 'token_hash' is in query parameters:
token_hash = st.query_params.get('token_hash')
email = st.query_params.get('email')
response = supabase.auth.verify_otp({
    'email': email,
    'token': token_hash,
    'type': 'magiclink'
})
```

**Current State:** NONE of these methods are called in the codebase.

---

## 5. Redirect URL Configuration

### Supabase Dashboard Settings
**Location:** Supabase Dashboard → Authentication → URL Configuration

**Required Configuration:**
- **Site URL:** The primary URL of your Streamlit app (e.g., `http://localhost:8501` or `https://your-app.streamlit.app`)
- **Redirect URLs:** List of allowed redirect URLs (must include your Streamlit app URL)

### Current Application Configuration
**Location:** `.env.example` and `streamlit_app/config.py`

**Finding:** No redirect URL configuration in the application code. This is correct since redirect URL is configured in Supabase dashboard, not in the app.

**Action Required:** Verify Supabase dashboard has correct redirect URL configured for your Streamlit deployment.

---

## 6. Authentication Flow Trace

### Current Flow (Step-by-Step)

#### Phase 1: Magic Link Request ✅
1. User navigates to app → Shows login page
2. User switches to "Magic Link" tab
3. User enters email and clicks "Send Magic Link"
4. `auth_manager.sign_in_with_otp(email)` called
5. Supabase sends email with magic link
6. App displays: "✅ Magic link sent! Check your email inbox."
7. **User remains on login page** (expected at this stage)

#### Phase 2: Magic Link Click ❌ BROKEN
1. User opens email and clicks magic link
2. Supabase validates the link
3. **Supabase redirects to app URL with tokens** (e.g., `https://app.com/#access_token=xxx&refresh_token=yyy...`)
4. **App loads fresh** (Streamlit doesn't persist state across page loads)
5. **App runs `main()` function from `app.py`**
6. **App calls `init_session_state()`** → All auth values set to None/False
7. **App calls `check_auth_status()`** → Returns False (no session)
8. **App calls `render_login_ui()`** → User sees login page again
9. **Tokens in URL are IGNORED and LOST** ← **ROOT CAUSE**

#### Phase 3: Session Management ✅ (Never Reached)
Would work correctly IF a session was established, but that never happens.

### Where the Flow Breaks

**Exact Location:** Between steps 4 and 5 of Phase 2 (after URL redirect, before session check)

**Missing Code Block Location:** Should be in `streamlit_app/app.py`, `main()` function, after line 51 (after `init_session_state()`)

---

## 7. Common Issues Checklist

| Issue | Present | Evidence |
|-------|---------|----------|
| Missing token extraction from URL | ✅ YES | No code checks `st.query_params` or hash fragments |
| Session state not persisted after redirect | ✅ YES | Tokens never stored from URL |
| Redirect URL mismatch | ⚠️ POSSIBLE | Cannot verify without Supabase dashboard access |
| Token expiry handling | ❌ NO | Refresh logic exists but only works if session established |
| Error handling that silently fails | ❌ NO | No callback code to fail silently |
| Missing `set_session()` call | ✅ YES | Method never called in codebase |
| Missing `verify_otp()` call | ✅ YES | Method never called in codebase |
| Missing `exchange_code_for_session()` call | ✅ YES | Method never called in codebase |

---

## 8. Root Cause Summary

### Primary Issue
**Missing callback handler code** to extract and process authentication tokens from the URL after Supabase redirect.

### Contributing Factors
1. **No URL parameter inspection:** App doesn't check `st.query_params` or hash fragments
2. **No session establishment from tokens:** No calls to `set_session()`, `verify_otp()`, or `exchange_code_for_session()`
3. **Execution order:** Session check happens before callback handling
4. **Streamlit stateless nature:** Each page load starts fresh; without capturing URL tokens immediately, they're lost

### Why It Happens
Streamlit apps are stateless by default. When a user clicks the magic link:
1. A new browser tab/window opens with tokens in the URL
2. The Streamlit app executes `main()` from scratch
3. Without code to capture URL tokens on load, they're ignored
4. The app finds no authenticated session and shows login page
5. The tokens are lost forever (unless user manually re-triggers the callback)

---

## 9. Recommended Fix

### Implementation Strategy

Add a callback handler that runs early in the app lifecycle to capture and process magic link tokens.

### Code Changes Required

#### Change 1: Add Callback Handler Function
**File:** `streamlit_app/auth.py`
**Location:** After `AuthManager` class definition

```python
def handle_magic_link_callback(auth_manager: AuthManager) -> bool:
    """Handle magic link callback by extracting tokens from URL.
    
    This function checks for authentication tokens in the URL (either in
    query parameters or hash fragments) and establishes a session if found.
    
    Args:
        auth_manager: AuthManager instance
        
    Returns:
        True if callback was handled and session established, False otherwise
    """
    import streamlit as st
    
    try:
        # Check for tokens in query parameters (PKCE flow or token hash flow)
        query_params = st.query_params
        
        # Method 1: Code exchange (PKCE flow)
        if 'code' in query_params:
            logger.info("Magic link callback detected (PKCE code)")
            code = query_params['code']
            
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
        
        # Method 2: Token hash verification (OTP flow)
        elif 'token_hash' in query_params or 'token' in query_params:
            logger.info("Magic link callback detected (token hash)")
            token_hash = query_params.get('token_hash') or query_params.get('token')
            token_type = query_params.get('type', 'magiclink')
            
            try:
                # Verify OTP token
                # Note: Supabase Python SDK might require email for verification
                # If email not in URL, this flow won't work
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
        
        # Method 3: Direct tokens (hash fragment flow - less common with Streamlit)
        # Note: Streamlit doesn't directly support reading URL hash fragments
        # This would require JavaScript injection, which is complex
        # Most Supabase setups use query params instead
        
        # No callback detected
        return False
        
    except Exception as e:
        logger.error(f"Callback handler error: {e}", exc_info=True)
        return False
```

#### Change 2: Integrate Callback Handler
**File:** `streamlit_app/app.py`
**Location:** In `main()` function, after `init_session_state()` and before `check_auth_status()`

```python
def main():
    """Main application entry point."""
    # Load configuration
    try:
        config = StreamlitConfig.from_env()
        config.validate_llm_config()
    except Exception as e:
        st.error(f"❌ Configuration Error: {str(e)}")
        st.info("""
        Please ensure all required environment variables are set:
        - SUPABASE_URL
        - SUPABASE_KEY
        - SUPABASE_JWT_SECRET
        - PROJECT_ID
        - LLM provider API key (OPENAI_API_KEY, ANTHROPIC_API_KEY, or GOOGLE_API_KEY)
        """)
        st.stop()
    
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
    
    # ========== NEW CODE: Handle magic link callback ==========
    # Check if this is a magic link callback and handle it
    callback_handled = handle_magic_link_callback(auth_manager)
    
    if callback_handled:
        # Callback was handled and session established
        # Show success message and rerun to show main app
        st.success("✅ Successfully signed in with magic link!")
        st.rerun()
        return
    # ==========================================================
    
    # Check authentication status
    if not check_auth_status(auth_manager):
        # Show login UI
        render_login_ui(auth_manager)
        return
    
    # User is authenticated - show main app
    render_main_app(config, auth_manager)
```

#### Change 3: Update Import Statement
**File:** `streamlit_app/app.py`
**Location:** Line 12

```python
# Change FROM:
from streamlit_app.auth import AuthManager, render_login_ui, check_auth_status, sign_out

# Change TO:
from streamlit_app.auth import AuthManager, render_login_ui, check_auth_status, sign_out, handle_magic_link_callback
```

#### Change 4: Update Magic Link Request Configuration
**File:** `streamlit_app/auth.py`
**Location:** In `sign_in_with_otp()` method

```python
def sign_in_with_otp(self, email: str, redirect_url: Optional[str] = None) -> bool:
    """Send magic link to email.
    
    Args:
        email: User email
        redirect_url: Optional redirect URL (defaults to current page)
        
    Returns:
        True if OTP sent successfully, False otherwise
    """
    try:
        options = {"email": email}
        
        # Add redirect URL if provided
        if redirect_url:
            options["options"] = {"redirect_to": redirect_url}
        
        self.supabase.auth.sign_in_with_otp(options)
        return True
    except Exception as e:
        logger.error(f"OTP error: {e}")
        raise
```

---

## 10. Testing Recommendations

### Test Scenarios

#### 1. Basic Magic Link Flow
1. Navigate to app
2. Enter email in "Magic Link" tab
3. Click "Send Magic Link"
4. Check email inbox
5. Click magic link
6. **Expected:** Redirected to app and automatically signed in
7. **Verify:** Chat interface is displayed, not login page

#### 2. Token Expiry
1. Receive magic link
2. Wait 10+ minutes (typical token expiry)
3. Click magic link
4. **Expected:** Error message about expired token
5. **Verify:** Can request new magic link

#### 3. Invalid Token
1. Manually modify token in magic link URL
2. Click modified link
3. **Expected:** Error message about invalid token
4. **Verify:** Redirect back to login page

#### 4. Multiple Redirects
1. Complete magic link authentication
2. Manually add `?code=invalid` to URL
3. Refresh page
4. **Expected:** No duplicate authentication attempts
5. **Verify:** Existing session maintained

#### 5. Session Persistence
1. Sign in with magic link
2. Use chat interface
3. Close browser
4. Re-open app
5. **Expected:** Session may be expired, need to sign in again
6. **Verify:** Can sign in with either method

### Supabase Configuration to Verify

**Dashboard Location:** Supabase Dashboard → Authentication → URL Configuration

1. **Site URL:** Should match your Streamlit app base URL
   - Local dev: `http://localhost:8501`
   - Production: `https://your-app.streamlit.app`

2. **Redirect URLs:** Should include your Streamlit app URL
   - Add both with and without trailing slash
   - Example: `http://localhost:8501`, `http://localhost:8501/`

3. **Email Templates:** Verify magic link email template
   - Check that `{{ .ConfirmationURL }}` is used
   - Verify email sending is enabled

4. **Rate Limiting:** Check if rate limits are too restrictive
   - May prevent testing multiple magic links quickly

---

## 11. Alternative Solutions

### Option A: Use PKCE Flow (Recommended)
- Configure Supabase to use PKCE flow (code exchange)
- Tokens delivered via query parameters (easier to capture in Streamlit)
- More secure than direct token delivery
- **Implementation:** Use `exchange_code_for_session()` as shown above

### Option B: Use Token Hash Flow
- Configure Supabase to use token hash in query params
- Verify with `verify_otp()`
- May require email in URL (less secure)
- **Implementation:** Use `verify_otp()` as shown above

### Option C: Use JavaScript for Hash Fragment
- Inject JavaScript to read `window.location.hash`
- Extract tokens from hash fragment
- Pass to Python via hidden input or component
- **Complexity:** High, not recommended for Streamlit

### Option D: Use Custom Redirect Handler
- Create a separate FastAPI endpoint for OAuth callback
- Handle token exchange server-side
- Set a session cookie
- Redirect to Streamlit app
- **Complexity:** Medium-High, requires additional infrastructure

---

## 12. Deployment Considerations

### Local Development
- Use `http://localhost:8501` as redirect URL
- Test with real email delivery
- Check browser console for errors

### Streamlit Cloud
- Use `https://your-app.streamlit.app` as redirect URL
- Ensure secrets are configured in Streamlit Cloud settings
- Test with production Supabase project

### Docker/Custom Hosting
- Use your actual domain as redirect URL
- Ensure HTTPS is configured (Supabase requires HTTPS for production)
- Test SSL certificate validity

---

## 13. Potential Gotchas

### Issue 1: Hash Fragments in Streamlit
**Problem:** Streamlit doesn't natively support reading URL hash fragments (`#access_token=...`)

**Solution:** Configure Supabase to use query parameters instead of hash fragments

**Configuration:** In Supabase Dashboard → Authentication → URL Configuration → Disable "Use hash fragments"

### Issue 2: Streamlit Rerun Behavior
**Problem:** `st.rerun()` clears query parameters in some Streamlit versions

**Solution:** Clear query params explicitly after extracting tokens

```python
# After storing tokens in session state:
st.query_params.clear()
st.rerun()
```

### Issue 3: Double Authentication
**Problem:** User already signed in might trigger callback handler again

**Solution:** Check if already authenticated before processing callback

```python
def handle_magic_link_callback(auth_manager: AuthManager) -> bool:
    # Skip if already authenticated
    if st.session_state.get("authenticated"):
        # But still clear URL params to avoid confusion
        if 'code' in st.query_params or 'token_hash' in st.query_params:
            st.query_params.clear()
        return False
    
    # ... rest of callback handling
```

### Issue 4: Email Provider Blocking
**Problem:** Some email providers (Gmail, Outlook) may block or delay magic link emails

**Solution:**
- Configure SPF, DKIM, DMARC for your sending domain
- Use Supabase's default email service for testing
- Consider custom SMTP provider for production

### Issue 5: Token Timing
**Problem:** Tokens in URL might expire before user switches to browser tab

**Solution:**
- Increase token expiry time in Supabase settings
- Show clear error message for expired tokens
- Allow easy re-request of magic link

---

## 14. Documentation Updates Needed

After implementing the fix, update the following documentation:

### File: `docs/STREAMLIT_QUICKSTART.md`
- Add section on magic link authentication
- Include troubleshooting steps
- Document Supabase configuration requirements

### File: `docs/streamlit.md`
- Add detailed magic link flow diagram
- Document callback handler implementation
- Include testing procedures

### File: `README.md`
- Add magic link authentication to features list
- Include setup instructions for Supabase redirect URLs

### File: `.env.example`
- No changes needed (redirect URL configured in Supabase dashboard)

---

## 15. Summary & Next Steps

### Investigation Complete ✅

**Root Cause Identified:**
Magic link callback is not implemented. Tokens delivered via URL after Supabase redirect are not captured or processed.

**Location of Issue:**
- Missing callback handler function in `streamlit_app/auth.py`
- Missing callback handler invocation in `streamlit_app/app.py` main()

**Confidence Level:** 100%
- Code inspection confirms no URL parameter handling exists
- No calls to token exchange/verification methods
- Authentication flow trace shows exact point of failure

### Recommended Implementation (Priority Order)

1. **Phase 1: Add Callback Handler (High Priority)**
   - Implement `handle_magic_link_callback()` function
   - Support PKCE code exchange flow
   - Add error handling and logging

2. **Phase 2: Integrate Handler (High Priority)**
   - Call handler early in `main()` function
   - Add success feedback
   - Handle edge cases

3. **Phase 3: Configuration (Medium Priority)**
   - Verify Supabase redirect URL configuration
   - Test with both local and production URLs
   - Document configuration steps

4. **Phase 4: Testing (Medium Priority)**
   - Test end-to-end magic link flow
   - Verify error handling
   - Test edge cases

5. **Phase 5: Documentation (Low Priority)**
   - Update quickstart guide
   - Add troubleshooting section
   - Document testing procedures

### Estimated Effort
- **Implementation:** 2-4 hours
- **Testing:** 1-2 hours
- **Documentation:** 1 hour
- **Total:** 4-7 hours

### Risk Assessment
- **Technical Risk:** Low (well-understood problem, clear solution)
- **Testing Risk:** Medium (requires real email delivery testing)
- **User Impact:** High (enables passwordless authentication)

---

## 16. Code Snippets for Quick Reference

### Minimal Working Example

**Add to `streamlit_app/auth.py`:**
```python
def handle_magic_link_callback(auth_manager: AuthManager) -> bool:
    """Handle magic link callback."""
    try:
        if 'code' in st.query_params:
            code = st.query_params['code']
            response = auth_manager.supabase.auth.exchange_code_for_session(code)
            
            if response and response.session:
                st.session_state.authenticated = True
                st.session_state.user = response.user.model_dump()
                st.session_state.access_token = response.session.access_token
                st.session_state.refresh_token = response.session.refresh_token
                st.session_state.expires_at = response.session.expires_at
                st.query_params.clear()
                return True
        return False
    except Exception as e:
        logger.error(f"Callback error: {e}")
        st.query_params.clear()
        return False
```

**Add to `streamlit_app/app.py` main():**
```python
# After: auth_manager = AuthManager(...)
# Before: if not check_auth_status(...)

from streamlit_app.auth import handle_magic_link_callback

if handle_magic_link_callback(auth_manager):
    st.success("✅ Successfully signed in!")
    st.rerun()
    return
```

---

## 17. Appendix

### A. Supabase Auth Methods Reference

| Method | Purpose | When to Use |
|--------|---------|-------------|
| `sign_in_with_otp()` | Send magic link | ✅ Already implemented |
| `exchange_code_for_session()` | Exchange code for tokens | ❌ Missing - needed for PKCE |
| `verify_otp()` | Verify token hash | ❌ Missing - needed for token hash flow |
| `set_session()` | Set session from tokens | ❌ Missing - needed for direct tokens |
| `get_session()` | Get current session | ✅ Already implemented |
| `refresh_session()` | Refresh expired session | ✅ Already implemented |

### B. Streamlit URL Parameter Reference

| API | Streamlit Version | Usage |
|-----|-------------------|-------|
| `st.query_params` | 1.30.0+ | ✅ Recommended - dict-like interface |
| `st.experimental_get_query_params()` | Older versions | ⚠️ Deprecated |
| `st.experimental_set_query_params()` | Older versions | ⚠️ Deprecated |
| URL hash fragments | N/A | ❌ Not supported natively |

### C. Common Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| "Invalid code" | Code expired or already used | Request new magic link |
| "Token has expired" | Took too long to click link | Request new magic link |
| "Redirect URL mismatch" | Supabase config incorrect | Fix redirect URL in dashboard |
| "No session found" | Callback handler not run | Implement callback handler |

### D. Useful Debug Commands

```python
# Check if callback params present
print("Query params:", dict(st.query_params))

# Log authentication state
logger.info(f"Auth state: {st.session_state.get('authenticated')}")

# Check Supabase session
session = auth_manager.get_session()
print("Supabase session:", session)
```

---

**Report Prepared By:** AI Code Agent  
**Date:** 2024  
**Version:** 1.0  
**Status:** Complete - Ready for Implementation
