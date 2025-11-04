"""Main Streamlit application for BigQuery Insights."""
from dotenv import load_dotenv

# Load .env file BEFORE anything else to ensure environment variables are available
load_dotenv()

import streamlit as st
import asyncio
import logging
import sys
from pathlib import Path
from typing import Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from streamlit_app.config import StreamlitConfig
from streamlit_app.auth import (
    AuthManager, 
    render_login_ui, 
    check_auth_status, 
    sign_out,
    handle_magic_link_callback
)
from streamlit_app.session_manager import SessionManager, init_session_state
from streamlit_app.chat_ui import render_chat_interface

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


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
    
    # Debug logging for initial page load
    logger.info("=" * 80)
    logger.info("🚀 Page Load")
    logger.info(f"🔑 Query params present: {list(st.query_params.keys())}")
    logger.info(f"🔐 Authenticated: {st.session_state.get('authenticated', False)}")
    logger.info("=" * 80)
    
    # Handle magic link callback if present (must be before auth check)
    callback_handled = handle_magic_link_callback(auth_manager)
    logger.info(f"🔗 Magic link callback handled: {callback_handled}")
    
    if callback_handled:
        # Callback was handled, function will handle rerun
        logger.info("🔗 Callback processing complete, rerunning...")
        return
    
    # Check authentication status
    auth_status = check_auth_status(auth_manager)
    logger.info(f"🔐 Auth status: {auth_status}")
    
    if not auth_status:
        # Show login UI
        logger.info("🔐 User not authenticated, showing login UI")
        render_login_ui(auth_manager)
        return
    
    logger.info(f"✅ User authenticated, rendering main app for: {st.session_state.get('user', {}).get('email', 'Unknown')}")
    
    # User is authenticated - show main app
    render_main_app(config, auth_manager)


def render_main_app(config: StreamlitConfig, auth_manager: AuthManager):
    """Render the main application interface.
    
    Args:
        config: Application configuration
        auth_manager: Authentication manager
    """
    # Get user info
    user = st.session_state.get("user", {})
    user_id = user.get("id")
    user_email = user.get("email", "Unknown")
    
    # Header
    col1, col2 = st.columns([4, 1])
    with col1:
        st.title(f"{config.app_icon} {config.app_title}")
    with col2:
        with st.popover("👤 Account"):
            st.markdown(f"**{user_email}**")
            st.caption(f"User ID: {user_id[:8]}...")
            st.divider()
            if st.button("🚪 Sign Out", use_container_width=True):
                sign_out(auth_manager)
                st.rerun()
    
    st.markdown("Ask questions about your BigQuery data in natural language")
    st.divider()
    
    # Initialize components
    try:
        # Session manager for chat persistence
        session_manager = SessionManager(
            base_url=config.mcp_base_url,
            access_token=st.session_state.access_token
        )
        
        # Get user context for RBAC
        user_context = get_user_context(
            user_id=user_id,
            access_token=st.session_state.access_token,
            config=config
        )
        
        if not user_context:
            st.error("❌ Failed to load user permissions. Please try signing out and back in.")
            return
        
        # Initialize conversation manager
        conversation_manager = get_conversation_manager(config, user_context)
        
        # Render chat interface
        render_chat_interface(
            conversation_manager=conversation_manager,
            session_manager=session_manager,
            user_id=user_id,
            user_context=user_context
        )
        
    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=True)
        st.error(f"❌ Application Error: {str(e)}")


@st.cache_resource
def get_conversation_manager(config: StreamlitConfig, _user_context: Any):
    """Get or create conversation manager (cached).
    
    Args:
        config: Application configuration
        _user_context: User context (not used in cache key)
        
    Returns:
        ConversationManager instance
    """
    from mcp_bigquery.agent import ConversationManager
    from mcp_bigquery.client import MCPClient
    from mcp_bigquery.client.config import ClientConfig
    from mcp_bigquery.core.supabase_client import SupabaseKnowledgeBase
    
    # Initialize MCP client
    mcp_config = ClientConfig(
        base_url=config.mcp_base_url,
        auth_token=st.session_state.access_token
    )
    mcp_client = MCPClient(mcp_config)
    
    # Initialize Supabase knowledge base with service key for RLS bypass
    kb = SupabaseKnowledgeBase(
        supabase_url=config.supabase_url,
        supabase_key=config.supabase_service_key or config.supabase_key
    )
    
    # Determine API key based on provider
    api_key = None
    if config.llm_provider.lower() == "openai":
        api_key = config.openai_api_key
    elif config.llm_provider.lower() == "anthropic":
        api_key = config.anthropic_api_key
    elif config.llm_provider.lower() == "gemini":
        api_key = config.google_api_key
    
    # Create conversation manager
    manager = ConversationManager(
        mcp_client=mcp_client,
        kb=kb,
        project_id=config.project_id,
        provider_type=config.llm_provider,
        api_key=api_key,
        model=config.llm_model,
        enable_caching=config.enable_caching,
        enable_rate_limiting=config.enable_rate_limiting,
        max_context_turns=config.max_context_turns
    )
    
    return manager


def get_user_context(user_id: str, access_token: str, config: StreamlitConfig) -> Any:
    """Get user context with RBAC information.
    
    Args:
        user_id: User ID
        access_token: JWT access token
        config: Application configuration
        
    Returns:
        UserContext instance
    """
    try:
        from mcp_bigquery.core.auth import UserContext
        from mcp_bigquery.core.supabase_client import SupabaseKnowledgeBase
        
        # Initialize Supabase knowledge base with service key for RLS bypass
        kb = SupabaseKnowledgeBase(
            supabase_url=config.supabase_url,
            supabase_key=config.supabase_service_key or config.supabase_key
        )
        
        # Create user context from token
        user_context = asyncio.run(UserContext.from_token_async(
            token=access_token,
            jwt_secret=config.supabase_jwt_secret,
            supabase_kb=kb
        ))
        
        return user_context
        
    except Exception as e:
        logger.error(f"Failed to get user context: {e}", exc_info=True)
        return None


if __name__ == "__main__":
    main()
