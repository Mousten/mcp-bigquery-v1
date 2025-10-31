# Magic Link Authentication Testing Checklist

This document provides a comprehensive testing checklist for verifying the magic link authentication flow.

## Prerequisites

Before testing, ensure:
- [ ] Supabase project is configured with:
  - [ ] Email authentication enabled
  - [ ] Redirect URLs configured (e.g., `http://localhost:8501`)
  - [ ] Email templates configured (optional)
- [ ] Environment variables are set in `.env`:
  - [ ] `SUPABASE_URL`
  - [ ] `SUPABASE_KEY`
  - [ ] `SUPABASE_JWT_SECRET`
  - [ ] `STREAMLIT_APP_URL` (optional, auto-detected if not set)
- [ ] MCP server is running: `uv run mcp-bigquery --transport http-stream --port 8000`
- [ ] Streamlit app is running: `streamlit run streamlit_app/app.py`

## Test Cases

### Test 1: Basic Magic Link Flow (Happy Path)

**Steps:**
1. Navigate to `http://localhost:8501`
2. Click on the "Magic Link" tab
3. Enter a valid email address
4. Click "Send Magic Link"
5. Verify success message: "✅ Magic link sent! Check your email inbox."
6. Check email inbox for the magic link
7. Click the link in the email
8. Wait for redirect back to Streamlit app

**Expected Results:**
- [ ] Email is received within 1-2 minutes
- [ ] Magic link redirects to Streamlit app
- [ ] URL briefly shows tokens: `?access_token=...&refresh_token=...`
- [ ] Success message: "✅ Successfully authenticated! Redirecting..."
- [ ] URL is cleaned (no tokens visible)
- [ ] User is redirected to chat interface
- [ ] User email is displayed in account menu

### Test 2: Session Persistence

**Steps:**
1. Complete Test 1 (sign in via magic link)
2. Note the current URL (should be clean)
3. Refresh the page (F5 or Ctrl+R)

**Expected Results:**
- [ ] User remains authenticated after refresh
- [ ] Chat interface is displayed immediately
- [ ] No redirect to sign-in page
- [ ] User email still shows in account menu

### Test 3: Magic Link Expiration

**Steps:**
1. Request a magic link
2. Wait for email to arrive
3. Wait for 60+ minutes (magic links expire after 1 hour by default)
4. Click the expired magic link

**Expected Results:**
- [ ] Error message is displayed
- [ ] URL contains `error` parameter
- [ ] Error is user-friendly
- [ ] User is redirected to sign-in page
- [ ] Can request a new magic link

### Test 4: Invalid/Tampered Token

**Steps:**
1. Request a magic link
2. Open the link in a text editor
3. Modify the `access_token` parameter
4. Open the modified link in browser

**Expected Results:**
- [ ] Error message: "❌ Failed to complete authentication"
- [ ] User is redirected to sign-in page
- [ ] No session is created
- [ ] Can request a new magic link

### Test 5: Multiple Devices

**Steps:**
1. Request magic link on Device A
2. Check email on Device B
3. Click magic link on Device B
4. Return to Device A

**Expected Results:**
- [ ] Device B is authenticated successfully
- [ ] Device A remains at sign-in page (or logs out if previously logged in)
- [ ] Can sign in on Device A using password or new magic link
- [ ] Both devices can be authenticated simultaneously

### Test 6: Sign Out and Re-authenticate

**Steps:**
1. Sign in via magic link (Test 1)
2. Click account menu in top-right
3. Click "🚪 Sign Out"
4. Request new magic link
5. Click link in email

**Expected Results:**
- [ ] Sign out clears all session data
- [ ] User is redirected to sign-in page
- [ ] New magic link works correctly
- [ ] User is signed back in successfully
- [ ] New session is created (different session ID)

### Test 7: Token Refresh on Expiration

**Steps:**
1. Sign in via magic link
2. Wait for access token to expire (default: 1 hour)
3. Perform an action (e.g., send a chat message)

**Expected Results:**
- [ ] Token is automatically refreshed in background
- [ ] User is not logged out
- [ ] Action completes successfully
- [ ] No visible interruption to user

### Test 8: Concurrent Authentication Attempts

**Steps:**
1. Request magic link for same email twice in quick succession
2. Check email for both links
3. Click the first link
4. Click the second link

**Expected Results:**
- [ ] First link authenticates successfully
- [ ] Second link either:
  - [ ] Also authenticates (replaces first session), or
  - [ ] Shows error (already authenticated)
- [ ] No app crashes or errors

### Test 9: Browser Back Button

**Steps:**
1. Sign in via magic link
2. Wait for redirect to chat interface
3. Click browser back button

**Expected Results:**
- [ ] User remains authenticated
- [ ] Does not go back to sign-in page
- [ ] No tokens visible in URL
- [ ] Chat interface remains functional

### Test 10: Direct URL Access After Sign-In

**Steps:**
1. Sign in via magic link
2. Note the clean URL (e.g., `http://localhost:8501/`)
3. Copy the URL
4. Open a new browser tab
5. Paste and navigate to the URL

**Expected Results:**
- [ ] User is authenticated in new tab
- [ ] Chat interface loads immediately
- [ ] No redirect to sign-in page
- [ ] Session is shared across tabs

### Test 11: Production Deployment

**For production testing:**

**Steps:**
1. Deploy app to production environment
2. Update `STREAMLIT_APP_URL` to production URL
3. Update Supabase redirect URLs to include production URL
4. Request magic link using production app
5. Click link in email

**Expected Results:**
- [ ] HTTPS is enforced
- [ ] Magic link redirects to correct production URL
- [ ] Authentication completes successfully
- [ ] Tokens are transmitted securely (HTTPS)
- [ ] URL is cleaned after authentication

### Test 12: Error Handling - Network Issues

**Steps:**
1. Disconnect network/internet
2. Try to request magic link
3. Reconnect network
4. Try again

**Expected Results:**
- [ ] Clear error message when network is down
- [ ] No app crash
- [ ] Can retry after reconnecting
- [ ] Successful on retry

## Security Checks

### Security Test 1: Token Visibility

**Steps:**
1. Complete magic link authentication
2. Check browser history
3. Check browser URL bar

**Expected Results:**
- [ ] Tokens are not in browser history
- [ ] URL is clean (no tokens visible)
- [ ] Tokens are not logged to console

### Security Test 2: Token Storage

**Steps:**
1. Complete magic link authentication
2. Open browser developer tools
3. Check Local Storage
4. Check Session Storage
5. Check Cookies

**Expected Results:**
- [ ] Tokens are NOT in Local Storage
- [ ] Tokens are NOT in Session Storage
- [ ] Tokens are NOT in browser Cookies
- [ ] Tokens are only in Streamlit session state (server-side)

### Security Test 3: URL Parameter Injection

**Steps:**
1. Try to craft URL with fake tokens:
   `http://localhost:8501/?access_token=fake&refresh_token=fake`
2. Navigate to this URL

**Expected Results:**
- [ ] Fake tokens are rejected
- [ ] Error message is displayed
- [ ] User is not authenticated
- [ ] No security vulnerabilities exposed

## Performance Checks

### Performance Test 1: Authentication Speed

**Measure:**
- Time to send magic link: < 2 seconds
- Time to receive email: < 2 minutes
- Time to complete authentication after clicking link: < 3 seconds
- Time to load chat interface: < 2 seconds

### Performance Test 2: Token Refresh Speed

**Measure:**
- Token refresh on expiration: < 1 second
- No user-visible delay
- No chat interruption

## Logging and Debugging

During testing, monitor logs for:

**Expected Log Messages:**
```
INFO - Magic link callback detected, processing tokens...
INFO - Magic link authentication successful for user: user@example.com
INFO - Session restored from Supabase
INFO - Session refreshed successfully
```

**Error Log Messages to Watch For:**
```
ERROR - Magic link authentication error: [error] - [description]
ERROR - Failed to set session from tokens
ERROR - Token refresh failed: [error]
```

## Known Issues and Limitations

1. **Magic Link Expiration**: Links expire after 1 hour (Supabase default)
2. **Email Delivery**: May take 1-2 minutes depending on email provider
3. **Browser Cookies**: Some functionality requires browser cookies to be enabled
4. **Pop-up Blockers**: May interfere with redirects in some browsers
5. **Private Browsing**: Session state may not persist in private/incognito mode

## Troubleshooting Quick Reference

| Issue | Solution |
|-------|----------|
| Magic link not received | Check spam folder, verify email provider settings |
| Authentication fails | Check Supabase redirect URLs, verify tokens not expired |
| Session not persisting | Check browser cookies enabled, verify refresh token valid |
| URL still shows tokens | Hard refresh (Ctrl+Shift+R), check for JavaScript errors |
| Error after clicking link | Check link not expired, verify Supabase configuration |
| Can't sign out | Check network connection, verify Supabase reachable |

## Test Sign-Off

**Tester Name:** ___________________________

**Date:** ___________________________

**Test Results:**
- [ ] All basic tests passed
- [ ] All security tests passed
- [ ] All performance benchmarks met
- [ ] No critical issues found
- [ ] Production-ready

**Notes:**
_____________________________________________
_____________________________________________
_____________________________________________
