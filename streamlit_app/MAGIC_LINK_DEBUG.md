# Magic Link Authentication Debugging Guide

## Overview
This document explains the debugging implementation for magic link authentication in the Streamlit app and how to diagnose issues.

## Problem Analysis

### Root Cause
Magic link authentication can fail for several reasons:

1. **URL Hash Fragments vs Query Parameters**
   - Supabase may return tokens in URL hash fragments (`#access_token=...`) instead of query parameters (`?access_token=...`)
   - Streamlit's `st.query_params` only reads query parameters, NOT hash fragments
   - This is the most common cause of magic link failures

2. **Redirect URL Mismatch**
   - The redirect URL sent with the magic link must exactly match the URL configured in Supabase dashboard
   - Mismatches (including trailing slashes, http vs https, ports) will cause failures

3. **Token Expiration**
   - Tokens may expire before the user clicks the link
   - Network delays can cause timing issues

4. **CORS Issues**
   - Cross-origin requests may be blocked by browser security

## Debug Mode

### Enabling Debug Mode
Set the environment variable:
```bash
export DEBUG_AUTH=true
```

Or add to `.env` file:
```
DEBUG_AUTH=true
```

### Debug Features

When debug mode is enabled, the app provides:

1. **Debug Info Panel** (Sidebar)
   - Shows query parameters
   - Shows session state keys
   - Shows token detection status
   - Shows authentication flow steps

2. **Enhanced Logging**
   - All authentication events are logged with emoji prefixes
   - Token lengths are logged (not the actual tokens)
   - Each step of the callback process is logged

3. **Visual Debug Output**
   - Status messages show what's happening
   - Token information (truncated) is displayed
   - Error details are shown inline

4. **Redirect URL Display**
   - Shows the configured redirect URL
   - Warns if it might not match Supabase config

## Implementation Details

### Hash Fragment Extraction

The implementation includes JavaScript to extract hash fragments:

```javascript
// Extract parameters from URL hash
const hash = window.location.hash.substring(1);
const params = {};
hash.split('&').forEach(function(part) {
    const item = part.split('=');
    params[item[0]] = decodeURIComponent(item[1]);
});
```

These parameters are stored in session storage and checked during callback handling.

### Callback Flow

1. **Page Load**
   - `handle_magic_link_callback()` is called BEFORE auth check
   - Extracts hash fragments using JavaScript
   - Checks query parameters using `st.query_params`

2. **Token Detection**
   - Checks for tokens in query parameters first
   - Falls back to session state (for hash fragments)
   - Logs presence/absence of tokens

3. **Session Creation**
   - Calls `set_session_from_tokens()` with extracted tokens
   - Stores session data in Streamlit session state
   - Clears tokens from URL for security

4. **Rerun**
   - Triggers `st.rerun()` to show authenticated interface
   - Auth check now passes and shows main app

### Debug Information Logged

#### On Every Page Load
- Query parameters present
- Session state keys
- Authenticated status

#### During Magic Link Callback
- Token detection (yes/no)
- Token lengths
- Token types
- Session creation success/failure
- User email on success

#### On Magic Link Send
- Target email address
- Redirect URL
- Send success/failure

## Testing Procedure

### Step 1: Enable Debug Mode
```bash
export DEBUG_AUTH=true
```

### Step 2: Start the App
```bash
streamlit run streamlit_app/app.py
```

### Step 3: Request Magic Link
1. Go to "Magic Link" tab
2. Enter your email
3. Check debug output for redirect URL
4. Verify redirect URL matches Supabase dashboard

### Step 4: Check Email
1. Open the magic link email
2. **DO NOT CLICK YET**
3. Hover over the link and inspect the URL structure
4. Look for:
   - Is it `?access_token=...` (query params) or `#access_token=...` (hash)?
   - Does the base URL match your app?
   - Are there any extra parameters?

### Step 5: Click Magic Link
1. Click the link in the email
2. Watch the debug panel (sidebar)
3. Check the logs

### Step 6: Analyze Results

#### If Successful
- Debug panel shows "tokens_found: true"
- Debug panel shows "session_created: true"
- You're redirected to chat interface
- Console logs show user email

#### If Failed - No Tokens Detected
- Debug panel shows "tokens_found: false"
- Query params are empty
- **Likely cause:** Tokens in hash fragment, JavaScript not extracting them
- **Solution:** Check Supabase auth settings for redirect type

#### If Failed - Session Creation Failed
- Debug panel shows "tokens_found: true" but "session_created: false"
- Error message about invalid tokens
- **Likely cause:** Token expiration or invalid tokens
- **Solution:** Check token validity, try getting a fresh link

#### If Failed - Redirect URL Mismatch
- May not reach the app at all
- Supabase may show error page
- **Likely cause:** Redirect URL mismatch
- **Solution:** Update Supabase dashboard settings

## Supabase Configuration

### Required Settings

1. **Redirect URLs** (Authentication → URL Configuration)
   - Add your Streamlit app URL exactly as it appears
   - Include protocol (http:// or https://)
   - Include port if not standard (e.g., :8501)
   - Example: `http://localhost:8501`

2. **Email Templates** (Authentication → Email Templates)
   - Verify magic link template is enabled
   - Check the redirect URL variable: `{{ .ConfirmationURL }}`

3. **Auth Flow** (Authentication → Providers → Email)
   - Enable "Email" provider
   - Enable "Confirm email" if desired
   - Note the "Redirect Method" setting (query params vs hash)

### Checking Redirect Method

Supabase uses different redirect methods:

- **Query Parameters**: `?access_token=...&refresh_token=...`
  - Works with Streamlit's `st.query_params` directly
  - Recommended for server-side apps

- **Hash Fragment**: `#access_token=...&refresh_token=...`
  - Requires JavaScript extraction
  - Used for client-side apps
  - More secure (not sent to server)

To check which method Supabase is using:
1. Request a magic link
2. Inspect the email link URL
3. Look for `#` or `?` before `access_token`

## Common Issues and Solutions

### Issue 1: Stuck in Login Loop
**Symptoms:** After clicking magic link, redirected back to login page

**Diagnosis:**
- Check debug panel for token detection
- Look for errors in console logs

**Solutions:**
- Enable debug mode to see what's happening
- Verify redirect URL matches Supabase config
- Check if tokens are in hash fragment (look for `#` in URL)
- Try clearing browser cache and cookies

### Issue 2: "Failed to complete authentication"
**Symptoms:** Error message after clicking magic link

**Diagnosis:**
- Debug panel shows tokens found but session creation failed
- Check logs for `set_session_from_tokens` error

**Solutions:**
- Tokens may be expired - request fresh magic link
- Check Supabase service is running
- Verify Supabase keys in environment variables
- Check network connectivity

### Issue 3: Magic Link Not Received
**Symptoms:** No email arrives

**Diagnosis:**
- Check Supabase logs (Dashboard → Authentication → Logs)
- Verify email provider is configured

**Solutions:**
- Check spam folder
- Verify email address is correct
- Check Supabase email rate limits
- Configure SMTP if using custom email

### Issue 4: Redirect to Wrong URL
**Symptoms:** Clicking link goes to wrong address

**Diagnosis:**
- Check email link URL
- Compare with STREAMLIT_APP_URL environment variable

**Solutions:**
- Update STREAMLIT_APP_URL environment variable
- Update Supabase redirect URL settings
- Ensure they match exactly

## Environment Variables

### Required
- `SUPABASE_URL`: Your Supabase project URL
- `SUPABASE_KEY`: Your Supabase anonymous key
- `SUPABASE_JWT_SECRET`: JWT secret for token validation

### Optional
- `STREAMLIT_APP_URL`: Redirect URL for magic links (default: `http://localhost:8501`)
- `DEBUG_AUTH`: Enable debug mode (default: `false`)

### Example `.env` File
```bash
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_KEY=eyJhbGc...
SUPABASE_JWT_SECRET=your-jwt-secret
STREAMLIT_APP_URL=http://localhost:8501
DEBUG_AUTH=true
```

## Debugging Checklist

- [ ] Debug mode enabled (`DEBUG_AUTH=true`)
- [ ] Supabase redirect URL matches app URL exactly
- [ ] Correct environment variables set
- [ ] Magic link email received
- [ ] Link URL inspected (query params vs hash)
- [ ] Debug panel shows token detection
- [ ] Console logs show authentication flow
- [ ] Browser console checked for JavaScript errors
- [ ] Network tab shows Supabase API calls
- [ ] Session state persists after rerun

## Production Deployment

### Before Going Live

1. **Disable Debug Mode**
   ```bash
   export DEBUG_AUTH=false
   ```

2. **Update Redirect URL**
   - Set `STREAMLIT_APP_URL` to production URL
   - Update Supabase dashboard with production URL
   - Use HTTPS in production

3. **Test Thoroughly**
   - Test magic link flow end-to-end
   - Verify redirect works correctly
   - Check that debug info is hidden

4. **Monitor Logs**
   - Watch application logs for errors
   - Check Supabase logs for auth events
   - Set up error alerts if needed

## Additional Resources

- [Supabase Auth Documentation](https://supabase.com/docs/guides/auth)
- [Streamlit Query Parameters](https://docs.streamlit.io/library/api-reference/utilities/st.query_params)
- [Magic Link Best Practices](https://supabase.com/docs/guides/auth/auth-magic-link)

## Support

If you continue to experience issues after following this guide:

1. Enable debug mode
2. Reproduce the issue
3. Save the debug output and logs
4. Check Supabase authentication logs
5. Report with all diagnostic information
