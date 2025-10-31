# Magic Link Authentication Flow Diagrams

## Current Flow (Broken) ❌

```
┌──────────────────────────────────────────────────────────────────────┐
│                         USER JOURNEY                                  │
└──────────────────────────────────────────────────────────────────────┘

Step 1: Request Magic Link
┌─────────────┐
│   User      │ Opens Streamlit app
│   Browser   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Streamlit   │ Shows login page with "Magic Link" tab
│    App      │
└──────┬──────┘
       │
       │ User enters email, clicks "Send Magic Link"
       │
       ▼
┌─────────────┐
│  Supabase   │ auth.sign_in_with_otp(email)
│    Auth     │
└──────┬──────┘
       │
       │ Sends email with magic link
       │
       ▼
┌─────────────┐
│   Email     │ ✅ "Magic link sent! Check your inbox."
│   Inbox     │
└──────┬──────┘
       │
       │ User clicks link in email
       │
       ▼

Step 2: Magic Link Callback (WHERE IT BREAKS)
┌─────────────┐
│  Supabase   │ Validates magic link
│    Auth     │ Generates access_token, refresh_token
└──────┬──────┘
       │
       │ Redirects to: http://localhost:8501/?code=abc123&type=magiclink
       │
       ▼
┌─────────────┐
│   User      │ ❌ URL has ?code=abc123 but app doesn't read it
│   Browser   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Streamlit   │ 1. App loads fresh (stateless)
│    App      │ 2. init_session_state() → authenticated = False
│   main()    │ 3. check_auth_status() → Returns False
└──────┬──────┘    4. ❌ IGNORES URL PARAMETERS
       │           5. render_login_ui() → Shows login page
       │
       ▼
┌─────────────┐
│   Login     │ ❌ User sees login page again!
│    Page     │    Tokens in URL are lost forever
└─────────────┘    User thinks it didn't work


❌ PROBLEM: No code extracts tokens from URL
❌ RESULT: User stuck on login page
```

---

## Fixed Flow (With Callback Handler) ✅

```
┌──────────────────────────────────────────────────────────────────────┐
│                         USER JOURNEY                                  │
└──────────────────────────────────────────────────────────────────────┘

Step 1: Request Magic Link (Same as before)
┌─────────────┐
│   User      │ Opens Streamlit app
│   Browser   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Streamlit   │ Shows login page with "Magic Link" tab
│    App      │
└──────┬──────┘
       │
       │ User enters email, clicks "Send Magic Link"
       │
       ▼
┌─────────────┐
│  Supabase   │ auth.sign_in_with_otp(email)
│    Auth     │
└──────┬──────┘
       │
       │ Sends email with magic link
       │
       ▼
┌─────────────┐
│   Email     │ ✅ "Magic link sent! Check your inbox."
│   Inbox     │
└──────┬──────┘
       │
       │ User clicks link in email
       │
       ▼

Step 2: Magic Link Callback (NOW FIXED)
┌─────────────┐
│  Supabase   │ Validates magic link
│    Auth     │ Generates access_token, refresh_token
└──────┬──────┘
       │
       │ Redirects to: http://localhost:8501/?code=abc123&type=magiclink
       │
       ▼
┌─────────────┐
│   User      │ ✅ URL has ?code=abc123
│   Browser   │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────┐
│ Streamlit App main()                                            │
│                                                                 │
│ 1. init_session_state()                                        │
│    └─> authenticated = False                                   │
│                                                                 │
│ 2. auth_manager = AuthManager(...)                             │
│                                                                 │
│ 3. ✅ NEW: handle_magic_link_callback(auth_manager)            │
│    │                                                            │
│    ├─> Check st.query_params for 'code'                        │
│    │   └─> Found: 'abc123'                                     │
│    │                                                            │
│    ├─> Call supabase.auth.exchange_code_for_session('abc123') │
│    │   └─> Returns: {session, user, tokens}                    │
│    │                                                            │
│    ├─> Store in st.session_state:                              │
│    │   ├─> authenticated = True                                │
│    │   ├─> user = {...}                                        │
│    │   ├─> access_token = "..."                                │
│    │   ├─> refresh_token = "..."                               │
│    │   └─> expires_at = 1234567890                             │
│    │                                                            │
│    ├─> st.query_params.clear()  # Remove code from URL         │
│    │                                                            │
│    └─> Return True  # Success!                                 │
│                                                                 │
│ 4. Show success message                                         │
│                                                                 │
│ 5. st.rerun()  # Reload app with authenticated session          │
└─────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────┐
│ Streamlit   │ Second run (after rerun):
│    App      │ 1. check_auth_status() → Returns True ✅
│   main()    │ 2. render_main_app() → Shows chat interface ✅
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Chat      │ ✅ User is signed in!
│ Interface   │ ✅ Can ask questions and see results
└─────────────┘


✅ FIXED: Callback handler extracts and processes tokens
✅ RESULT: User automatically signed in
```

---

## Code Execution Comparison

### Before (Broken)

```python
def main():
    config = StreamlitConfig.from_env()
    st.set_page_config(...)
    
    init_session_state()                    # authenticated = False
    auth_manager = AuthManager(...)
    
    # ❌ MISSING: No callback handler here
    
    if not check_auth_status(auth_manager): # Returns False
        render_login_ui(auth_manager)       # ❌ Shows login page
        return                               # Stops here
    
    render_main_app(config, auth_manager)   # ❌ Never reached
```

**Problem:** App goes straight to `check_auth_status()` which returns False because no session exists. The URL parameters with the authentication code are never examined.

---

### After (Fixed)

```python
def main():
    config = StreamlitConfig.from_env()
    st.set_page_config(...)
    
    init_session_state()                    # authenticated = False
    auth_manager = AuthManager(...)
    
    # ✅ NEW: Check for magic link callback
    callback_handled = handle_magic_link_callback(auth_manager)
    if callback_handled:                    # True if tokens found in URL
        st.success("✅ Signed in!")
        st.rerun()                          # Reload with authenticated = True
        return
    
    if not check_auth_status(auth_manager): # Now returns True after rerun
        render_login_ui(auth_manager)
        return
    
    render_main_app(config, auth_manager)   # ✅ Now reached!
```

**Fix:** Before checking authentication status, we first check if this is a callback from a magic link. If so, we extract the code, exchange it for tokens, store the session, and reload the app.

---

## URL Flow Diagram

### Magic Link URL Structure

```
When user clicks magic link in email:

┌─────────────────────────────────────────────────────────────┐
│ Original Email Link (from Supabase)                         │
│ https://your-project.supabase.co/auth/v1/verify?           │
│   token=eyJh...&                                            │
│   type=magiclink&                                           │
│   redirect_to=http://localhost:8501                         │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ Supabase validates
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ Supabase Redirects To (PKCE Flow)                          │
│ http://localhost:8501/?code=abc123&type=magiclink          │
│                                                             │
│ OR (Token Hash Flow)                                        │
│ http://localhost:8501/?token_hash=xyz789&type=magiclink    │
│                                                             │
│ OR (Hash Fragment - less common with Streamlit)            │
│ http://localhost:8501/#access_token=...&refresh_token=...  │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ Streamlit loads
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ Callback Handler Extracts Tokens                           │
│                                                             │
│ st.query_params → {'code': 'abc123', 'type': 'magiclink'} │
│                                                             │
│ exchange_code_for_session('abc123')                        │
│   └─> Returns: access_token, refresh_token, expires_at     │
│                                                             │
│ Store in st.session_state                                   │
│                                                             │
│ st.query_params.clear()                                     │
│   └─> URL becomes: http://localhost:8501/ (clean)          │
└─────────────────────────────────────────────────────────────┘
```

---

## Session State Evolution

```
Timeline of st.session_state values:

┌─────────────────────────────────────────────────────────────┐
│ T0: App First Load (Login Page)                            │
├─────────────────────────────────────────────────────────────┤
│ authenticated: False                                        │
│ user: None                                                  │
│ access_token: None                                          │
│ refresh_token: None                                         │
│ expires_at: None                                            │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ User requests magic link
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ T1: After Clicking "Send Magic Link"                       │
├─────────────────────────────────────────────────────────────┤
│ authenticated: False    (unchanged)                         │
│ user: None              (unchanged)                         │
│ access_token: None      (unchanged)                         │
│ refresh_token: None     (unchanged)                         │
│ expires_at: None        (unchanged)                         │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ User clicks link in email
                           │ URL: /?code=abc123
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ T2: Callback Handler Runs (WITHOUT FIX) ❌                 │
├─────────────────────────────────────────────────────────────┤
│ authenticated: False    (no change - handler missing!)     │
│ user: None              (no change)                         │
│ access_token: None      (no change)                         │
│ refresh_token: None     (no change)                         │
│ expires_at: None        (no change)                         │
│                                                             │
│ Result: Shows login page again                              │
└─────────────────────────────────────────────────────────────┘

                           VS

┌─────────────────────────────────────────────────────────────┐
│ T2: Callback Handler Runs (WITH FIX) ✅                    │
├─────────────────────────────────────────────────────────────┤
│ authenticated: True     ✅ SET BY HANDLER                   │
│ user: {id: "...", email: "user@example.com", ...}          │
│ access_token: "eyJh..."  ✅ FROM SUPABASE                   │
│ refresh_token: "..."     ✅ FROM SUPABASE                   │
│ expires_at: 1234567890   ✅ FROM SUPABASE                   │
│                                                             │
│ Result: Shows chat interface ✅                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Decision Flow Chart

```
┌─────────────────────────────────────────────┐
│         User Arrives at App                 │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
         ┌────────────────┐
         │ Check URL for  │
         │ 'code' or      │◄────┐
         │ 'token_hash'?  │     │
         └────────┬───────┘     │
                  │             │
        ┌─────────┴─────────┐   │
        │                   │   │
       YES                 NO   │
        │                   │   │
        ▼                   │   │
┌────────────────┐          │   │
│ Extract token  │          │   │
│ from URL       │          │   │
└────────┬───────┘          │   │
         │                  │   │
         ▼                  │   │
┌────────────────┐          │   │
│ Exchange with  │          │   │
│ Supabase       │          │   │
└────────┬───────┘          │   │
         │                  │   │
    ┌────┴────┐             │   │
    │         │             │   │
  Valid?   Invalid          │   │
    │         │             │   │
   YES       NO             │   │
    │         │             │   │
    ▼         ▼             │   │
┌────────┐ ┌─────────┐     │   │
│ Store  │ │ Show    │     │   │
│ Session│ │ Error   │     │   │
└───┬────┘ └────┬────┘     │   │
    │           │          │   │
    ▼           │          │   │
┌────────┐      │          │   │
│ Clear  │      │          │   │
│ URL    │      │          │   │
└───┬────┘      │          │   │
    │           │          │   │
    ▼           │          │   │
┌────────┐      │          │   │
│ Rerun  │──────┘          │   │
└────────┘                 │   │
                           │   │
                           ▼   │
                    ┌────────────────┐
                    │ Already        │
                    │ authenticated? │
                    └────────┬───────┘
                             │
                    ┌────────┴────────┐
                    │                 │
                   YES               NO
                    │                 │
                    ▼                 ▼
            ┌────────────┐    ┌────────────┐
            │ Show Chat  │    │ Show Login │
            │ Interface  │    │ Page       │
            └────────────┘    └────────────┘
```

---

## Supabase Configuration Flow

```
┌─────────────────────────────────────────────────────────────┐
│                   Supabase Dashboard                        │
│              Authentication → URL Configuration             │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
          ┌───────────────────┐
          │   Site URL        │
          │ localhost:8501    │
          └───────┬───────────┘
                  │
                  ▼
          ┌───────────────────┐
          │  Redirect URLs    │
          │ localhost:8501    │
          │ (Add to allow)    │
          └───────┬───────────┘
                  │
                  ▼
          ┌───────────────────┐
          │  Email Templates  │
          │ Magic Link: ✓     │
          └───────┬───────────┘
                  │
                  ▼
          ┌───────────────────┐
          │  Auth Settings    │
          │ PKCE: Recommended │
          │ Hash: Alternative │
          └───────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                   IMPORTANT NOTES                           │
├─────────────────────────────────────────────────────────────┤
│ • Redirect URL must match EXACTLY (with/without trailing /) │
│ • HTTPS required for production                             │
│ • localhost OK for development                              │
│ • Test both flows (PKCE and token hash) if unsure          │
└─────────────────────────────────────────────────────────────┘
```

---

## Summary

**The Problem:** Missing callback handler = tokens ignored = user stuck on login page

**The Solution:** Add 3 code blocks (50 lines total) to handle the callback

**The Result:** Magic link works perfectly, passwordless auth enabled ✅
