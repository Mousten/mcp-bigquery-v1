"""Tests for chat persistence in SupabaseKnowledgeBase."""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from mcp_bigquery.core.supabase_client import SupabaseKnowledgeBase


@pytest.fixture
def mock_supabase_client():
    """Create a mock Supabase client with chainable query builder."""
    client = MagicMock()
    
    # Create a reusable query builder that chains methods
    query_builder = MagicMock()
    query_builder.select = MagicMock(return_value=query_builder)
    query_builder.insert = MagicMock(return_value=query_builder)
    query_builder.update = MagicMock(return_value=query_builder)
    query_builder.delete = MagicMock(return_value=query_builder)
    query_builder.eq = MagicMock(return_value=query_builder)
    query_builder.order = MagicMock(return_value=query_builder)
    query_builder.limit = MagicMock(return_value=query_builder)
    query_builder.range = MagicMock(return_value=query_builder)
    query_builder.execute = MagicMock()
    
    client.table = MagicMock(return_value=query_builder)
    return client


@pytest.fixture
def knowledge_base(mock_supabase_client):
    """Create a SupabaseKnowledgeBase instance with mocked client."""
    with patch.dict('os.environ', {
        'SUPABASE_URL': 'https://test.supabase.co',
        'SUPABASE_SERVICE_KEY': 'test-key'
    }):
        kb = SupabaseKnowledgeBase()
        kb.supabase = mock_supabase_client
        kb._connection_verified = True
        return kb


@pytest.mark.asyncio
async def test_create_chat_session_success(knowledge_base, mock_supabase_client):
    """Test successful chat session creation."""
    user_id = "user-123"
    title = "Test Conversation"
    session_id = str(uuid4())
    
    # Mock response
    expected_data = {
        "id": session_id,
        "user_id": user_id,
        "title": title,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    mock_response = MagicMock()
    mock_response.data = [expected_data]
    
    # Setup mock to return the response
    query_builder = mock_supabase_client.table.return_value
    query_builder.insert.return_value.execute.return_value = mock_response
    
    # Create session
    result = await knowledge_base.create_chat_session(user_id, title)
    
    assert result is not None
    assert result["id"] == session_id
    assert result["user_id"] == user_id
    assert result["title"] == title


@pytest.mark.asyncio
async def test_create_chat_session_default_title(knowledge_base, mock_supabase_client):
    """Test chat session creation with default title."""
    user_id = "user-456"
    session_id = str(uuid4())
    
    expected_data = {
        "id": session_id,
        "user_id": user_id,
        "title": "New Conversation",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    mock_response = MagicMock()
    mock_response.data = [expected_data]
    
    query_builder = mock_supabase_client.table.return_value
    query_builder.insert.return_value.execute.return_value = mock_response
    
    result = await knowledge_base.create_chat_session(user_id)
    
    assert result is not None
    assert result["title"] == "New Conversation"


@pytest.mark.asyncio
async def test_list_chat_sessions(knowledge_base, mock_supabase_client):
    """Test listing chat sessions for a user."""
    user_id = "user-123"
    
    expected_sessions = [
        {
            "id": str(uuid4()),
            "user_id": user_id,
            "title": "Session 1",
            "created_at": "2024-01-01T10:00:00Z",
            "updated_at": "2024-01-01T12:00:00Z"
        },
        {
            "id": str(uuid4()),
            "user_id": user_id,
            "title": "Session 2",
            "created_at": "2024-01-02T10:00:00Z",
            "updated_at": "2024-01-02T11:00:00Z"
        }
    ]
    
    mock_response = MagicMock()
    mock_response.data = expected_sessions
    
    query_builder = mock_supabase_client.table.return_value
    query_builder.select.return_value = query_builder
    query_builder.eq.return_value = query_builder
    query_builder.order.return_value = query_builder
    query_builder.range.return_value = query_builder
    query_builder.execute.return_value = mock_response
    
    result = await knowledge_base.list_chat_sessions(user_id, limit=50, offset=0)
    
    assert len(result) == 2
    assert result[0]["title"] == "Session 1"
    assert result[1]["title"] == "Session 2"


@pytest.mark.asyncio
async def test_list_chat_sessions_empty(knowledge_base, mock_supabase_client):
    """Test listing chat sessions when user has none."""
    user_id = "user-new"
    
    mock_response = MagicMock()
    mock_response.data = []
    
    query_builder = mock_supabase_client.table.return_value
    query_builder.select.return_value = query_builder
    query_builder.eq.return_value = query_builder
    query_builder.order.return_value = query_builder
    query_builder.range.return_value = query_builder
    query_builder.execute.return_value = mock_response
    
    result = await knowledge_base.list_chat_sessions(user_id)
    
    assert result == []


@pytest.mark.asyncio
async def test_append_chat_message_success(knowledge_base, mock_supabase_client):
    """Test successfully appending a message to a session."""
    session_id = str(uuid4())
    user_id = "user-123"
    message_id = str(uuid4())
    
    # Mock session ownership check
    session_response = MagicMock()
    session_response.data = [{"user_id": user_id}]
    
    # Mock message count query
    count_response = MagicMock()
    count_response.data = [{"ordering": 2}]
    
    # Mock message insert
    insert_response = MagicMock()
    insert_response.data = [{
        "id": message_id,
        "session_id": session_id,
        "role": "user",
        "content": "Hello!",
        "metadata": {},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "ordering": 3
    }]
    
    # Use execute side_effect to return different responses for each call
    query_builder = mock_supabase_client.table.return_value
    query_builder.execute.side_effect = [session_response, count_response, insert_response]
    
    result = await knowledge_base.append_chat_message(
        session_id=session_id,
        role="user",
        content="Hello!",
        user_id=user_id
    )
    
    assert result is not None
    assert result["id"] == message_id
    assert result["role"] == "user"
    assert result["content"] == "Hello!"
    assert result["ordering"] == 3


@pytest.mark.asyncio
async def test_append_chat_message_invalid_role(knowledge_base):
    """Test appending a message with invalid role."""
    session_id = str(uuid4())
    
    result = await knowledge_base.append_chat_message(
        session_id=session_id,
        role="invalid_role",
        content="Test",
        user_id="user-123"
    )
    
    assert result is None


@pytest.mark.asyncio
async def test_append_chat_message_unauthorized(knowledge_base, mock_supabase_client):
    """Test appending message to another user's session."""
    session_id = str(uuid4())
    user_id = "user-123"
    
    # Mock session ownership check - different user
    session_response = MagicMock()
    session_response.data = [{"user_id": "user-456"}]
    
    mock_supabase_client.table("chat_sessions").select.return_value.eq.return_value.limit.return_value.execute.return_value = session_response
    
    result = await knowledge_base.append_chat_message(
        session_id=session_id,
        role="user",
        content="Test",
        user_id=user_id
    )
    
    assert result is None


@pytest.mark.asyncio
async def test_append_chat_message_session_not_found(knowledge_base, mock_supabase_client):
    """Test appending message to non-existent session."""
    session_id = str(uuid4())
    user_id = "user-123"
    
    # Mock session not found
    session_response = MagicMock()
    session_response.data = []
    
    mock_supabase_client.table("chat_sessions").select.return_value.eq.return_value.limit.return_value.execute.return_value = session_response
    
    result = await knowledge_base.append_chat_message(
        session_id=session_id,
        role="user",
        content="Test",
        user_id=user_id
    )
    
    assert result is None


@pytest.mark.asyncio
async def test_fetch_chat_history_success(knowledge_base, mock_supabase_client):
    """Test fetching chat history with proper ordering."""
    session_id = str(uuid4())
    user_id = "user-123"
    
    # Mock session ownership check
    session_response = MagicMock()
    session_response.data = [{"user_id": user_id}]
    
    # Mock messages
    messages_response = MagicMock()
    messages_response.data = [
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
            "content": "Hi there!",
            "metadata": {},
            "created_at": "2024-01-01T10:01:00Z",
            "ordering": 1
        },
        {
            "id": str(uuid4()),
            "session_id": session_id,
            "role": "user",
            "content": "How are you?",
            "metadata": {},
            "created_at": "2024-01-01T10:02:00Z",
            "ordering": 2
        }
    ]
    
    # Setup mock calls
    table_mock = mock_supabase_client.table
    
    def side_effect(table_name):
        query_builder = MagicMock()
        query_builder.select = MagicMock(return_value=query_builder)
        query_builder.eq = MagicMock(return_value=query_builder)
        query_builder.order = MagicMock(return_value=query_builder)
        query_builder.limit = MagicMock(return_value=query_builder)
        
        if table_name == "chat_sessions":
            query_builder.execute = MagicMock(return_value=session_response)
        else:
            query_builder.execute = MagicMock(return_value=messages_response)
        
        return query_builder
    
    table_mock.side_effect = side_effect
    
    result = await knowledge_base.fetch_chat_history(session_id, user_id)
    
    assert len(result) == 3
    assert result[0]["ordering"] == 0
    assert result[1]["ordering"] == 1
    assert result[2]["ordering"] == 2
    assert result[0]["role"] == "user"
    assert result[1]["role"] == "assistant"


@pytest.mark.asyncio
async def test_fetch_chat_history_unauthorized(knowledge_base, mock_supabase_client):
    """Test fetching chat history for unauthorized session."""
    session_id = str(uuid4())
    user_id = "user-123"
    
    # Mock session ownership check - different user
    session_response = MagicMock()
    session_response.data = [{"user_id": "user-456"}]
    
    mock_supabase_client.table("chat_sessions").select.return_value.eq.return_value.limit.return_value.execute.return_value = session_response
    
    result = await knowledge_base.fetch_chat_history(session_id, user_id)
    
    assert result == []


@pytest.mark.asyncio
async def test_fetch_chat_history_not_found(knowledge_base, mock_supabase_client):
    """Test fetching chat history for non-existent session."""
    session_id = str(uuid4())
    user_id = "user-123"
    
    # Mock session not found
    session_response = MagicMock()
    session_response.data = []
    
    mock_supabase_client.table("chat_sessions").select.return_value.eq.return_value.limit.return_value.execute.return_value = session_response
    
    result = await knowledge_base.fetch_chat_history(session_id, user_id)
    
    assert result == []


@pytest.mark.asyncio
async def test_rename_session_success(knowledge_base, mock_supabase_client):
    """Test successfully renaming a session."""
    session_id = str(uuid4())
    user_id = "user-123"
    new_title = "Updated Title"
    
    # Mock session ownership check
    session_response = MagicMock()
    session_response.data = [{"user_id": user_id}]
    
    # Mock update response
    update_response = MagicMock()
    update_response.data = [{
        "id": session_id,
        "user_id": user_id,
        "title": new_title,
        "created_at": "2024-01-01T10:00:00Z",
        "updated_at": datetime.now(timezone.utc).isoformat()
    }]
    
    # Setup mock calls
    table_mock = mock_supabase_client.table
    
    def side_effect(table_name):
        query_builder = MagicMock()
        query_builder.select = MagicMock(return_value=query_builder)
        query_builder.update = MagicMock(return_value=query_builder)
        query_builder.eq = MagicMock(return_value=query_builder)
        query_builder.limit = MagicMock(return_value=query_builder)
        
        # First call is select for ownership check, second is update
        if hasattr(query_builder, '_update_called'):
            query_builder.execute = MagicMock(return_value=update_response)
        else:
            query_builder._update_called = True
            query_builder.execute = MagicMock(return_value=session_response)
        
        return query_builder
    
    table_mock.side_effect = side_effect
    
    result = await knowledge_base.rename_session(session_id, new_title, user_id)
    
    assert result is True


@pytest.mark.asyncio
async def test_rename_session_unauthorized(knowledge_base, mock_supabase_client):
    """Test renaming another user's session."""
    session_id = str(uuid4())
    user_id = "user-123"
    
    # Mock session ownership check - different user
    session_response = MagicMock()
    session_response.data = [{"user_id": "user-456"}]
    
    mock_supabase_client.table("chat_sessions").select.return_value.eq.return_value.limit.return_value.execute.return_value = session_response
    
    result = await knowledge_base.rename_session(session_id, "New Title", user_id)
    
    assert result is False


@pytest.mark.asyncio
async def test_delete_chat_session_success(knowledge_base, mock_supabase_client):
    """Test successfully deleting a session."""
    session_id = str(uuid4())
    user_id = "user-123"
    
    # Mock session ownership check
    session_response = MagicMock()
    session_response.data = [{"user_id": user_id}]
    
    # Mock delete response
    delete_response = MagicMock()
    delete_response.data = [{"id": session_id}]
    
    # Use execute side_effect to return different responses for each call
    query_builder = mock_supabase_client.table.return_value
    query_builder.execute.side_effect = [session_response, delete_response]
    
    result = await knowledge_base.delete_chat_session(session_id, user_id)
    
    assert result is True


@pytest.mark.asyncio
async def test_delete_chat_session_unauthorized(knowledge_base, mock_supabase_client):
    """Test deleting another user's session."""
    session_id = str(uuid4())
    user_id = "user-123"
    
    # Mock session ownership check - different user
    session_response = MagicMock()
    session_response.data = [{"user_id": "user-456"}]
    
    mock_supabase_client.table("chat_sessions").select.return_value.eq.return_value.limit.return_value.execute.return_value = session_response
    
    result = await knowledge_base.delete_chat_session(session_id, user_id)
    
    assert result is False


@pytest.mark.asyncio
async def test_message_ordering_sequential(knowledge_base, mock_supabase_client):
    """Test that messages are ordered sequentially."""
    session_id = str(uuid4())
    user_id = "user-123"
    message_id = str(uuid4())
    
    # Mock session ownership
    session_response = MagicMock()
    session_response.data = [{"user_id": user_id}]
    
    # Mock empty message list (first message)
    first_count_response = MagicMock()
    first_count_response.data = []
    
    first_insert_response = MagicMock()
    first_insert_response.data = [{
        "id": message_id,
        "session_id": session_id,
        "role": "user",
        "content": "First message",
        "metadata": {},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "ordering": 0
    }]
    
    # Use execute side_effect to return different responses for each call
    query_builder = mock_supabase_client.table.return_value
    query_builder.execute.side_effect = [session_response, first_count_response, first_insert_response]
    
    result = await knowledge_base.append_chat_message(
        session_id=session_id,
        role="user",
        content="First message",
        user_id=user_id
    )
    
    assert result is not None
    assert result["ordering"] == 0
