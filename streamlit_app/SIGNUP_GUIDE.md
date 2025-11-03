# Sign-Up Functionality Guide

## Overview

The Streamlit UI now includes comprehensive sign-up functionality that allows new users to create accounts before signing in. This guide explains how to use the sign-up feature and its configuration.

## Features

### 1. Sign-Up UI

- **Mode Selection**: Users can toggle between "Sign In" and "Sign Up" modes using radio buttons
- **Clean Interface**: Clear visual distinction between sign-up and sign-in modes
- **Form Fields**:
  - Email address (required, validated)
  - Password (required, with strength validation)
  - Confirm password (required, must match)

### 2. Password Validation

The sign-up process enforces password requirements:

- **Minimum 8 characters**
- **At least one uppercase letter**
- **At least one lowercase letter**
- **At least one number**
- Special characters optional but recommended for stronger passwords

### 3. Real-Time Feedback

- **Password Strength Indicator**: Shows "Weak", "Medium", or "Strong" with color coding
- **Requirements Display**: Expandable section showing all password requirements
- **Validation Errors**: Clear error messages for:
  - Invalid email format
  - Weak passwords with specific requirements not met
  - Password mismatch
  - Email already registered

### 4. Email Confirmation Flow

The sign-up process supports both email confirmation modes:

#### With Email Confirmation Disabled (Default Development)
- User account is created immediately
- User is automatically signed in
- Redirected to main application

#### With Email Confirmation Enabled (Production)
- User account is created
- Confirmation email is sent to the user
- User must click the confirmation link in their email
- After confirmation, user can sign in normally

### 5. Error Handling

Comprehensive error handling for:
- **Email already exists**: Friendly message suggesting to sign in instead
- **Invalid email format**: Client-side validation before submission
- **Weak password**: Displays specific requirements not met
- **Password mismatch**: Immediate feedback
- **Network errors**: User-friendly error messages
- **Supabase API errors**: Graceful error handling with actionable messages

## Usage

### For Users

1. **Navigate to the Sign-Up Page**
   - Open the Streamlit app
   - Select "Sign Up" from the mode toggle

2. **Fill in the Form**
   - Enter your email address
   - Choose a strong password (check the strength indicator)
   - Confirm your password
   - Review password requirements if needed

3. **Submit**
   - Click "Create Account"
   - Wait for account creation

4. **Next Steps**
   - **If auto-login enabled**: You'll be automatically signed in and redirected to the main app
   - **If email confirmation required**: Check your email for a confirmation link, then sign in

### For Developers

#### Configuration

Sign-up functionality works with your existing Supabase configuration:

```python
# Environment variables (in .env file)
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key
SUPABASE_JWT_SECRET=your_jwt_secret
```

#### Email Confirmation Settings

Configure in your Supabase Dashboard:
1. Go to Authentication > Settings
2. Under "Email Auth", toggle "Enable email confirmations"
3. Customize email templates under "Email Templates"

#### Password Policy

Configure in Supabase Dashboard:
1. Go to Authentication > Policies  
2. Adjust password requirements (Supabase enforces minimum 6 characters by default)
3. Our client-side validation enforces stricter rules (8+ characters, mixed case, numbers)

## Code Structure

### Main Components

1. **`AuthManager.sign_up()`** (`auth.py`)
   - Handles sign-up API calls to Supabase
   - Returns user and session data
   - Handles metadata for user profiles

2. **`validate_email()`** (`auth.py`)
   - Email format validation using regex
   - Returns validation status and error message

3. **`validate_password()`** (`auth.py`)
   - Password strength validation
   - Returns validation status and list of errors

4. **`get_password_strength()`** (`auth.py`)
   - Calculates password strength score
   - Returns strength level and color for UI display

5. **`render_signup_ui()`** (`auth.py`)
   - Renders the sign-up form
   - Handles form submission and validation
   - Manages auto-login or confirmation flow

6. **`render_login_ui()`** (`auth.py`)
   - Updated to include mode selection (Sign In / Sign Up)
   - Routes to appropriate UI based on selection

## Security Considerations

1. **Password Masking**: All password fields use `type="password"` to mask input
2. **Client-Side Validation**: Validates before sending to server
3. **Server-Side Validation**: Supabase enforces additional validation
4. **No Password Display**: Passwords never displayed in logs or UI
5. **Email Enumeration Protection**: Same messages for existing/new emails when appropriate
6. **Secure Transport**: All communication over HTTPS (when deployed)

## Testing

### Manual Testing Checklist

- [ ] Sign up with valid email and strong password
- [ ] Sign up with existing email (should show appropriate error)
- [ ] Sign up with invalid email format
- [ ] Sign up with weak password (should show validation errors)
- [ ] Sign up with mismatched passwords
- [ ] Password strength indicator shows correct levels
- [ ] Email confirmation flow (if enabled)
- [ ] Auto-sign-in flow (if email confirmation disabled)
- [ ] Switch between Sign In and Sign Up modes
- [ ] All error messages are clear and actionable

### Automated Testing

Run validation tests:
```bash
uv run python -c "
from streamlit_app.auth import validate_email, validate_password, get_password_strength

# Test email validation
assert validate_email('test@example.com')[0] == True
assert validate_email('invalid-email')[0] == False

# Test password validation
assert validate_password('Test1234')[0] == True
assert validate_password('weak')[0] == False

print('✅ All tests passed')
"
```

## Troubleshooting

### Issue: Sign-up button doesn't respond
- Check browser console for JavaScript errors
- Verify Supabase URL and keys are correct
- Check network tab for failed API calls

### Issue: Email confirmation not sending
- Verify email templates are configured in Supabase
- Check Supabase dashboard for email delivery status
- Ensure SMTP is properly configured in Supabase

### Issue: Auto-login not working
- Check if email confirmation is enabled in Supabase
- Verify session state is being set correctly
- Check browser console for session errors

### Issue: Password validation too strict/lenient
- Adjust validation rules in `validate_password()` function
- Update password requirements display to match
- Consider Supabase password policy settings

## Future Enhancements

Potential improvements for future iterations:

1. **Social Sign-Up**: Add OAuth providers (Google, GitHub, etc.)
2. **Profile Fields**: Add optional fields during sign-up (name, company, etc.)
3. **Terms of Service**: Add checkbox for ToS acceptance
4. **Captcha**: Add reCAPTCHA for bot prevention
5. **Password Visibility Toggle**: Add eye icon to show/hide password
6. **Rate Limiting**: Implement client-side rate limiting for sign-up attempts
7. **Email Verification Resend**: Add button to resend confirmation email
8. **Custom Redirects**: Allow custom redirect URLs after sign-up

## Support

For issues or questions:
1. Check Supabase logs for API errors
2. Review Streamlit logs for application errors
3. Verify environment variables are set correctly
4. Check that Supabase email auth is enabled

## Related Documentation

- [Supabase Auth Documentation](https://supabase.com/docs/guides/auth)
- [Streamlit Forms Documentation](https://docs.streamlit.io/library/api-reference/control-flow/st.form)
- [Password Security Best Practices](https://www.owasp.org/index.php/Authentication_Cheat_Sheet)
