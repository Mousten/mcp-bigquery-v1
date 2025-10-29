"""Session management for chat persistence."""
import streamlit as st
from typing import List, Dict, Any, Optional
import httpx
import logging

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages chat sessions via the MCP API."""
    
    def __init__(self, base_url: str, access_token: str):
        """Initialize session manager.
        
        Args:
            base_url: Base URL of the MCP server
            access_token: JWT access token
        """
        self.base_url = base_url.rstrip('/')
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
    
    async def create_session(self, title: str = "New Conversation") -> Optional[Dict[str, Any]]:
        """Create a new chat session.
        
        Args:
            title: Session title
            
        Returns:
            Session data if successful, None otherwise
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/stream/chat/sessions",
                    headers=self.headers,
                    json={"title": title},
                    timeout=10.0
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            return None
    
    async def list_sessions(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """List chat sessions.
        
        Args:
            limit: Maximum sessions to return
            offset: Number of sessions to skip
            
        Returns:
            List of sessions
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/stream/chat/sessions",
                    headers=self.headers,
                    params={"limit": limit, "offset": offset},
                    timeout=10.0
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")
            return []
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session details.
        
        Args:
            session_id: Session ID
            
        Returns:
            Session data if found, None otherwise
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/stream/chat/sessions/{session_id}",
                    headers=self.headers,
                    timeout=10.0
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Failed to get session: {e}")
            return None
    
    async def rename_session(self, session_id: str, title: str) -> bool:
        """Rename a session.
        
        Args:
            session_id: Session ID
            title: New title
            
        Returns:
            True if successful, False otherwise
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.put(
                    f"{self.base_url}/stream/chat/sessions/{session_id}",
                    headers=self.headers,
                    json={"title": title},
                    timeout=10.0
                )
                response.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"Failed to rename session: {e}")
            return False
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete a session.
        
        Args:
            session_id: Session ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{self.base_url}/stream/chat/sessions/{session_id}",
                    headers=self.headers,
                    timeout=10.0
                )
                response.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"Failed to delete session: {e}")
            return False
    
    async def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Append a message to a session.
        
        Args:
            session_id: Session ID
            role: Message role (user, assistant, system)
            content: Message content
            metadata: Optional metadata
            
        Returns:
            Message data if successful, None otherwise
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/stream/chat/sessions/{session_id}/messages",
                    headers=self.headers,
                    json={
                        "role": role,
                        "content": content,
                        "metadata": metadata or {}
                    },
                    timeout=10.0
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Failed to append message: {e}")
            return None
    
    async def fetch_messages(
        self,
        session_id: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Fetch messages for a session.
        
        Args:
            session_id: Session ID
            limit: Optional maximum messages to return
            
        Returns:
            List of messages
        """
        try:
            async with httpx.AsyncClient() as client:
                params = {}
                if limit:
                    params["limit"] = limit
                
                response = await client.get(
                    f"{self.base_url}/stream/chat/sessions/{session_id}/messages",
                    headers=self.headers,
                    params=params,
                    timeout=10.0
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch messages: {e}")
            return []


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
    
    if "current_session" not in st.session_state:
        st.session_state.current_session = None
    
    if "chat_sessions" not in st.session_state:
        st.session_state.chat_sessions = []
    
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "processing" not in st.session_state:
        st.session_state.processing = False
