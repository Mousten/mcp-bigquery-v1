# Magic Link Authentication Setup

This document explains how to configure and use magic link authentication in the BigQuery Insights Streamlit app.

## Overview

Magic link authentication allows users to sign in by clicking a link sent to their email, without needing to remember a password. The implementation uses Supabase Auth with proper token handling and session management.

## How It Works

1. **User Requests Magic Link**: User enters their email in the Streamlit UI
2. **Email Sent**: Supabase sends an email with a magic link to the user
3. **User Clicks Link**: The link redirects to the Streamlit app with auth tokens in the URL
4. **Token Exchange**: The app extracts tokens from the URL and establishes a session
5. **Session Storage**: Session data is stored in Streamlit state and persists across reloads
6. **URL Cleanup**: Tokens are removed from the browser URL for security

## Supabase Configuration

### 1. Configure Redirect URLs

In your Supabase project dashboard:

1. Go to **Authentication** → **URL Configuration**
2. Add your Streamlit app URLs to the **Redirect URLs** list:
   - Development: `http://localhost:8501`
   - Production: `https://your-app-domain.com`

### 2. Enable Email Auth

1. Go to **Authentication** → **Providers**
2. Ensure **Email** provider is enabled
3. Configure email templates if desired (optional)

### 3. Email Template Customization (Optional)

You can customize the magic link email template:

1. Go to **Authentication** → **Email Templates**
2. Edit the **Magic Link** template
3. Customize subject, body, and branding

## Environment Variables

Add the following to your `.env` file:

```bash
# Required for all authentication
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_JWT_SECRET=your-jwt-secret

# Optional: Explicitly set Streamlit app URL for magic link redirects
# If not set, the app will auto-detect the URL
STREAMLIT_APP_URL=http://localhost:8501  # or https://your-production-url.com
```

### URL Configuration Priority

The app determines the redirect URL in this order:

1. `STREAMLIT_APP_URL` environment variable (if set)
2. Auto-detected from request headers (works in most deployments)
3. Fallback to `http://localhost:8501` for local development

## Usage

### For Users

1. Navigate to the Streamlit app
2. Click the **"Magic Link"** tab in the sign-in page
3. Enter your email address
4. Click **"Send Magic Link"**
5. Check your email inbox for the magic link
6. Click the link in the email
7. You'll be automatically signed in and redirected to the chat interface

### Testing the Flow

To test magic link authentication:

```bash
# 1. Start the MCP server
uv run mcp-bigquery --transport http-stream --port 8000

# 2. Start the Streamlit app
streamlit run streamlit_app/app.py

# 3. Navigate to http://localhost:8501
# 4. Use the Magic Link tab to request a link
# 5. Check your email and click the link
```

## Troubleshooting

### Magic Link Not Working

**Symptom**: Clicking the magic link redirects to sign-in page instead of authenticating

**Solutions**:
1. Verify redirect URL is configured in Supabase dashboard
2. Check that the URL in the email matches your Streamlit app URL exactly
3. Ensure no browser extensions are blocking redirects
4. Check browser console for errors

### Tokens Not Detected

**Symptom**: URL has tokens but authentication doesn't complete

**Check**:
1. URL should contain `access_token` and `refresh_token` parameters
2. Check browser console and Streamlit logs for errors
3. Verify Supabase project is correctly configured

### Session Not Persisting

**Symptom**: User is logged out on page reload

**Solutions**:
1. Check that session state is being stored correctly
2. Verify token expiration times
3. Check refresh token is valid
4. Review browser console for storage errors

### Email Not Received

**Symptom**: Magic link email never arrives

**Solutions**:
1. Check email spam/junk folder
2. Verify email provider settings in Supabase
3. Check Supabase logs for email delivery status
4. Ensure user exists or sign-up is enabled

### Authentication Errors in URL

**Symptom**: URL contains `error` parameter after clicking magic link

**Common Errors**:
- `invalid_request`: Magic link may have expired (links expire after 1 hour by default)
- `access_denied`: User may not have permission or email verification failed
- `unauthorized_client`: Redirect URL may not be configured correctly

**Solutions**:
1. Request a new magic link
2. Verify user has access to the application
3. Check Supabase authentication settings

## Security Considerations

### Token Handling

- **URL Cleanup**: Tokens are immediately removed from the browser URL after processing
- **Secure Storage**: Tokens are stored in Streamlit session state (server-side)
- **No Client-Side Storage**: Tokens are never stored in browser local storage or cookies
- **HTTPS Required**: Production deployments must use HTTPS to protect tokens in transit

### Session Management

- **Automatic Refresh**: Expired access tokens are automatically refreshed using refresh tokens
- **Graceful Expiry**: Users are redirected to sign-in page if refresh fails
- **Logout Cleanup**: All session data is cleared on sign-out

### Best Practices

1. **Always use HTTPS in production** to protect tokens during redirect
2. **Configure short magic link expiry** (default 1 hour is recommended)
3. **Enable email verification** if required for your security policy
4. **Monitor authentication logs** in Supabase dashboard
5. **Set token expiry appropriately** (default 1 hour for access tokens)

## Architecture

### Authentication Flow

```
┌─────────────┐
│   User      │
└──────┬──────┘
       │ 1. Enter email
       ▼
┌─────────────────────┐
│  Streamlit App      │
│  (Magic Link Form)  │
└──────┬──────────────┘
       │ 2. Request magic link with redirect_url
       ▼
┌─────────────────────┐
│  Supabase Auth      │
│  (send_magic_link)  │
└──────┬──────────────┘
       │ 3. Send email with link
       ▼
┌─────────────────────┐
│  User Email         │
└──────┬──────────────┘
       │ 4. Click link
       ▼
┌─────────────────────────────────────────┐
│  Streamlit App                          │
│  URL: app.com?access_token=...&         │
│                refresh_token=...        │
└──────┬──────────────────────────────────┘
       │ 5. Extract tokens from URL
       ▼
┌─────────────────────┐
│  Supabase Auth      │
│  (set_session)      │
└──────┬──────────────┘
       │ 6. Establish session
       ▼
┌─────────────────────┐
│  Streamlit State    │
│  (store tokens)     │
└──────┬──────────────┘
       │ 7. Clear URL params
       ▼
┌─────────────────────┐
│  Chat Interface     │
│  (authenticated)    │
└─────────────────────┘
```

### Code Flow

1. **`AuthManager.sign_in_with_otp()`**: Sends magic link with redirect URL
2. **`handle_magic_link_callback()`**: Detects and processes URL tokens
3. **`AuthManager.set_session_from_tokens()`**: Exchanges tokens for session
4. **`check_auth_status()`**: Validates session and refreshes if needed
5. **Streamlit state**: Persists session across page interactions

## Implementation Details

### Files Modified

- **`streamlit_app/auth.py`**:
  - Added `set_session_from_tokens()` method
  - Added `handle_magic_link_callback()` function
  - Updated `sign_in_with_otp()` to accept redirect URL
  - Enhanced `check_auth_status()` for session restoration
  - Updated `render_login_ui()` to auto-detect redirect URL

- **`streamlit_app/app.py`**:
  - Added callback handling before authentication check
  - Imports `handle_magic_link_callback()`

### Token Exchange

The token exchange process:

```python
# 1. Extract tokens from URL
query_params = st.query_params
access_token = query_params.get("access_token")
refresh_token = query_params.get("refresh_token")

# 2. Exchange with Supabase
session_data = auth_manager.set_session_from_tokens(access_token, refresh_token)

# 3. Store in session state
st.session_state.authenticated = True
st.session_state.user = session_data["user"]
st.session_state.access_token = session_data["access_token"]
st.session_state.refresh_token = session_data["refresh_token"]

# 4. Clean URL
st.query_params.clear()
st.rerun()
```

### Session Persistence

Sessions persist through:

1. **Streamlit State**: Primary storage during active session
2. **Session Restoration**: Attempts to restore from Supabase on page reload
3. **Token Refresh**: Automatically refreshes expired access tokens

## API Reference

### `AuthManager.sign_in_with_otp(email, redirect_to)`

Sends a magic link to the specified email.

**Parameters**:
- `email` (str): User's email address
- `redirect_to` (str, optional): URL to redirect to after clicking magic link

**Returns**: `bool` - True if email sent successfully

**Example**:
```python
success = auth_manager.sign_in_with_otp(
    email="user@example.com",
    redirect_to="https://my-app.com"
)
```

### `AuthManager.set_session_from_tokens(access_token, refresh_token)`

Exchanges URL tokens for a Supabase session.

**Parameters**:
- `access_token` (str): Access token from URL
- `refresh_token` (str): Refresh token from URL

**Returns**: `Dict[str, Any]` - Session data including user info and tokens

**Example**:
```python
session_data = auth_manager.set_session_from_tokens(
    access_token="eyJ...",
    refresh_token="abc..."
)
```

### `handle_magic_link_callback(auth_manager)`

Handles the complete magic link callback flow.

**Parameters**:
- `auth_manager` (AuthManager): AuthManager instance

**Returns**: `bool` - True if callback was handled (tokens found)

**Example**:
```python
if handle_magic_link_callback(auth_manager):
    return  # Callback handled, function will rerun
```

## Additional Resources

- [Supabase Auth Documentation](https://supabase.com/docs/guides/auth)
- [Streamlit Session State](https://docs.streamlit.io/library/api-reference/session-state)
- [Supabase Magic Links](https://supabase.com/docs/guides/auth/auth-magic-link)
