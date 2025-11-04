"""Tests for tool message formatting fix.

This test verifies that tool result messages are properly formatted
with the required OpenAI message structure:
1. User message
2. Assistant message with tool_calls
3. Tool result messages with tool_call_id
"""

import pytest
from unittest.mock import AsyncMock, Mock
import json

from src.mcp_bigquery.agent.conversation import InsightsAgent
from src.mcp_bigquery.agent.models import AgentRequest
from src.mcp_bigquery.agent.mcp_client import DatasetInfo
from src.mcp_bigquery.llm.providers.base import (
    Message,
    GenerationResponse,
    ToolCall,
)


@pytest.fixture
def mock_mcp_client():
    """Create a mock MCP client."""
    client = AsyncMock()
    client.list_datasets = AsyncMock(return_value=[
        DatasetInfo(dataset_id="Analytics", project_id="test-project"),
        DatasetInfo(dataset_id="Sales", project_id="test-project"),
    ])
    return client


@pytest.fixture
def mock_kb():
    """Create a mock knowledge base."""
    kb = AsyncMock()
    kb.get_chat_messages = AsyncMock(return_value=[])
    kb.append_chat_message = AsyncMock()
    return kb


class TestToolMessageFormatting:
    """Tests for tool message formatting."""
    
    @pytest.mark.asyncio
    async def test_assistant_message_includes_tool_calls(self, mock_mcp_client, mock_kb):
        """Test that assistant message with tool_calls is properly added before tool results."""
        
        # Track the messages sent to LLM
        messages_sent = []
        
        def capture_messages(messages, **kwargs):
            """Capture messages sent to LLM."""
            messages_sent.append([msg for msg in messages])
            
            # First call: LLM requests tool call
            if len(messages_sent) == 1:
                return GenerationResponse(
                    content=None,
                    tool_calls=[
                        ToolCall(id="call_123", name="list_datasets", arguments={})
                    ],
                    finish_reason="tool_calls"
                )
            # Second call: LLM provides final answer
            else:
                return GenerationResponse(
                    content="You have access to 2 datasets: Analytics and Sales.",
                    tool_calls=[],
                    finish_reason="stop"
                )
        
        mock_llm = Mock()
        mock_llm.provider_name = "openai"
        mock_llm.config = Mock(model="gpt-4o")
        mock_llm.supports_functions = Mock(return_value=True)
        mock_llm.generate = AsyncMock(side_effect=capture_messages)
        
        agent = InsightsAgent(
            llm_provider=mock_llm,
            mcp_client=mock_mcp_client,
            kb=mock_kb,
            project_id="test-project",
            enable_tool_selection=True
        )
        
        request = AgentRequest(
            question="what datasets do we have?",
            session_id="test_session",
            user_id="test_user",
            allowed_datasets={"*"},
            allowed_tables={}
        )
        
        response = await agent.process_question(request)
        
        # Verify response is successful
        assert response.success is True
        assert "datasets" in response.answer.lower() or "Analytics" in response.answer
        
        # Verify LLM was called twice
        assert len(messages_sent) == 2
        
        # Check first call (tool selection)
        first_call_messages = messages_sent[0]
        assert any(msg.role == "system" for msg in first_call_messages)
        assert any(msg.role == "user" for msg in first_call_messages)
        
        # Check second call (final response) - THIS IS THE CRITICAL FIX
        second_call_messages = messages_sent[1]
        
        # Find assistant message with tool_calls
        assistant_with_tools = None
        tool_messages = []
        
        for msg in second_call_messages:
            if msg.role == "assistant" and msg.tool_calls:
                assistant_with_tools = msg
            elif msg.role == "tool":
                tool_messages.append(msg)
        
        # CRITICAL ASSERTIONS - These would fail before the fix
        assert assistant_with_tools is not None, "Assistant message with tool_calls must be present"
        assert len(assistant_with_tools.tool_calls) == 1, "Assistant message must have tool_calls"
        assert assistant_with_tools.tool_calls[0].id == "call_123", "Tool call ID must match"
        assert assistant_with_tools.tool_calls[0].name == "list_datasets", "Tool name must be correct"
        
        # Verify tool message has tool_call_id
        assert len(tool_messages) == 1, "Tool result message must be present"
        assert tool_messages[0].tool_call_id == "call_123", "Tool message must have tool_call_id"
        assert tool_messages[0].content is not None, "Tool message must have content"
        
        # Verify message order: assistant with tool_calls comes BEFORE tool results
        assistant_idx = second_call_messages.index(assistant_with_tools)
        tool_idx = second_call_messages.index(tool_messages[0])
        assert assistant_idx < tool_idx, "Assistant message must come before tool result"
    
    @pytest.mark.asyncio
    async def test_message_format_matches_openai_requirements(self, mock_mcp_client, mock_kb):
        """Test that message format exactly matches OpenAI API requirements."""
        
        # Track the actual OpenAI-formatted messages
        openai_messages_sent = []
        
        async def mock_openai_generate(messages, **kwargs):
            """Mock OpenAI generate that validates message format."""
            # Convert Message objects to OpenAI format (as the provider does)
            openai_msgs = []
            for msg in messages:
                openai_msg = {
                    "role": msg.role,
                    "content": msg.content
                }
                
                if msg.role == "assistant" and msg.tool_calls:
                    openai_msg["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments)
                            }
                        }
                        for tc in msg.tool_calls
                    ]
                
                if msg.role == "tool" and msg.tool_call_id:
                    openai_msg["tool_call_id"] = msg.tool_call_id
                
                openai_msgs.append(openai_msg)
            
            openai_messages_sent.append(openai_msgs)
            
            # Validate OpenAI requirements for tool messages
            if len(openai_messages_sent) > 1:
                # Second call should have proper tool message format
                for i, msg in enumerate(openai_msgs):
                    if msg["role"] == "tool":
                        # Find the preceding assistant message
                        found_tool_calls = False
                        for j in range(i - 1, -1, -1):
                            if openai_msgs[j]["role"] == "assistant" and "tool_calls" in openai_msgs[j]:
                                found_tool_calls = True
                                break
                        
                        # This is the OpenAI requirement that was failing
                        if not found_tool_calls:
                            raise ValueError(
                                "Invalid parameter: messages with role 'tool' must be a "
                                "response to a preceeding message with 'tool_calls'."
                            )
                        
                        # Tool message must have tool_call_id
                        if "tool_call_id" not in msg:
                            raise ValueError("Tool message must have tool_call_id")
            
            # Return mock responses
            if len(openai_messages_sent) == 1:
                return GenerationResponse(
                    content=None,
                    tool_calls=[ToolCall(id="call_abc", name="list_datasets", arguments={})],
                    finish_reason="tool_calls"
                )
            else:
                return GenerationResponse(
                    content="You have 2 datasets.",
                    tool_calls=[],
                    finish_reason="stop"
                )
        
        mock_llm = Mock()
        mock_llm.provider_name = "openai"
        mock_llm.config = Mock(model="gpt-4o")
        mock_llm.supports_functions = Mock(return_value=True)
        mock_llm.generate = AsyncMock(side_effect=mock_openai_generate)
        
        agent = InsightsAgent(
            llm_provider=mock_llm,
            mcp_client=mock_mcp_client,
            kb=mock_kb,
            project_id="test-project",
            enable_tool_selection=True
        )
        
        request = AgentRequest(
            question="show datasets",
            session_id="test_session",
            user_id="test_user",
            allowed_datasets={"*"},
            allowed_tables={}
        )
        
        # This should NOT raise the OpenAI validation error
        response = await agent.process_question(request)
        
        assert response.success is True
        assert len(openai_messages_sent) == 2
