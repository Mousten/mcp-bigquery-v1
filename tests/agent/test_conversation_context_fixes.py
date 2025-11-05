"""Tests for conversation context management fixes.

This module tests the fixes for:
1. Recursive summarization loop
2. Message truncation
3. Duplicate message history
4. Tool calling behavior
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from mcp_bigquery.agent.conversation_manager import ConversationManager
from mcp_bigquery.agent.conversation import InsightsAgent
from mcp_bigquery.agent.models import AgentRequest, AgentResponse, ConversationContext
from mcp_bigquery.llm.providers import (
    Message,
    GenerationResponse,
    LLMProviderConfig,
)


@pytest.fixture
def mock_llm_provider():
    """Create a mock LLM provider with function calling support."""
    provider = MagicMock()
    provider.provider_name = "openai"
    provider.config = LLMProviderConfig(
        api_key="test-key",
        model="gpt-4o",
        temperature=0.7
    )
    provider.generate = AsyncMock(return_value=GenerationResponse(
        content="Test response",
        usage={"total_tokens": 100, "prompt_tokens": 50, "completion_tokens": 50}
    ))
    provider.count_tokens = MagicMock(return_value=20)
    provider.count_messages_tokens = MagicMock(return_value=50)
    provider.supports_functions = MagicMock(return_value=True)
    return provider


@pytest.fixture
def mock_mcp_client():
    """Create a mock MCP client."""
    client = MagicMock()
    client.execute_sql = AsyncMock(return_value={
        "rows": [{"id": 1, "name": "test"}],
        "schema": [
            {"name": "id", "type": "INTEGER"},
            {"name": "name", "type": "STRING"}
        ]
    })
    client.list_datasets = AsyncMock(return_value={"datasets": []})
    client.list_tables = AsyncMock(return_value={"tables": []})
    client.get_table_schema = AsyncMock(return_value={"schema": []})
    return client


@pytest.fixture
def mock_kb():
    """Create a mock knowledge base."""
    kb = MagicMock()
    kb.get_chat_messages = AsyncMock(return_value=[])
    kb.append_chat_message = AsyncMock()
    kb.cache_llm_response = AsyncMock()
    kb.get_cached_llm_response = AsyncMock(return_value=None)
    kb.check_user_quota = AsyncMock(return_value={
        "quota_limit": 10000,
        "tokens_used": 1000,
        "remaining": 9000,
        "is_over_quota": False,
        "quota_period": "daily"
    })
    kb.record_token_usage = AsyncMock(return_value=True)
    return kb


@pytest.mark.asyncio
async def test_no_recursive_summarization(mock_llm_provider, mock_mcp_client, mock_kb):
    """Test that summarization doesn't include existing summaries (Issue 1)."""
    manager = ConversationManager(
        mcp_client=mock_mcp_client,
        kb=mock_kb,
        project_id="test-project",
        provider=mock_llm_provider,
        context_summarization_threshold=5
    )
    
    # Create messages with existing summary
    messages = [
        {"role": "system", "content": "Previous conversation summary:\nuser: old question\nassistant: old answer"},
        {"role": "user", "content": "Question 1"},
        {"role": "assistant", "content": "Answer 1"},
        {"role": "user", "content": "Question 2"},
        {"role": "assistant", "content": "Answer 2"},
        {"role": "user", "content": "Question 3"},
        {"role": "assistant", "content": "Answer 3"},
        {"role": "user", "content": "Question 4"},
        {"role": "assistant", "content": "Answer 4"},
        {"role": "user", "content": "Question 5"},
        {"role": "assistant", "content": "Answer 5"},
    ]
    
    await manager._summarize_old_context(
        session_id="test-session",
        user_id="test-user",
        messages=messages
    )
    
    # Check that append_chat_message was called
    assert mock_kb.append_chat_message.called
    
    # Get the summary content
    call_args = mock_kb.append_chat_message.call_args
    summary_content = call_args[1]["content"]
    
    # Verify the summary doesn't contain nested "Previous conversation summary:"
    assert summary_content.count("Previous conversation summary:") == 1, \
        "Summary should not contain nested summaries"
    
    # Verify the summary doesn't start with "system: Previous conversation summary:"
    assert not summary_content.startswith("system: Previous conversation summary:"), \
        "Summary should not include the role prefix of previous summaries"


@pytest.mark.asyncio
async def test_no_message_truncation_mid_word(mock_llm_provider, mock_mcp_client, mock_kb):
    """Test that messages are not truncated mid-word (Issue 2)."""
    manager = ConversationManager(
        mcp_client=mock_mcp_client,
        kb=mock_kb,
        project_id="test-project",
        provider=mock_llm_provider,
        context_summarization_threshold=2,  # Lower threshold to trigger summarization
        max_context_turns=1  # Keep only 1 turn (2 messages) recent
    )
    
    # Create messages with long content (need more than max_context_turns * 2)
    long_content = "Brand_Name Location_Code Sales_Amount Revenue_Total Customer_Count Store_Identifier" * 10
    messages = [
        {"role": "user", "content": long_content},
        {"role": "assistant", "content": "Short answer"},
        {"role": "user", "content": "Question 2"},
        {"role": "assistant", "content": "Answer 2"},
        {"role": "user", "content": "Question 3"},
        {"role": "assistant", "content": "Answer 3"},
    ]
    
    await manager._summarize_old_context(
        session_id="test-session",
        user_id="test-user",
        messages=messages
    )
    
    # Verify append_chat_message was called
    assert mock_kb.append_chat_message.called, "Summary should have been created"
    
    # Get the summary content
    call_args = mock_kb.append_chat_message.call_args
    summary_content = call_args[1]["content"]
    
    # Verify no incomplete words (no trailing partial words without ...)
    # Check that if content is truncated, it ends with "..." or a complete word
    lines = summary_content.split('\n')[1:]  # Skip the "Previous conversation summary:" line
    for line in lines:
        if line.strip():
            # If line is truncated (contains ...), verify it's at a word boundary
            if "..." in line:
                before_ellipsis = line.split("...")[0]
                # Should end with a space or complete word
                assert before_ellipsis.endswith(" ") or before_ellipsis[-1].isalnum(), \
                    f"Truncated line should end at word boundary: {line}"
            else:
                # Non-truncated lines should not end mid-word with special chars (except punctuation)
                # This checks we're not cutting like "Brand_" or "Location ("
                last_chars = line.strip()[-2:] if len(line.strip()) >= 2 else line.strip()
                # Allow normal punctuation and complete words, but not incomplete tokens
                assert not (last_chars[-1] in "_(" and not last_chars.endswith("...")), \
                    f"Line should not end with incomplete token: {line}"


@pytest.mark.asyncio
async def test_no_duplicate_messages(mock_llm_provider, mock_mcp_client, mock_kb):
    """Test that messages are deduplicated (Issue 4)."""
    agent = InsightsAgent(
        llm_provider=mock_llm_provider,
        mcp_client=mock_mcp_client,
        kb=mock_kb,
        project_id="test-project",
        enable_tool_selection=True
    )
    
    # Create duplicate messages
    messages = [
        {"role": "user", "content": "what columns does the table ANDO_Daily_Sales_KE have?"},
        {"role": "assistant", "content": "The table has columns: id, date, sales"},
        {"role": "user", "content": "what columns does the table ANDO_Daily_Sales_KE have?"},  # Duplicate
        {"role": "assistant", "content": "The table has columns: id, date, sales"},  # Duplicate
        {"role": "user", "content": "show me sales data"},
    ]
    
    # Test deduplication
    deduplicated = agent._deduplicate_messages(messages)
    
    # Should remove the duplicate question and answer
    assert len(deduplicated) == 3, f"Expected 3 unique messages, got {len(deduplicated)}"
    
    # Verify the first occurrence is kept
    assert deduplicated[0]["content"] == "what columns does the table ANDO_Daily_Sales_KE have?"
    assert deduplicated[1]["content"] == "The table has columns: id, date, sales"
    assert deduplicated[2]["content"] == "show me sales data"


@pytest.mark.asyncio
async def test_tool_selection_system_prompt_emphasizes_immediate_action(mock_llm_provider, mock_mcp_client, mock_kb):
    """Test that system prompt discourages narration (Issue 3)."""
    agent = InsightsAgent(
        llm_provider=mock_llm_provider,
        mcp_client=mock_mcp_client,
        kb=mock_kb,
        project_id="test-project",
        enable_tool_selection=True
    )
    
    context = ConversationContext(
        session_id="test-session",
        user_id="test-user",
        messages=[],
        allowed_datasets={"sales"},
        allowed_tables={"sales": {"orders"}}
    )
    
    prompt = agent._build_tool_selection_system_prompt(context)
    
    # Verify prompt discourages narration
    assert "CRITICAL - HOW TO USE TOOLS:" in prompt
    assert "DO NOT say" in prompt or "Don't say" in prompt.lower()
    assert "immediately" in prompt.lower() or "IMMEDIATELY" in prompt
    
    # Verify it shows correct and incorrect examples
    assert "WRONG:" in prompt or "❌" in prompt
    assert "RIGHT:" in prompt or "✅" in prompt
    
    # Verify it specifically mentions not to say "I will"
    assert "I will" in prompt


@pytest.mark.asyncio
async def test_context_validation_logs_incomplete_messages(mock_llm_provider, mock_mcp_client, mock_kb, caplog):
    """Test that incomplete messages are logged during context retrieval."""
    import logging
    
    agent = InsightsAgent(
        llm_provider=mock_llm_provider,
        mcp_client=mock_mcp_client,
        kb=mock_kb,
        project_id="test-project"
    )
    
    # Mock get_chat_messages to return messages with issues
    mock_kb.get_chat_messages = AsyncMock(return_value=[
        {"role": "user", "content": "Valid message"},
        {"role": "assistant"},  # Missing content
        {"role": "user", "content": 123},  # Non-string content
    ])
    
    with caplog.at_level(logging.WARNING):
        context = await agent._get_conversation_context(
            session_id="test-session",
            user_id="test-user",
            allowed_datasets={"sales"},
            allowed_tables={},
            context_turns=5
        )
    
    # Verify warnings were logged
    assert any("missing 'content' field" in record.message for record in caplog.records)
    assert any("non-string content" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_summarization_skips_when_only_summaries_exist(mock_llm_provider, mock_mcp_client, mock_kb, caplog):
    """Test that summarization is skipped when old messages are all summaries."""
    import logging
    
    manager = ConversationManager(
        mcp_client=mock_mcp_client,
        kb=mock_kb,
        project_id="test-project",
        provider=mock_llm_provider,
        context_summarization_threshold=2,
        max_context_turns=3  # Keep 3 turns (6 messages) recent
    )
    
    # Create messages where ALL old messages (beyond recent) are summaries
    # With max_context_turns=3, recent_messages = messages[:6], old_messages = messages[6:]
    # Recent: indexes 0-5 (first 6 messages) - these stay
    # Old: indexes 6-11 (last 6 messages) - these should all be summaries to test the fix
    messages = [
        {"role": "user", "content": "Question 1"},
        {"role": "assistant", "content": "Answer 1"},
        {"role": "user", "content": "Question 2"},
        {"role": "assistant", "content": "Answer 2"},
        {"role": "user", "content": "Question 3"},
        {"role": "assistant", "content": "Answer 3"},
        {"role": "system", "content": "Previous conversation summary:\nuser: q4\nassistant: a4"},
        {"role": "system", "content": "Previous conversation summary:\nuser: q5\nassistant: a5"},
        {"role": "system", "content": "Previous conversation summary:\nuser: q6\nassistant: a6"},
        {"role": "system", "content": "Previous conversation summary:\nuser: q7\nassistant: a7"},
        {"role": "system", "content": "Previous conversation summary:\nuser: q8\nassistant: a8"},
        {"role": "system", "content": "Previous conversation summary:\nuser: q9\nassistant: a9"},
    ]
    
    # Reset the mock to clear any previous calls
    mock_kb.append_chat_message.reset_mock()
    
    with caplog.at_level(logging.INFO):
        await manager._summarize_old_context(
            session_id="test-session",
            user_id="test-user",
            messages=messages
        )
    
    # Verify no new summary was created
    assert not mock_kb.append_chat_message.called, "No summary should be created when only summaries exist"
    
    # Verify appropriate log message
    log_messages = [record.message for record in caplog.records]
    assert any("No new messages to summarize" in msg for msg in log_messages), \
        f"Expected 'No new messages to summarize' in logs, got: {log_messages}"


@pytest.mark.asyncio
async def test_llm_response_without_tool_calls_is_logged(mock_llm_provider, mock_mcp_client, mock_kb, caplog):
    """Test that LLM responses without tool calls are logged as warnings (Issue 3)."""
    import logging
    
    # Mock LLM to return text response instead of tool calls
    mock_response = GenerationResponse(
        content="I will check the schema of this table and then calculate the results.",
        usage={"total_tokens": 50},
        tool_calls=[]  # Empty list, not None
    )
    mock_llm_provider.generate = AsyncMock(return_value=mock_response)
    
    agent = InsightsAgent(
        llm_provider=mock_llm_provider,
        mcp_client=mock_mcp_client,
        kb=mock_kb,
        project_id="test-project",
        enable_tool_selection=True
    )
    
    request = AgentRequest(
        question="what were the total sales yesterday?",
        session_id="test-session",
        user_id="test-user",
        allowed_datasets={"sales"}
    )
    
    mock_kb.get_chat_messages = AsyncMock(return_value=[])
    
    # Capture logs from the specific logger
    with caplog.at_level(logging.WARNING, logger="mcp_bigquery.agent.conversation"):
        response = await agent.process_question(request)
    
    # Get all log messages
    log_messages = [record.message for record in caplog.records]
    
    # Verify warning was logged about no tool calls
    assert any("responded with text instead of tool calls" in msg for msg in log_messages), \
        f"Expected warning about text response, got: {log_messages}"
    
    # Verify the narration content was logged
    assert any("I will check" in msg for msg in log_messages), \
        f"Expected logged content with 'I will check', got: {log_messages}"
