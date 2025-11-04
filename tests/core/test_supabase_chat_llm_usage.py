"""Tests for chat persistence, LLM caching, and usage tracking in SupabaseKnowledgeBase."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from mcp_bigquery.core.supabase_client import SupabaseKnowledgeBase


@pytest.fixture
def mock_supabase():
    """Mock Supabase client for testing."""
    mock = MagicMock()
    mock.table = MagicMock(return_value=mock)
    mock.select = MagicMock(return_value=mock)
    mock.insert = MagicMock(return_value=mock)
    mock.update = MagicMock(return_value=mock)
    mock.delete = MagicMock(return_value=mock)
    mock.upsert = MagicMock(return_value=mock)
    mock.eq = MagicMock(return_value=mock)
    mock.gte = MagicMock(return_value=mock)
    mock.lt = MagicMock(return_value=mock)
    mock.lte = MagicMock(return_value=mock)
    mock.order = MagicMock(return_value=mock)
    mock.limit = MagicMock(return_value=mock)
    mock.offset = MagicMock(return_value=mock)
    mock.in_ = MagicMock(return_value=mock)
    mock.on_conflict = MagicMock(return_value=mock)
    return mock


@pytest.fixture
def supabase_kb():
    """Create a SupabaseKnowledgeBase instance with mocked Supabase client."""
    with patch.dict('os.environ', {
        'SUPABASE_URL': 'https://test.supabase.co',
        'SUPABASE_SERVICE_KEY': 'test-service-key'
    }):
        kb = SupabaseKnowledgeBase()
        kb._connection_verified = True
        return kb


class TestChatSessionManagement:
    """Tests for chat session CRUD operations."""
    
    @pytest.mark.asyncio
    async def test_create_chat_session_success(self, supabase_kb, mock_supabase):
        """Test creating a new chat session."""
        session_id = str(uuid4())
        mock_response = MagicMock()
        mock_response.data = [{
            "id": session_id,
            "user_id": "user-123",
            "title": "Test Chat",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }]
        mock_supabase.execute = MagicMock(return_value=mock_response)
        supabase_kb.supabase = mock_supabase
        
        result = await supabase_kb.create_chat_session(
            user_id="user-123",
            title="Test Chat"
        )
        
        assert result is not None
        assert result["id"] == session_id
        assert result["user_id"] == "user-123"
        assert result["title"] == "Test Chat"
        mock_supabase.table.assert_called_with("chat_sessions")
        mock_supabase.insert.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_chat_session_default_title(self, supabase_kb, mock_supabase):
        """Test creating a chat session with default title."""
        session_id = str(uuid4())
        mock_response = MagicMock()
        mock_response.data = [{
            "id": session_id,
            "user_id": "user-123",
            "title": "New Chat",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "metadata": {}
        }]
        mock_supabase.execute = MagicMock(return_value=mock_response)
        supabase_kb.supabase = mock_supabase
        
        result = await supabase_kb.create_chat_session(user_id="user-123")
        
        assert result is not None
        assert result["title"] == "New Chat"
    
    @pytest.mark.asyncio
    async def test_get_chat_session_found(self, supabase_kb, mock_supabase):
        """Test retrieving an existing chat session."""
        session_id = str(uuid4())
        mock_response = MagicMock()
        mock_response.data = [{
            "id": session_id,
            "user_id": "user-123",
            "title": "Test Chat",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "metadata": {}
        }]
        mock_supabase.execute = MagicMock(return_value=mock_response)
        supabase_kb.supabase = mock_supabase
        
        result = await supabase_kb.get_chat_session(session_id=session_id)
        
        assert result is not None
        assert result["id"] == session_id
        mock_supabase.table.assert_called_with("chat_sessions")
        mock_supabase.eq.assert_called_with("id", session_id)
    
    @pytest.mark.asyncio
    async def test_get_chat_session_not_found(self, supabase_kb, mock_supabase):
        """Test retrieving a non-existent chat session."""
        mock_response = MagicMock()
        mock_response.data = []
        mock_supabase.execute = MagicMock(return_value=mock_response)
        supabase_kb.supabase = mock_supabase
        
        result = await supabase_kb.get_chat_session(session_id=str(uuid4()))
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_user_chat_sessions(self, supabase_kb, mock_supabase):
        """Test retrieving all sessions for a user."""
        sessions = [
            {
                "id": str(uuid4()),
                "user_id": "user-123",
                "title": f"Chat {i}",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "metadata": {}
            }
            for i in range(3)
        ]
        mock_response = MagicMock()
        mock_response.data = sessions
        mock_supabase.execute = MagicMock(return_value=mock_response)
        supabase_kb.supabase = mock_supabase
        
        result = await supabase_kb.get_user_chat_sessions(user_id="user-123", limit=10)
        
        assert len(result) == 3
        assert all(s["user_id"] == "user-123" for s in result)
        mock_supabase.eq.assert_called_with("user_id", "user-123")
        mock_supabase.order.assert_called_with("updated_at", desc=True)
    
    @pytest.mark.asyncio
    async def test_update_chat_session(self, supabase_kb, mock_supabase):
        """Test updating a chat session's title and metadata."""
        session_id = str(uuid4())
        mock_response = MagicMock()
        mock_response.data = [{"id": session_id}]
        mock_supabase.execute = MagicMock(return_value=mock_response)
        supabase_kb.supabase = mock_supabase
        
        result = await supabase_kb.update_chat_session(
            session_id=session_id,
            title="Updated Title",
            metadata={"updated": True}
        )
        
        assert result is True
        mock_supabase.table.assert_called_with("chat_sessions")
        mock_supabase.update.assert_called_once()
        mock_supabase.eq.assert_called_with("id", session_id)


class TestChatMessages:
    """Tests for chat message operations."""
    
    @pytest.mark.asyncio
    async def test_append_chat_message_success(self, supabase_kb, mock_supabase):
        """Test appending a message to a chat session."""
        session_id = str(uuid4())
        message_id = str(uuid4())
        
        # Mock session ownership check
        session_response = MagicMock()
        session_response.data = [{"user_id": "user-123"}]
        
        # Mock message count query
        count_response = MagicMock()
        count_response.data = []
        
        # Mock message insert
        insert_response = MagicMock()
        insert_response.data = [{
            "id": message_id,
            "session_id": session_id,
            "user_id": "user-123",
            "role": "user",
            "content": "Hello!",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "ordering": 0,
            "metadata": {"tokens": 5}
        }]
        
        # Mock returns different responses for each execute call
        mock_supabase.execute = MagicMock(side_effect=[session_response, count_response, insert_response])
        supabase_kb.supabase = mock_supabase
        
        result = await supabase_kb.append_chat_message(
            session_id=session_id,
            user_id="user-123",
            role="user",
            content="Hello!",
            metadata={"tokens": 5}
        )
        
        assert result is not None
        assert result["id"] == message_id
        assert result["role"] == "user"
        assert result["content"] == "Hello!"
    
    @pytest.mark.asyncio
    async def test_get_chat_messages(self, supabase_kb, mock_supabase):
        """Test retrieving messages from a chat session."""
        session_id = str(uuid4())
        messages = [
            {
                "id": str(uuid4()),
                "session_id": session_id,
                "user_id": "user-123",
                "role": "user" if i % 2 == 0 else "assistant",
                "content": f"Message {i}",
                "created_at": (datetime.now(timezone.utc) + timedelta(seconds=i)).isoformat(),
                "metadata": {}
            }
            for i in range(5)
        ]
        mock_response = MagicMock()
        mock_response.data = messages
        mock_supabase.execute = MagicMock(return_value=mock_response)
        supabase_kb.supabase = mock_supabase
        
        result = await supabase_kb.get_chat_messages(session_id=session_id, limit=10)
        
        assert len(result) == 5
        assert all(m["session_id"] == session_id for m in result)
        mock_supabase.eq.assert_called_with("session_id", session_id)
        mock_supabase.order.assert_called_with("created_at", desc=False)
    
    @pytest.mark.asyncio
    async def test_get_chat_history(self, supabase_kb, mock_supabase):
        """Test retrieving chat history with messages."""
        session_id = str(uuid4())
        sessions = [{
            "id": session_id,
            "user_id": "user-123",
            "title": "Test Chat",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "metadata": {}
        }]
        messages = [{
            "id": str(uuid4()),
            "session_id": session_id,
            "user_id": "user-123",
            "role": "user",
            "content": "Hello!",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "metadata": {}
        }]
        
        # Mock two different responses for sessions and messages
        mock_sessions_response = MagicMock()
        mock_sessions_response.data = sessions
        mock_messages_response = MagicMock()
        mock_messages_response.data = messages
        
        call_count = [0]
        def execute_side_effect():
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_sessions_response
            return mock_messages_response
        
        mock_supabase.execute = MagicMock(side_effect=execute_side_effect)
        supabase_kb.supabase = mock_supabase
        
        result = await supabase_kb.get_chat_history(user_id="user-123", limit_sessions=10)
        
        assert len(result) == 1
        assert result[0]["id"] == session_id
        assert "messages" in result[0]
        assert len(result[0]["messages"]) == 1


class TestLLMCaching:
    """Tests for LLM response caching."""
    
    def test_generate_prompt_hash(self, supabase_kb):
        """Test prompt hash generation."""
        hash1 = supabase_kb._generate_prompt_hash(
            prompt="What is the weather?",
            provider="openai",
            model="gpt-4"
        )
        hash2 = supabase_kb._generate_prompt_hash(
            prompt="What is the weather?",
            provider="openai",
            model="gpt-4"
        )
        hash3 = supabase_kb._generate_prompt_hash(
            prompt="What is the weather?",
            provider="anthropic",
            model="claude-3-opus"
        )
        
        assert hash1 == hash2  # Same prompt, same hash
        assert hash1 != hash3  # Different provider, different hash
        assert len(hash1) == 64  # SHA256 produces 64 char hex string
    
    def test_generate_prompt_hash_with_params(self, supabase_kb):
        """Test prompt hash generation with parameters."""
        hash1 = supabase_kb._generate_prompt_hash(
            prompt="Test prompt",
            provider="openai",
            model="gpt-4",
            parameters={"temperature": 0.7, "max_tokens": 100}
        )
        hash2 = supabase_kb._generate_prompt_hash(
            prompt="Test prompt",
            provider="openai",
            model="gpt-4",
            parameters={"max_tokens": 100, "temperature": 0.7}  # Different order
        )
        hash3 = supabase_kb._generate_prompt_hash(
            prompt="Test prompt",
            provider="openai",
            model="gpt-4",
            parameters={"temperature": 0.8, "max_tokens": 100}  # Different value
        )
        
        assert hash1 == hash2  # Same params, order doesn't matter
        assert hash1 != hash3  # Different params, different hash
    
    def test_generate_prompt_hash_normalization(self, supabase_kb):
        """Test prompt normalization in hash generation."""
        hash1 = supabase_kb._generate_prompt_hash(
            prompt="What   is    the weather?",
            provider="openai",
            model="gpt-4"
        )
        hash2 = supabase_kb._generate_prompt_hash(
            prompt="What is the weather?",
            provider="openai",
            model="gpt-4"
        )
        
        assert hash1 == hash2  # Extra whitespace normalized
    
    @pytest.mark.asyncio
    async def test_get_cached_llm_response_hit(self, supabase_kb, mock_supabase):
        """Test cache hit for LLM response."""
        cache_id = str(uuid4())
        prompt_hash = "test-hash"
        mock_response = MagicMock()
        mock_response.data = [{
            "id": cache_id,
            "prompt_hash": prompt_hash,
            "prompt": "Test prompt",
            "provider": "openai",
            "model": "gpt-4",
            "response": "Test response",
            "metadata": {"tokens": 100},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            "hit_count": 5
        }]
        mock_supabase.execute = MagicMock(return_value=mock_response)
        supabase_kb.supabase = mock_supabase
        
        result = await supabase_kb.get_cached_llm_response(
            prompt="Test prompt",
            provider="openai",
            model="gpt-4"
        )
        
        assert result is not None
        assert result["cached"] is True
        assert result["response"] == "Test response"
        assert result["metadata"]["tokens"] == 100
        assert result["hit_count"] == 5
        mock_supabase.table.assert_called_with("llm_response_cache")
    
    @pytest.mark.asyncio
    async def test_get_cached_llm_response_miss(self, supabase_kb, mock_supabase):
        """Test cache miss for LLM response."""
        mock_response = MagicMock()
        mock_response.data = []
        mock_supabase.execute = MagicMock(return_value=mock_response)
        supabase_kb.supabase = mock_supabase
        
        result = await supabase_kb.get_cached_llm_response(
            prompt="Test prompt",
            provider="openai",
            model="gpt-4"
        )
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_cache_llm_response_success(self, supabase_kb, mock_supabase):
        """Test caching an LLM response."""
        cache_id = str(uuid4())
        mock_response = MagicMock()
        mock_response.data = [{"id": cache_id}]
        mock_supabase.execute = MagicMock(return_value=mock_response)
        supabase_kb.supabase = mock_supabase
        
        result = await supabase_kb.cache_llm_response(
            prompt="Test prompt",
            provider="openai",
            model="gpt-4",
            response="Test response",
            metadata={"tokens": 100},
            ttl_hours=168
        )
        
        assert result is True
        mock_supabase.table.assert_called_with("llm_response_cache")
        mock_supabase.upsert.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cache_llm_response_empty_response(self, supabase_kb, mock_supabase):
        """Test that empty responses are not cached."""
        supabase_kb.supabase = mock_supabase
        
        result = await supabase_kb.cache_llm_response(
            prompt="Test prompt",
            provider="openai",
            model="gpt-4",
            response="",
            metadata={}
        )
        
        assert result is False
        mock_supabase.insert.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_cache_llm_response_with_embedding(self, supabase_kb, mock_supabase):
        """Test caching an LLM response with embedding vector."""
        cache_id = str(uuid4())
        mock_response = MagicMock()
        mock_response.data = [{"id": cache_id}]
        mock_supabase.execute = MagicMock(return_value=mock_response)
        supabase_kb.supabase = mock_supabase
        
        embedding = [0.1, 0.2, 0.3, 0.4]
        result = await supabase_kb.cache_llm_response(
            prompt="Test prompt",
            provider="openai",
            model="gpt-4",
            response="Test response",
            embedding=embedding
        )
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_llm_cache(self, supabase_kb, mock_supabase):
        """Test cleaning up expired LLM cache entries."""
        expired_ids = [str(uuid4()) for _ in range(3)]
        mock_select_response = MagicMock()
        mock_select_response.data = [{"id": id} for id in expired_ids]
        mock_delete_response = MagicMock()
        mock_delete_response.data = expired_ids
        
        call_count = [0]
        def execute_side_effect():
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_select_response
            return mock_delete_response
        
        mock_supabase.execute = MagicMock(side_effect=execute_side_effect)
        supabase_kb.supabase = mock_supabase
        
        result = await supabase_kb.cleanup_expired_llm_cache()
        
        assert result == 3
        mock_supabase.table.assert_called_with("llm_response_cache")


class TestTokenUsageTracking:
    """Tests for token usage tracking and quotas."""
    
    @pytest.mark.asyncio
    async def test_record_token_usage_new_record(self, supabase_kb, mock_supabase):
        """Test recording token usage for a new day."""
        mock_select_response = MagicMock()
        mock_select_response.data = []
        mock_insert_response = MagicMock()
        mock_insert_response.data = [{"id": str(uuid4())}]
        
        call_count = [0]
        def execute_side_effect():
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_select_response
            return mock_insert_response
        
        mock_supabase.execute = MagicMock(side_effect=execute_side_effect)
        supabase_kb.supabase = mock_supabase
        
        result = await supabase_kb.record_token_usage(
            user_id="user-123",
            tokens_consumed=100,
            provider="openai",
            model="gpt-4"
        )
        
        assert result is True
        mock_supabase.insert.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_record_token_usage_update_existing(self, supabase_kb, mock_supabase):
        """Test updating existing token usage record."""
        stat_id = str(uuid4())
        mock_select_response = MagicMock()
        mock_select_response.data = [{
            "id": stat_id,
            "user_id": "user-123",
            "tokens_consumed": 100,
            "requests_count": 5,
            "metadata": {
                "providers": {
                    "openai": {
                        "gpt-4": {
                            "tokens": 100,
                            "requests": 5
                        }
                    }
                }
            }
        }]
        mock_update_response = MagicMock()
        mock_update_response.data = [{"id": stat_id}]
        
        call_count = [0]
        def execute_side_effect():
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_select_response
            return mock_update_response
        
        mock_supabase.execute = MagicMock(side_effect=execute_side_effect)
        supabase_kb.supabase = mock_supabase
        
        result = await supabase_kb.record_token_usage(
            user_id="user-123",
            tokens_consumed=50,
            provider="openai",
            model="gpt-4"
        )
        
        assert result is True
        mock_supabase.update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_record_token_usage_zero_tokens(self, supabase_kb, mock_supabase):
        """Test that zero tokens are not recorded."""
        supabase_kb.supabase = mock_supabase
        
        result = await supabase_kb.record_token_usage(
            user_id="user-123",
            tokens_consumed=0,
            provider="openai",
            model="gpt-4"
        )
        
        assert result is True
        mock_supabase.insert.assert_not_called()
        mock_supabase.update.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_get_user_token_usage(self, supabase_kb, mock_supabase):
        """Test retrieving user token usage statistics."""
        daily_stats = [
            {
                "id": str(uuid4()),
                "user_id": "user-123",
                "period_start": (datetime.now(timezone.utc) - timedelta(days=i)).date().isoformat(),
                "tokens_consumed": 100 * (i + 1),
                "requests_count": 5 * (i + 1),
                "metadata": {
                    "providers": {
                        "openai": {
                            "gpt-4": {
                                "tokens": 100 * (i + 1),
                                "requests": 5 * (i + 1)
                            }
                        }
                    }
                }
            }
            for i in range(3)
        ]
        mock_response = MagicMock()
        mock_response.data = daily_stats
        mock_supabase.execute = MagicMock(return_value=mock_response)
        supabase_kb.supabase = mock_supabase
        
        result = await supabase_kb.get_user_token_usage(user_id="user-123", days=30)
        
        assert result["total_tokens"] == 600  # 100 + 200 + 300
        assert result["total_requests"] == 30  # 5 + 10 + 15
        assert "daily_breakdown" in result
        assert "provider_breakdown" in result
        assert "openai" in result["provider_breakdown"]
        assert "gpt-4" in result["provider_breakdown"]["openai"]
    
    @pytest.mark.asyncio
    async def test_check_user_quota_under_limit(self, supabase_kb, mock_supabase):
        """Test checking quota when user is under limit."""
        # Mock get_user_token_usage response
        daily_stats = [{
            "id": str(uuid4()),
            "user_id": "user-123",
            "tokens_consumed": 500,
            "requests_count": 10,
            "metadata": {"providers": {}}
        }]
        mock_usage_response = MagicMock()
        mock_usage_response.data = daily_stats
        
        # Mock get_user_preferences response
        mock_prefs_response = MagicMock()
        mock_prefs_response.data = [{
            "user_id": "user-123",
            "preferences": {
                "daily_token_quota": 1000,
                "monthly_token_quota": 30000
            }
        }]
        
        call_count = [0]
        def execute_side_effect():
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_usage_response
            return mock_prefs_response
        
        mock_supabase.execute = MagicMock(side_effect=execute_side_effect)
        supabase_kb.supabase = mock_supabase
        
        result = await supabase_kb.check_user_quota(user_id="user-123", quota_period="daily")
        
        assert result["quota_limit"] == 1000
        assert result["tokens_used"] == 500
        assert result["remaining"] == 500
        assert result["is_over_quota"] is False
    
    @pytest.mark.asyncio
    async def test_check_user_quota_over_limit(self, supabase_kb, mock_supabase):
        """Test checking quota when user is over limit."""
        # Mock get_user_token_usage response
        daily_stats = [{
            "id": str(uuid4()),
            "user_id": "user-123",
            "tokens_consumed": 1500,
            "requests_count": 30,
            "metadata": {"providers": {}}
        }]
        mock_usage_response = MagicMock()
        mock_usage_response.data = daily_stats
        
        # Mock get_user_preferences response
        mock_prefs_response = MagicMock()
        mock_prefs_response.data = [{
            "user_id": "user-123",
            "preferences": {
                "daily_token_quota": 1000,
                "monthly_token_quota": 30000
            }
        }]
        
        call_count = [0]
        def execute_side_effect():
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_usage_response
            return mock_prefs_response
        
        mock_supabase.execute = MagicMock(side_effect=execute_side_effect)
        supabase_kb.supabase = mock_supabase
        
        result = await supabase_kb.check_user_quota(user_id="user-123", quota_period="daily")
        
        assert result["quota_limit"] == 1000
        assert result["tokens_used"] == 1500
        assert result["remaining"] == 0
        assert result["is_over_quota"] is True
    
    @pytest.mark.asyncio
    async def test_check_user_quota_no_limit(self, supabase_kb, mock_supabase):
        """Test checking quota when user has no quota limit set."""
        # Mock get_user_token_usage response
        daily_stats = [{
            "id": str(uuid4()),
            "user_id": "user-123",
            "tokens_consumed": 500,
            "requests_count": 10,
            "metadata": {"providers": {}}
        }]
        mock_usage_response = MagicMock()
        mock_usage_response.data = daily_stats
        
        # Mock get_user_preferences response (no quota set)
        mock_prefs_response = MagicMock()
        mock_prefs_response.data = [{
            "user_id": "user-123",
            "preferences": {}
        }]
        
        call_count = [0]
        def execute_side_effect():
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_usage_response
            return mock_prefs_response
        
        mock_supabase.execute = MagicMock(side_effect=execute_side_effect)
        supabase_kb.supabase = mock_supabase
        
        result = await supabase_kb.check_user_quota(user_id="user-123", quota_period="daily")
        
        assert result["quota_limit"] is None
        assert result["tokens_used"] == 500
        assert result["remaining"] is None
        assert result["is_over_quota"] is False


class TestBackwardCompatibility:
    """Tests to ensure backward compatibility with existing functionality."""
    
    @pytest.mark.asyncio
    async def test_existing_methods_still_work(self, supabase_kb, mock_supabase):
        """Test that existing cache methods still work with user_id."""
        mock_response = MagicMock()
        mock_response.data = []
        mock_supabase.execute = MagicMock(return_value=mock_response)
        supabase_kb.supabase = mock_supabase
        
        # Test existing method with user_id (required for cache isolation)
        result = await supabase_kb.get_cached_query(
            sql="SELECT * FROM test",
            use_cache=True,
            user_id="user-123"
        )
        
        assert result is None  # Cache miss
        mock_supabase.table.assert_called_with("query_cache")
    
    @pytest.mark.asyncio
    async def test_connection_verification_required(self, supabase_kb):
        """Test that methods check connection before proceeding."""
        supabase_kb._connection_verified = False
        
        # Chat methods
        result = await supabase_kb.create_chat_session(user_id="user-123")
        assert result is None
        
        result = await supabase_kb.get_chat_session(session_id="test-id")
        assert result is None
        
        result = await supabase_kb.get_user_chat_sessions(user_id="user-123")
        assert result == []
        
        # LLM cache methods
        result = await supabase_kb.get_cached_llm_response(
            prompt="test", provider="openai", model="gpt-4"
        )
        assert result is None
        
        result = await supabase_kb.cache_llm_response(
            prompt="test", provider="openai", model="gpt-4", response="test"
        )
        assert result is False
        
        # Usage tracking methods
        result = await supabase_kb.record_token_usage(
            user_id="user-123", tokens_consumed=100, provider="openai", model="gpt-4"
        )
        assert result is False


class TestErrorHandling:
    """Tests for error handling and graceful failures."""
    
    @pytest.mark.asyncio
    async def test_create_chat_session_table_missing(self, supabase_kb, mock_supabase):
        """Test graceful handling when chat_sessions table doesn't exist."""
        from postgrest.exceptions import APIError
        
        mock_supabase.execute = MagicMock(side_effect=APIError({"message": "Table not found"}))
        supabase_kb.supabase = mock_supabase
        
        # The method returns None instead of raising, and logs the error
        result = await supabase_kb.create_chat_session(user_id="user-123")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_append_chat_message_table_missing(self, supabase_kb, mock_supabase):
        """Test graceful handling when chat_messages table doesn't exist."""
        from postgrest.exceptions import APIError
        
        mock_supabase.execute = MagicMock(side_effect=APIError({"message": "Table not found"}))
        supabase_kb.supabase = mock_supabase
        
        # The method returns None instead of raising, and logs the error
        result = await supabase_kb.append_chat_message(
            session_id="test-id",
            user_id="user-123",
            role="user",
            content="test"
        )
        assert result is None
    
    @pytest.mark.asyncio
    async def test_cache_llm_response_error_handling(self, supabase_kb, mock_supabase):
        """Test error handling when caching LLM response fails."""
        mock_supabase.execute = MagicMock(side_effect=Exception("Database error"))
        supabase_kb.supabase = mock_supabase
        
        result = await supabase_kb.cache_llm_response(
            prompt="test",
            provider="openai",
            model="gpt-4",
            response="test response"
        )
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_record_token_usage_error_handling(self, supabase_kb, mock_supabase):
        """Test error handling when recording token usage fails."""
        mock_supabase.execute = MagicMock(side_effect=Exception("Database error"))
        supabase_kb.supabase = mock_supabase
        
        result = await supabase_kb.record_token_usage(
            user_id="user-123",
            tokens_consumed=100,
            provider="openai",
            model="gpt-4"
        )
        
        assert result is False
