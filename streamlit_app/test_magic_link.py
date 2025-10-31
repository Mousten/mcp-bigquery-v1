"""
Test script for magic link authentication debugging.
This script simulates the magic link flow and validates the implementation.
"""
import os
import sys
from pathlib import Path
import logging

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from streamlit_app.auth import AuthManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_auth_manager_initialization():
    """Test that AuthManager can be initialized."""
    print("\n" + "=" * 80)
    print("TEST 1: AuthManager Initialization")
    print("=" * 80)
    
    try:
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        
        if not supabase_url or not supabase_key:
            print("❌ FAILED: Missing SUPABASE_URL or SUPABASE_KEY environment variables")
            return False
        
        auth_manager = AuthManager(supabase_url, supabase_key)
        print("✅ PASSED: AuthManager initialized successfully")
        print(f"   Supabase URL: {supabase_url}")
        return True
    except Exception as e:
        print(f"❌ FAILED: {str(e)}")
        return False


def test_otp_send():
    """Test sending OTP (magic link)."""
    print("\n" + "=" * 80)
    print("TEST 2: Send Magic Link")
    print("=" * 80)
    
    try:
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        test_email = os.getenv("TEST_EMAIL")
        
        if not test_email:
            print("⚠️  SKIPPED: No TEST_EMAIL environment variable set")
            print("   Set TEST_EMAIL to run this test")
            return None
        
        auth_manager = AuthManager(supabase_url, supabase_key)
        redirect_url = os.getenv("STREAMLIT_APP_URL", "http://localhost:8501")
        
        print(f"   Email: {test_email}")
        print(f"   Redirect URL: {redirect_url}")
        
        success = auth_manager.sign_in_with_otp(test_email, redirect_to=redirect_url)
        
        if success:
            print("✅ PASSED: Magic link sent successfully")
            print(f"   Check {test_email} for the magic link")
            print(f"   The link should redirect to: {redirect_url}")
            return True
        else:
            print("❌ FAILED: Failed to send magic link")
            return False
    except Exception as e:
        print(f"❌ FAILED: {str(e)}")
        logger.exception("Exception in test_otp_send")
        return False


def test_session_methods():
    """Test session-related methods."""
    print("\n" + "=" * 80)
    print("TEST 3: Session Methods")
    print("=" * 80)
    
    try:
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        
        auth_manager = AuthManager(supabase_url, supabase_key)
        
        # Test get_session (should return None if not authenticated)
        session = auth_manager.get_session()
        print(f"   get_session() result: {bool(session)}")
        
        print("✅ PASSED: Session methods work")
        return True
    except Exception as e:
        print(f"❌ FAILED: {str(e)}")
        logger.exception("Exception in test_session_methods")
        return False


def test_environment_variables():
    """Test that all required environment variables are set."""
    print("\n" + "=" * 80)
    print("TEST 4: Environment Variables")
    print("=" * 80)
    
    required_vars = {
        "SUPABASE_URL": os.getenv("SUPABASE_URL"),
        "SUPABASE_KEY": os.getenv("SUPABASE_KEY"),
        "SUPABASE_JWT_SECRET": os.getenv("SUPABASE_JWT_SECRET"),
    }
    
    optional_vars = {
        "STREAMLIT_APP_URL": os.getenv("STREAMLIT_APP_URL", "http://localhost:8501"),
        "DEBUG_AUTH": os.getenv("DEBUG_AUTH", "false"),
        "TEST_EMAIL": os.getenv("TEST_EMAIL", "Not set"),
    }
    
    all_set = True
    
    print("\n   Required Variables:")
    for var_name, var_value in required_vars.items():
        if var_value:
            print(f"   ✅ {var_name}: {'*' * 20}... (set)")
        else:
            print(f"   ❌ {var_name}: Not set")
            all_set = False
    
    print("\n   Optional Variables:")
    for var_name, var_value in optional_vars.items():
        if var_name in ["SUPABASE_KEY", "SUPABASE_JWT_SECRET"] and var_value:
            display_value = f"{'*' * 20}... (set)"
        else:
            display_value = var_value
        print(f"   ℹ️  {var_name}: {display_value}")
    
    if all_set:
        print("\n✅ PASSED: All required environment variables are set")
        return True
    else:
        print("\n❌ FAILED: Some required environment variables are missing")
        return False


def test_debug_mode():
    """Test debug mode configuration."""
    print("\n" + "=" * 80)
    print("TEST 5: Debug Mode Configuration")
    print("=" * 80)
    
    debug_auth = os.getenv("DEBUG_AUTH", "false").lower() in ("true", "1", "yes")
    
    print(f"   DEBUG_AUTH environment variable: {os.getenv('DEBUG_AUTH', 'not set')}")
    print(f"   Debug mode enabled: {debug_auth}")
    
    if debug_auth:
        print("\n   ⚠️  WARNING: Debug mode is enabled")
        print("   This will show sensitive information in the UI")
        print("   Set DEBUG_AUTH=false for production")
    else:
        print("\n   ℹ️  Debug mode is disabled (good for production)")
        print("   Set DEBUG_AUTH=true to enable debugging")
    
    print("\n✅ PASSED: Debug mode configuration is valid")
    return True


def print_instructions():
    """Print instructions for manual testing."""
    print("\n" + "=" * 80)
    print("MANUAL TESTING INSTRUCTIONS")
    print("=" * 80)
    
    print("""
To test the magic link flow manually:

1. Enable debug mode:
   export DEBUG_AUTH=true

2. Start the Streamlit app:
   streamlit run streamlit_app/app.py

3. In the app:
   - Click the "Magic Link" tab
   - Enter your email address
   - Click "Send Magic Link"
   - Check the debug output for the redirect URL

4. Check your email:
   - Open the magic link email
   - Before clicking, hover over the link and inspect the URL
   - Look for: ?access_token=... (query params) or #access_token=... (hash)

5. Click the magic link:
   - Watch the debug panel in the sidebar
   - Check the browser console for any errors
   - Verify the authentication completes

6. Check the logs:
   - Look for emoji-prefixed log messages
   - Verify each step of the flow is logged
   - Check for any error messages

Expected behavior:
- Debug panel shows tokens detected
- Session is created successfully
- You're redirected to the chat interface
- No errors in console or logs

If it fails:
- Check the debug panel for what step failed
- Review the MAGIC_LINK_DEBUG.md document
- Verify Supabase redirect URL matches STREAMLIT_APP_URL
- Check if tokens are in hash fragment (needs JavaScript extraction)
""")


def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("MAGIC LINK AUTHENTICATION TEST SUITE")
    print("=" * 80)
    
    results = {
        "Environment Variables": test_environment_variables(),
        "AuthManager Initialization": test_auth_manager_initialization(),
        "Session Methods": test_session_methods(),
        "Debug Mode Configuration": test_debug_mode(),
        "Send Magic Link": test_otp_send(),
    }
    
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    for test_name, result in results.items():
        if result is True:
            status = "✅ PASSED"
        elif result is False:
            status = "❌ FAILED"
        else:
            status = "⚠️  SKIPPED"
        print(f"{status}: {test_name}")
    
    passed = sum(1 for r in results.values() if r is True)
    failed = sum(1 for r in results.values() if r is False)
    skipped = sum(1 for r in results.values() if r is None)
    total = len(results)
    
    print(f"\nTotal: {total} | Passed: {passed} | Failed: {failed} | Skipped: {skipped}")
    
    if failed > 0:
        print("\n⚠️  Some tests failed. Please fix the issues before proceeding.")
        print_instructions()
        return 1
    else:
        print("\n✅ All tests passed!")
        print_instructions()
        return 0


if __name__ == "__main__":
    exit(main())
