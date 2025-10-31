# Magic Link Debug - Quick Reference

## 🚀 Quick Start

### Enable Debug Mode
```bash
export DEBUG_AUTH=true
streamlit run streamlit_app/app.py
```

### Check Configuration
```bash
uv run python streamlit_app/test_magic_link.py
```

## 🔍 What to Look For

### ✅ Success Indicators
- Debug panel shows: `"tokens_found": true`
- Debug panel shows: `"session_created": true`
- Console logs show: `✅ Magic link authentication successful`
- User sees chat interface (not login page)

### ❌ Failure Indicators
- Debug panel shows: `"tokens_found": false`
- Error message: "Failed to complete authentication"
- Stuck in login loop after clicking magic link
- Console shows errors with ❌ prefix

## 🐛 Common Issues

### 1. Tokens Not Detected
**Symptom:** `"tokens_found": false` in debug panel

**Likely Cause:** Tokens in hash fragment, not query params

**Fix:**
1. Inspect email link URL
2. Look for `#` vs `?` before `access_token`
3. If using `#`, JavaScript extraction should handle it
4. Check browser console for JS errors

### 2. Session Creation Failed
**Symptom:** `"tokens_found": true` but `"session_created": false`

**Likely Cause:** Invalid or expired tokens

**Fix:**
1. Request fresh magic link
2. Click link immediately
3. Check Supabase service status
4. Verify environment variables are correct

### 3. Redirect URL Mismatch
**Symptom:** Never reach the app after clicking link

**Likely Cause:** Redirect URL mismatch

**Fix:**
1. Check `STREAMLIT_APP_URL` environment variable
2. Compare with Supabase dashboard redirect URLs
3. Ensure exact match (including http/https, port)
4. Update both to match

## 📋 Debug Checklist

- [ ] `DEBUG_AUTH=true` is set
- [ ] App is running
- [ ] Can see debug panel in sidebar
- [ ] Magic link sent successfully
- [ ] Email received
- [ ] Link URL inspected (before clicking)
- [ ] Redirect URL matches Supabase config
- [ ] Click magic link
- [ ] Watch debug panel
- [ ] Check console logs
- [ ] Verify authentication status

## 🔧 Environment Variables

### Required
```bash
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_KEY=eyJhbGc...
SUPABASE_JWT_SECRET=your-jwt-secret
```

### Optional
```bash
STREAMLIT_APP_URL=http://localhost:8501  # Redirect URL
DEBUG_AUTH=true                          # Debug mode
```

## 📊 Debug Panel Fields

| Field | Meaning | Good Value |
|-------|---------|------------|
| `callback_detected` | Magic link callback was triggered | `true` |
| `tokens_found` | Tokens extracted from URL | `true` |
| `session_created` | Session established | `true` |
| `query_params` | URL query parameters | Non-empty if using `?` |
| `hash_params` | Hash fragment parameters | Non-empty if using `#` |
| `errors` | List of errors | Empty `[]` |

## 📝 Console Log Prefixes

| Prefix | Meaning |
|--------|---------|
| 🚀 | Page load |
| 🔑 | Query parameters |
| 🔐 | Authentication status |
| 🔗 | Magic link callback |
| 📧 | Email operations |
| 🔍 | Token detection |
| ✅ | Success |
| ❌ | Error |
| ⚠️  | Warning |
| 🔄 | Processing |

## 🎯 Quick Commands

### View Recent Logs
```bash
# If running in terminal
# Logs will appear inline

# If running in background
tail -f app.log
```

### Test Configuration
```bash
uv run python streamlit_app/test_magic_link.py
```

### Start with Debug
```bash
DEBUG_AUTH=true streamlit run streamlit_app/app.py
```

### Check Environment
```bash
env | grep -E "SUPABASE|STREAMLIT|DEBUG"
```

## 🔗 Token Detection Flow

```
1. Page loads with URL
   ├─ Contains ?access_token=... → Query params ✓
   └─ Contains #access_token=... → Hash fragment
      ├─ JavaScript extracts → sessionStorage
      └─ Python reads → Tokens available ✓

2. handle_magic_link_callback()
   ├─ Check query params
   ├─ Check session state (from JS)
   └─ Extract tokens

3. set_session_from_tokens()
   ├─ Call Supabase API
   ├─ Create session
   └─ Store in st.session_state

4. st.rerun()
   └─ Show authenticated interface ✓
```

## 📞 Getting Help

If still having issues:

1. **Enable debug mode** ✓
2. **Run test script** ✓
3. **Reproduce issue** ✓
4. **Capture:**
   - Debug panel JSON output
   - Console logs (with emoji prefixes)
   - Email link URL structure
   - Supabase configuration
   - Environment variables (redacted)
5. **Review:**
   - MAGIC_LINK_DEBUG.md (detailed guide)
   - DEBUG_SOLUTION.md (implementation details)

## 🎓 Understanding the Flow

### Normal Flow (Working)
```
User enters email
  ↓
Magic link sent
  ↓
User clicks link
  ↓
URL contains tokens (? or #)
  ↓
handle_magic_link_callback() detects tokens
  ↓
set_session_from_tokens() creates session
  ↓
st.session_state.authenticated = True
  ↓
st.rerun() shows main app
  ↓
User sees chat interface ✅
```

### Broken Flow (Not Working)
```
User clicks link
  ↓
URL contains tokens
  ↓
handle_magic_link_callback() doesn't detect tokens ❌
  ↓
Returns False (no callback)
  ↓
check_auth_status() returns False
  ↓
Shows login page ❌
  ↓
User stuck in loop
```

### Debug Flow (With Debugging)
```
User clicks link
  ↓
Debug panel shows query_params
  ↓
Debug panel shows hash extraction
  ↓
Debug panel shows tokens_found: true/false
  ↓
If true: shows session creation status
  ↓
Console logs every step
  ↓
Errors are caught and displayed
  ↓
Can see exactly where it breaks 🔍
```

## 🎨 Visual Debug Indicators

### In UI
- **Sidebar**: "🔍 Auth Debug Info" expander
- **Login Page**: Debug info box (if enabled)
- **Status Messages**: Emoji-prefixed info/error messages

### In Logs
- Lines with emoji prefixes
- Separated by `=` bars
- Structured JSON output

## ⚡ Performance Notes

- Debug mode: Negligible performance impact
- JavaScript extraction: <1ms
- Production (DEBUG_AUTH=false): Zero overhead

## 🔒 Security Notes

- Tokens never logged in full (only lengths)
- Debug mode should be OFF in production
- Tokens cleared from URL after use
- Error details only shown when debug enabled

## 📚 Full Documentation

- **Detailed Guide**: `MAGIC_LINK_DEBUG.md`
- **Implementation**: `DEBUG_SOLUTION.md`
- **Test Script**: `test_magic_link.py`

---

**Remember:** Debug mode shows sensitive information. Always disable in production!
```bash
export DEBUG_AUTH=false  # Before deploying
```
