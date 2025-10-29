"""Chat persistence API routes."""

from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Body, Path, Query
from pydantic import BaseModel, Field

from ..core.auth import UserContext
from ..core.supabase_client import SupabaseKnowledgeBase


class CreateSessionRequest(BaseModel):
    """Request model for creating a chat session."""
    title: str = Field(default="New Conversation", description="Session title")


class RenameSessionRequest(BaseModel):
    """Request model for renaming a session."""
    title: str = Field(..., description="New session title")


class AppendMessageRequest(BaseModel):
    """Request model for appending a message to a session."""
    role: str = Field(..., description="Message role: user, assistant, or system")
    content: str = Field(..., description="Message content")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Optional message metadata")


class SessionResponse(BaseModel):
    """Response model for a chat session."""
    id: str
    user_id: str
    title: str
    created_at: str
    updated_at: str


class MessageResponse(BaseModel):
    """Response model for a chat message."""
    id: str
    session_id: str
    role: str
    content: str
    metadata: Dict[str, Any]
    created_at: str
    ordering: int


def create_chat_router(
    knowledge_base: SupabaseKnowledgeBase,
    auth_dependency
) -> APIRouter:
    """Create chat persistence router with authentication.
    
    Args:
        knowledge_base: SupabaseKnowledgeBase instance
        auth_dependency: Authentication dependency function
        
    Returns:
        Configured APIRouter
    """
    router = APIRouter(prefix="/chat", tags=["chat"])

    @router.post("/sessions", response_model=SessionResponse, status_code=201)
    async def create_session(
        request: CreateSessionRequest,
        user: UserContext = Depends(auth_dependency)
    ):
        """Create a new chat session for the authenticated user.
        
        Args:
            request: Session creation request with optional title
            user: Authenticated user context
            
        Returns:
            Created session details
            
        Raises:
            HTTPException: 500 if session creation fails
        """
        session = await knowledge_base.create_chat_session(
            user_id=user.user_id,
            title=request.title
        )
        
        if not session:
            raise HTTPException(
                status_code=500,
                detail="Failed to create chat session"
            )
        
        return session

    @router.get("/sessions", response_model=List[SessionResponse])
    async def list_sessions(
        limit: int = Query(50, ge=1, le=100, description="Maximum number of sessions to return"),
        offset: int = Query(0, ge=0, description="Number of sessions to skip"),
        user: UserContext = Depends(auth_dependency)
    ):
        """List chat sessions for the authenticated user.
        
        Args:
            limit: Maximum sessions to return (1-100)
            offset: Number of sessions to skip for pagination
            user: Authenticated user context
            
        Returns:
            List of user's sessions ordered by most recent first
        """
        sessions = await knowledge_base.list_chat_sessions(
            user_id=user.user_id,
            limit=limit,
            offset=offset
        )
        
        return sessions

    @router.get("/sessions/{session_id}")
    async def get_session(
        session_id: str = Path(..., description="Session UUID"),
        user: UserContext = Depends(auth_dependency)
    ):
        """Get details for a specific chat session.
        
        Args:
            session_id: Session UUID
            user: Authenticated user context
            
        Returns:
            Session details
            
        Raises:
            HTTPException: 404 if session not found or unauthorized
        """
        sessions = await knowledge_base.list_chat_sessions(user_id=user.user_id)
        session = next((s for s in sessions if s.get("id") == session_id), None)
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail="Session not found or access denied"
            )
        
        return session

    @router.put("/sessions/{session_id}", response_model=SessionResponse)
    async def rename_session(
        session_id: str = Path(..., description="Session UUID"),
        request: RenameSessionRequest = Body(...),
        user: UserContext = Depends(auth_dependency)
    ):
        """Rename a chat session.
        
        Args:
            session_id: Session UUID
            request: New title for the session
            user: Authenticated user context
            
        Returns:
            Updated session details
            
        Raises:
            HTTPException: 404 if session not found or 403 if unauthorized
        """
        success = await knowledge_base.rename_session(
            session_id=session_id,
            title=request.title,
            user_id=user.user_id
        )
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail="Session not found or access denied"
            )
        
        # Fetch updated session
        sessions = await knowledge_base.list_chat_sessions(user_id=user.user_id)
        session = next((s for s in sessions if s.get("id") == session_id), None)
        
        if not session:
            raise HTTPException(
                status_code=500,
                detail="Failed to retrieve updated session"
            )
        
        return session

    @router.delete("/sessions/{session_id}", status_code=204)
    async def delete_session(
        session_id: str = Path(..., description="Session UUID"),
        user: UserContext = Depends(auth_dependency)
    ):
        """Delete a chat session and all its messages.
        
        Args:
            session_id: Session UUID
            user: Authenticated user context
            
        Raises:
            HTTPException: 404 if session not found or 403 if unauthorized
        """
        success = await knowledge_base.delete_chat_session(
            session_id=session_id,
            user_id=user.user_id
        )
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail="Session not found or access denied"
            )
        
        return None

    @router.post("/sessions/{session_id}/messages", response_model=MessageResponse, status_code=201)
    async def append_message(
        session_id: str = Path(..., description="Session UUID"),
        request: AppendMessageRequest = Body(...),
        user: UserContext = Depends(auth_dependency)
    ):
        """Append a message to a chat session.
        
        Args:
            session_id: Session UUID
            request: Message details (role, content, metadata)
            user: Authenticated user context
            
        Returns:
            Created message details
            
        Raises:
            HTTPException: 400 for invalid role, 404 if session not found, 500 on failure
        """
        # Validate role
        if request.role not in ["user", "assistant", "system"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid role. Must be one of: user, assistant, system"
            )
        
        message = await knowledge_base.append_chat_message(
            session_id=session_id,
            role=request.role,
            content=request.content,
            metadata=request.metadata,
            user_id=user.user_id
        )
        
        if not message:
            raise HTTPException(
                status_code=404,
                detail="Session not found or access denied"
            )
        
        return message

    @router.get("/sessions/{session_id}/messages", response_model=List[MessageResponse])
    async def fetch_messages(
        session_id: str = Path(..., description="Session UUID"),
        limit: Optional[int] = Query(None, ge=1, description="Maximum number of messages to return"),
        user: UserContext = Depends(auth_dependency)
    ):
        """Fetch chat history for a session in chronological order.
        
        Args:
            session_id: Session UUID
            limit: Optional maximum number of messages to return
            user: Authenticated user context
            
        Returns:
            List of messages ordered by ordering field
            
        Raises:
            HTTPException: 404 if session not found or unauthorized
        """
        messages = await knowledge_base.fetch_chat_history(
            session_id=session_id,
            user_id=user.user_id,
            limit=limit
        )
        
        # If messages is empty, verify the session exists
        if not messages:
            sessions = await knowledge_base.list_chat_sessions(user_id=user.user_id)
            session = next((s for s in sessions if s.get("id") == session_id), None)
            
            if not session:
                raise HTTPException(
                    status_code=404,
                    detail="Session not found or access denied"
                )
        
        return messages

    return router
