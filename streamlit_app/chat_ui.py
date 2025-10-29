"""Chat interface UI for conversational interactions."""
import streamlit as st
import asyncio
from typing import Dict, Any, Optional, List
import logging
from datetime import datetime
from .session_manager import SessionManager
from .insights_ui import render_query_results, render_chart_suggestions
from .utils import format_timestamp, format_error_message, format_sql_query

logger = logging.getLogger(__name__)


async def process_user_question(
    question: str,
    session_id: str,
    user_id: str,
    conversation_manager: Any,
    session_manager: SessionManager,
    allowed_datasets: set,
    allowed_tables: dict
) -> Dict[str, Any]:
    """Process a user question through the conversation manager.
    
    Args:
        question: User question
        session_id: Session ID
        user_id: User ID
        conversation_manager: ConversationManager instance
        session_manager: SessionManager instance
        allowed_datasets: Set of allowed datasets
        allowed_tables: Dict of allowed tables per dataset
        
    Returns:
        Response dictionary
    """
    try:
        # Import here to avoid circular imports
        from mcp_bigquery.agent import AgentRequest
        
        # Create agent request
        request = AgentRequest(
            question=question,
            session_id=session_id,
            user_id=user_id,
            allowed_datasets=allowed_datasets,
            allowed_tables=allowed_tables,
            context_turns=5
        )
        
        # Process with conversation manager
        response = await conversation_manager.process_conversation(request)
        
        # Save user message to session
        await session_manager.append_message(
            session_id=session_id,
            role="user",
            content=question,
            metadata={}
        )
        
        # Save assistant response to session
        assistant_content = response.answer or "I encountered an error processing your request."
        await session_manager.append_message(
            session_id=session_id,
            role="assistant",
            content=assistant_content,
            metadata={
                "sql_query": response.sql_query,
                "sql_explanation": response.sql_explanation,
                "chart_suggestions": [s.model_dump() for s in response.chart_suggestions] if response.chart_suggestions else [],
                "success": response.success,
                "error": response.error,
                "error_type": response.error_type,
                "tokens_used": response.metadata.get("tokens_used"),
                "processing_time_ms": response.metadata.get("processing_time_ms")
            }
        )
        
        return {
            "success": response.success,
            "answer": response.answer,
            "sql_query": response.sql_query,
            "sql_explanation": response.sql_explanation,
            "results": response.results,
            "chart_suggestions": [s.model_dump() for s in response.chart_suggestions] if response.chart_suggestions else [],
            "error": response.error,
            "error_type": response.error_type,
            "metadata": response.metadata
        }
        
    except Exception as e:
        logger.error(f"Error processing question: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": "unknown"
        }


def render_message(message: Dict[str, Any]) -> None:
    """Render a single message in the chat interface.
    
    Args:
        message: Message dictionary
    """
    role = message.get("role", "user")
    content = message.get("content", "")
    metadata = message.get("metadata", {})
    
    # Determine avatar
    avatar = "🧑" if role == "user" else "🤖"
    
    with st.chat_message(role, avatar=avatar):
        st.markdown(content)
        
        # Show SQL query if available (for assistant messages)
        if role == "assistant" and metadata.get("sql_query"):
            with st.expander("📝 SQL Query", expanded=False):
                sql_query = metadata["sql_query"]
                st.code(format_sql_query(sql_query), language="sql")
                
                # Show explanation if available
                if metadata.get("sql_explanation"):
                    st.markdown("**Explanation:**")
                    st.markdown(metadata["sql_explanation"])
        
        # Show chart suggestions if available
        if role == "assistant" and metadata.get("chart_suggestions"):
            chart_suggestions = metadata["chart_suggestions"]
            if chart_suggestions and metadata.get("results"):
                # Note: We can't easily re-render charts from persisted messages
                # This would require storing the full results, which could be large
                st.info("💡 This response included chart suggestions (not shown in history)")
        
        # Show metadata info
        if role == "assistant" and (metadata.get("tokens_used") or metadata.get("processing_time_ms")):
            cols = st.columns(2)
            if metadata.get("tokens_used"):
                cols[0].caption(f"🪙 Tokens: {metadata['tokens_used']:,}")
            if metadata.get("processing_time_ms"):
                cols[1].caption(f"⏱️ Time: {metadata['processing_time_ms']:.0f}ms")


def render_chat_interface(
    conversation_manager: Any,
    session_manager: SessionManager,
    user_id: str,
    user_context: Any
) -> None:
    """Render the main chat interface.
    
    Args:
        conversation_manager: ConversationManager instance
        session_manager: SessionManager instance
        user_id: User ID
        user_context: UserContext instance for RBAC
    """
    # Sidebar for session management
    with st.sidebar:
        st.subheader("💬 Chat Sessions")
        
        # New chat button
        if st.button("➕ New Chat", use_container_width=True):
            asyncio.run(create_new_session(session_manager))
            st.rerun()
        
        st.divider()
        
        # Load sessions if not already loaded
        if not st.session_state.get("chat_sessions"):
            st.session_state.chat_sessions = asyncio.run(session_manager.list_sessions())
        
        # Display sessions
        sessions = st.session_state.get("chat_sessions", [])
        if sessions:
            for session in sessions:
                session_id = session.get("id")
                title = session.get("title", "Untitled")
                updated_at = format_timestamp(session.get("updated_at", ""))
                
                is_current = st.session_state.get("current_session") == session_id
                
                button_label = f"{'▶️' if is_current else '💬'} {title}"
                if st.button(button_label, key=f"session_{session_id}", use_container_width=True):
                    st.session_state.current_session = session_id
                    # Load messages for this session
                    st.session_state.messages = asyncio.run(
                        session_manager.fetch_messages(session_id)
                    )
                    st.rerun()
                
                st.caption(updated_at)
        else:
            st.info("No chat sessions yet. Start a new chat!")
    
    # Main chat area
    if not st.session_state.get("current_session"):
        # No session selected - create one
        st.info("👈 Select a chat session or create a new one to get started!")
        return
    
    current_session = st.session_state.current_session
    
    # Header with session info and actions
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        session_data = next(
            (s for s in st.session_state.chat_sessions if s.get("id") == current_session),
            None
        )
        if session_data:
            st.subheader(session_data.get("title", "Chat"))
    with col2:
        if st.button("✏️ Rename"):
            st.session_state.show_rename_dialog = True
    with col3:
        if st.button("🗑️ Delete"):
            if asyncio.run(session_manager.delete_session(current_session)):
                st.session_state.current_session = None
                st.session_state.messages = []
                st.session_state.chat_sessions = asyncio.run(session_manager.list_sessions())
                st.rerun()
    
    # Rename dialog
    if st.session_state.get("show_rename_dialog"):
        with st.form("rename_form"):
            new_title = st.text_input("New Title", value=session_data.get("title", ""))
            col1, col2 = st.columns(2)
            with col1:
                if st.form_submit_button("Save", use_container_width=True):
                    if asyncio.run(session_manager.rename_session(current_session, new_title)):
                        st.session_state.chat_sessions = asyncio.run(session_manager.list_sessions())
                        st.session_state.show_rename_dialog = False
                        st.rerun()
            with col2:
                if st.form_submit_button("Cancel", use_container_width=True):
                    st.session_state.show_rename_dialog = False
                    st.rerun()
    
    st.divider()
    
    # Display chat history
    messages = st.session_state.get("messages", [])
    for message in messages:
        render_message(message)
    
    # Chat input
    if prompt := st.chat_input("Ask a question about your data..."):
        if st.session_state.get("processing"):
            st.warning("⏳ Please wait for the current request to complete")
            return
        
        # Set processing flag
        st.session_state.processing = True
        
        # Display user message immediately
        with st.chat_message("user", avatar="🧑"):
            st.markdown(prompt)
        
        # Process the question
        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Thinking..."):
                response = asyncio.run(process_user_question(
                    question=prompt,
                    session_id=current_session,
                    user_id=user_id,
                    conversation_manager=conversation_manager,
                    session_manager=session_manager,
                    allowed_datasets=user_context.allowed_datasets,
                    allowed_tables=user_context.allowed_tables
                ))
                
                if response["success"]:
                    # Show answer
                    st.markdown(response["answer"])
                    
                    # Show SQL query
                    if response.get("sql_query"):
                        with st.expander("📝 SQL Query", expanded=True):
                            st.code(format_sql_query(response["sql_query"]), language="sql")
                            if response.get("sql_explanation"):
                                st.markdown("**Explanation:**")
                                st.markdown(response["sql_explanation"])
                    
                    # Show results
                    if response.get("results"):
                        render_query_results(response["results"])
                    
                    # Show chart suggestions
                    if response.get("chart_suggestions") and response.get("results"):
                        render_chart_suggestions(response["chart_suggestions"], response["results"])
                    
                    # Show metadata
                    metadata = response.get("metadata", {})
                    if metadata.get("tokens_used") or metadata.get("processing_time_ms"):
                        cols = st.columns(2)
                        if metadata.get("tokens_used"):
                            cols[0].caption(f"🪙 Tokens: {metadata['tokens_used']:,}")
                        if metadata.get("processing_time_ms"):
                            cols[1].caption(f"⏱️ Time: {metadata['processing_time_ms']:.0f}ms")
                else:
                    # Show error
                    error_msg = format_error_message(
                        response.get("error", "Unknown error"),
                        response.get("error_type")
                    )
                    st.error(error_msg)
        
        # Clear processing flag and reload messages
        st.session_state.processing = False
        st.session_state.messages = asyncio.run(
            session_manager.fetch_messages(current_session)
        )
        st.rerun()


async def create_new_session(session_manager: SessionManager) -> None:
    """Create a new chat session.
    
    Args:
        session_manager: SessionManager instance
    """
    session = await session_manager.create_session(
        title=f"Chat {datetime.now().strftime('%b %d, %I:%M %p')}"
    )
    
    if session:
        st.session_state.current_session = session["id"]
        st.session_state.messages = []
        st.session_state.chat_sessions = await session_manager.list_sessions()
