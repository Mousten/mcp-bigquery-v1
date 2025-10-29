"""Tests for chat API routes."""

import pytest
import jwt
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcp_bigquery.routes.chat import create_chat_router
from mcp_bigquery.api.dependencies import create_auth_dependency


@pytest.fixture
def jwt_secret():
    """Test JWT secret."""
    return "test-secret-key"


@pytest.fixture
def valid_token(jwt_secret):
    """Create a valid JWT token."""
    payload = {
        "sub": "user-123",
        "email": "test@example.com",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return jwt.encode(payload, jwt_secret, algorithm="HS256")


@pytest.fixture
def expired_token(jwt_secret):
    """Create an expired JWT token."""
    payload = {
        "sub": "user-123",
        "email": "test@example.com",
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
    }
    return jwt.encode(payload, jwt_secret, algorithm="HS256")


@pytest.fixture
def mock_knowledge_base():
    """Mock SupabaseKnowledgeBase."""
    kb = MagicMock()
    
    # Mock RBAC methods
    kb.get_user_profile = AsyncMock(return_value={
        "user_id": "user-123",
        "metadata": {}
    })
    kb.get_user_roles = AsyncMock(return_value=[])
    kb.get_role_permissions = AsyncMock(return_value=[])
    kb.get_role_dataset_access = AsyncMock(return_value=[])
    
    # Mock chat methods
    kb.create_chat_session = AsyncMock()
    kb.list_chat_sessions = AsyncMock()
    kb.append_chat_message = AsyncMock()
    kb.fetch_chat_history = AsyncMock()
    kb.rename_session = AsyncMock()
    kb.delete_chat_session = AsyncMock()
    
    return kb


@pytest.fixture
def app(mock_knowledge_base, jwt_secret):
    """Create test FastAPI app."""
    import os
    # Set the JWT secret in environment for the duration of tests
    original_secret = os.environ.get('SUPABASE_JWT_SECRET')
    os.environ['SUPABASE_JWT_SECRET'] = jwt_secret
    
    app = FastAPI()
    auth_dependency = create_auth_dependency(mock_knowledge_base)
    chat_router = create_chat_router(mock_knowledge_base, auth_dependency)
    app.include_router(chat_router)
    
    yield app
    
    # Restore original value
    if original_secret:
        os.environ['SUPABASE_JWT_SECRET'] = original_secret
    else:
        os.environ.pop('SUPABASE_JWT_SECRET', None)


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


def test_create_session_success(client, mock_knowledge_base, valid_token):
    """Test successful session creation."""
    session_id = str(uuid4())
    mock_knowledge_base.create_chat_session.return_value = {
        "id": session_id,
        "user_id": "user-123",
        "title": "Test Session",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    response = client.post(
        "/chat/sessions",
        json={"title": "Test Session"},
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["id"] == session_id
    assert data["title"] == "Test Session"
    assert data["user_id"] == "user-123"


def test_create_session_default_title(client, mock_knowledge_base, valid_token):
    """Test session creation with default title."""
    session_id = str(uuid4())
    mock_knowledge_base.create_chat_session.return_value = {
        "id": session_id,
        "user_id": "user-123",
        "title": "New Conversation",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    response = client.post(
        "/chat/sessions",
        json={},
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "New Conversation"


def test_create_session_unauthorized(client, mock_knowledge_base):
    """Test session creation without auth token."""
    response = client.post(
        "/chat/sessions",
        json={"title": "Test"}
    )
    
    assert response.status_code == 401


def test_create_session_expired_token(client, mock_knowledge_base, expired_token):
    """Test session creation with expired token."""
    response = client.post(
        "/chat/sessions",
        json={"title": "Test"},
        headers={"Authorization": f"Bearer {expired_token}"}
    )
    
    assert response.status_code == 401


def test_list_sessions_success(client, mock_knowledge_base, valid_token):
    """Test listing sessions."""
    mock_knowledge_base.list_chat_sessions.return_value = [
        {
            "id": str(uuid4()),
            "user_id": "user-123",
            "title": "Session 1",
            "created_at": "2024-01-01T10:00:00Z",
            "updated_at": "2024-01-01T12:00:00Z"
        },
        {
            "id": str(uuid4()),
            "user_id": "user-123",
            "title": "Session 2",
            "created_at": "2024-01-02T10:00:00Z",
            "updated_at": "2024-01-02T11:00:00Z"
        }
    ]
    
    response = client.get(
        "/chat/sessions",
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["title"] == "Session 1"


def test_list_sessions_with_pagination(client, mock_knowledge_base, valid_token):
    """Test listing sessions with pagination."""
    mock_knowledge_base.list_chat_sessions.return_value = []
    
    response = client.get(
        "/chat/sessions?limit=10&offset=5",
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    
    assert response.status_code == 200
    mock_knowledge_base.list_chat_sessions.assert_called_once()
    call_kwargs = mock_knowledge_base.list_chat_sessions.call_args[1]
    assert call_kwargs["limit"] == 10
    assert call_kwargs["offset"] == 5


def test_list_sessions_empty(client, mock_knowledge_base, valid_token):
    """Test listing sessions when none exist."""
    mock_knowledge_base.list_chat_sessions.return_value = []
    
    response = client.get(
        "/chat/sessions",
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    
    assert response.status_code == 200
    assert response.json() == []


def test_append_message_success(client, mock_knowledge_base, valid_token):
    """Test appending a message to a session."""
    session_id = str(uuid4())
    message_id = str(uuid4())
    
    mock_knowledge_base.append_chat_message.return_value = {
        "id": message_id,
        "session_id": session_id,
        "role": "user",
        "content": "Hello!",
        "metadata": {"test": "data"},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "ordering": 0
    }
    
    response = client.post(
        f"/chat/sessions/{session_id}/messages",
        json={
            "role": "user",
            "content": "Hello!",
            "metadata": {"test": "data"}
        },
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["id"] == message_id
    assert data["role"] == "user"
    assert data["content"] == "Hello!"
    assert data["ordering"] == 0


def test_append_message_invalid_role(client, mock_knowledge_base, valid_token):
    """Test appending message with invalid role."""
    session_id = str(uuid4())
    
    response = client.post(
        f"/chat/sessions/{session_id}/messages",
        json={
            "role": "invalid",
            "content": "Test"
        },
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    
    assert response.status_code == 400
    assert "Invalid role" in response.json()["detail"]


def test_append_message_unauthorized_session(client, mock_knowledge_base, valid_token):
    """Test appending message to unauthorized session."""
    session_id = str(uuid4())
    mock_knowledge_base.append_chat_message.return_value = None
    
    response = client.post(
        f"/chat/sessions/{session_id}/messages",
        json={
            "role": "user",
            "content": "Test"
        },
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    
    assert response.status_code == 404


def test_fetch_messages_success(client, mock_knowledge_base, valid_token):
    """Test fetching chat history."""
    session_id = str(uuid4())
    
    mock_knowledge_base.fetch_chat_history.return_value = [
        {
            "id": str(uuid4()),
            "session_id": session_id,
            "role": "user",
            "content": "Hello",
            "metadata": {},
            "created_at": "2024-01-01T10:00:00Z",
            "ordering": 0
        },
        {
            "id": str(uuid4()),
            "session_id": session_id,
            "role": "assistant",
            "content": "Hi!",
            "metadata": {},
            "created_at": "2024-01-01T10:01:00Z",
            "ordering": 1
        }
    ]
    
    response = client.get(
        f"/chat/sessions/{session_id}/messages",
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["ordering"] == 0
    assert data[1]["ordering"] == 1
    assert data[0]["role"] == "user"
    assert data[1]["role"] == "assistant"


def test_fetch_messages_with_limit(client, mock_knowledge_base, valid_token):
    """Test fetching chat history with limit."""
    session_id = str(uuid4())
    mock_knowledge_base.fetch_chat_history.return_value = []
    
    # When empty, the endpoint will check if session exists
    mock_knowledge_base.list_chat_sessions.return_value = [{
        "id": session_id,
        "user_id": "user-123",
        "title": "Test",
        "created_at": "2024-01-01T10:00:00Z",
        "updated_at": "2024-01-01T10:00:00Z"
    }]
    
    response = client.get(
        f"/chat/sessions/{session_id}/messages?limit=10",
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    
    assert response.status_code == 200
    mock_knowledge_base.fetch_chat_history.assert_called_once()
    call_kwargs = mock_knowledge_base.fetch_chat_history.call_args[1]
    assert call_kwargs["limit"] == 10


def test_fetch_messages_empty_session(client, mock_knowledge_base, valid_token):
    """Test fetching messages from empty session."""
    session_id = str(uuid4())
    
    # First return empty messages, then return the session on verification
    mock_knowledge_base.fetch_chat_history.return_value = []
    mock_knowledge_base.list_chat_sessions.return_value = [{
        "id": session_id,
        "user_id": "user-123",
        "title": "Test",
        "created_at": "2024-01-01T10:00:00Z",
        "updated_at": "2024-01-01T10:00:00Z"
    }]
    
    response = client.get(
        f"/chat/sessions/{session_id}/messages",
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    
    assert response.status_code == 200
    assert response.json() == []


def test_fetch_messages_unauthorized(client, mock_knowledge_base, valid_token):
    """Test fetching messages from unauthorized session."""
    session_id = str(uuid4())
    
    mock_knowledge_base.fetch_chat_history.return_value = []
    mock_knowledge_base.list_chat_sessions.return_value = []
    
    response = client.get(
        f"/chat/sessions/{session_id}/messages",
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    
    assert response.status_code == 404


def test_rename_session_success(client, mock_knowledge_base, valid_token):
    """Test renaming a session."""
    session_id = str(uuid4())
    
    mock_knowledge_base.rename_session.return_value = True
    mock_knowledge_base.list_chat_sessions.return_value = [{
        "id": session_id,
        "user_id": "user-123",
        "title": "Updated Title",
        "created_at": "2024-01-01T10:00:00Z",
        "updated_at": datetime.now(timezone.utc).isoformat()
    }]
    
    response = client.put(
        f"/chat/sessions/{session_id}",
        json={"title": "Updated Title"},
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Title"


def test_rename_session_unauthorized(client, mock_knowledge_base, valid_token):
    """Test renaming unauthorized session."""
    session_id = str(uuid4())
    mock_knowledge_base.rename_session.return_value = False
    
    response = client.put(
        f"/chat/sessions/{session_id}",
        json={"title": "New Title"},
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    
    assert response.status_code == 404


def test_delete_session_success(client, mock_knowledge_base, valid_token):
    """Test deleting a session."""
    session_id = str(uuid4())
    mock_knowledge_base.delete_chat_session.return_value = True
    
    response = client.delete(
        f"/chat/sessions/{session_id}",
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    
    assert response.status_code == 204


def test_delete_session_unauthorized(client, mock_knowledge_base, valid_token):
    """Test deleting unauthorized session."""
    session_id = str(uuid4())
    mock_knowledge_base.delete_chat_session.return_value = False
    
    response = client.delete(
        f"/chat/sessions/{session_id}",
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    
    assert response.status_code == 404


def test_get_session_success(client, mock_knowledge_base, valid_token):
    """Test getting a specific session."""
    session_id = str(uuid4())
    
    mock_knowledge_base.list_chat_sessions.return_value = [{
        "id": session_id,
        "user_id": "user-123",
        "title": "Test Session",
        "created_at": "2024-01-01T10:00:00Z",
        "updated_at": "2024-01-01T12:00:00Z"
    }]
    
    response = client.get(
        f"/chat/sessions/{session_id}",
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == session_id
    assert data["title"] == "Test Session"


def test_get_session_not_found(client, mock_knowledge_base, valid_token):
    """Test getting non-existent session."""
    session_id = str(uuid4())
    mock_knowledge_base.list_chat_sessions.return_value = []
    
    response = client.get(
        f"/chat/sessions/{session_id}",
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    
    assert response.status_code == 404


def test_message_metadata_preserved(client, mock_knowledge_base, valid_token):
    """Test that message metadata is preserved."""
    session_id = str(uuid4())
    message_id = str(uuid4())
    
    metadata = {
        "model": "gpt-4",
        "tokens": 150,
        "temperature": 0.7
    }
    
    mock_knowledge_base.append_chat_message.return_value = {
        "id": message_id,
        "session_id": session_id,
        "role": "assistant",
        "content": "Response",
        "metadata": metadata,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "ordering": 1
    }
    
    response = client.post(
        f"/chat/sessions/{session_id}/messages",
        json={
            "role": "assistant",
            "content": "Response",
            "metadata": metadata
        },
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["metadata"] == metadata


def test_multiple_users_isolation(client, mock_knowledge_base, jwt_secret):
    """Test that users can only access their own sessions."""
    # Create tokens for two different users
    token1 = jwt.encode({
        "sub": "user-123",
        "email": "user1@example.com",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }, jwt_secret, algorithm="HS256")
    
    token2 = jwt.encode({
        "sub": "user-456",
        "email": "user2@example.com",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }, jwt_secret, algorithm="HS256")
    
    # User 1 creates a session
    session_id = str(uuid4())
    mock_knowledge_base.create_chat_session.return_value = {
        "id": session_id,
        "user_id": "user-123",
        "title": "User 1 Session",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    response1 = client.post(
        "/chat/sessions",
        json={"title": "User 1 Session"},
        headers={"Authorization": f"Bearer {token1}"}
    )
    assert response1.status_code == 201
    
    # User 2 tries to access User 1's session
    mock_knowledge_base.fetch_chat_history.return_value = []
    mock_knowledge_base.list_chat_sessions.return_value = []
    
    response2 = client.get(
        f"/chat/sessions/{session_id}/messages",
        headers={"Authorization": f"Bearer {token2}"}
    )
    assert response2.status_code == 404
