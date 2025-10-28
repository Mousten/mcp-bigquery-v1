"""Tests for Anthropic provider implementation."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import ValidationError

from mcp_bigquery.llm.providers import (
    AnthropicProvider,
    AnthropicProviderConfig,
    LLMConfigurationError,
    LLMGenerationError,
    Message,
    ToolDefinition,
)


@pytest.fixture
def anthropic_config():
    """Create a valid Anthropic config for testing."""
    return AnthropicProviderConfig(
        api_key="sk-ant-test-key-123",
        model="claude-3-5-sonnet-20241022",
        temperature=0.7,
        max_tokens=4096,
    )


class TestAnthropicProviderConfig:
    """Tests for Anthropic provider configuration."""
    
    def test_config_with_defaults(self):
        """Test config with default values."""
        config = AnthropicProviderConfig(api_key="sk-ant-test")
        assert config.model == "claude-3-5-sonnet-20241022"
        assert config.temperature == 0.7
        assert config.base_url is None
    
    def test_config_with_custom_values(self):
        """Test config with custom values."""
        config = AnthropicProviderConfig(
            api_key="sk-ant-test",
            model="claude-3-opus-20240229",
            temperature=0.5,
            base_url="https://custom.anthropic.com",
        )
        assert config.model == "claude-3-opus-20240229"
        assert config.base_url == "https://custom.anthropic.com"


class TestAnthropicProviderInitialization:
    """Tests for Anthropic provider initialization."""
    
    @patch('mcp_bigquery.llm.providers.anthropic_provider.AsyncAnthropic')
    def test_provider_initialization(self, mock_anthropic_class, anthropic_config):
        """Test successful provider initialization."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client
        
        provider = AnthropicProvider(anthropic_config)
        
        assert provider.config == anthropic_config
        assert provider.provider_name == "anthropic"
        mock_anthropic_class.assert_called_once()
    
    @patch('mcp_bigquery.llm.providers.anthropic_provider.AsyncAnthropic')
    def test_provider_initialization_failure(self, mock_anthropic_class):
        """Test provider initialization failure."""
        mock_anthropic_class.side_effect = Exception("Connection failed")
        
        config = AnthropicProviderConfig(api_key="sk-ant-test")
        with pytest.raises(LLMConfigurationError) as exc_info:
            AnthropicProvider(config)
        
        assert "Failed to initialize Anthropic client" in str(exc_info.value)


class TestAnthropicProviderGeneration:
    """Tests for Anthropic provider generation."""
    
    @pytest.mark.asyncio
    @patch('mcp_bigquery.llm.providers.anthropic_provider.AsyncAnthropic')
    async def test_generate_simple_message(self, mock_anthropic_class, anthropic_config):
        """Test generating a simple text response."""
        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = "Hello, how can I help you?"
        
        mock_response = MagicMock()
        mock_response.content = [mock_text_block]
        mock_response.stop_reason = "end_turn"
        mock_response.usage = MagicMock()
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 7
        
        mock_client = MagicMock()
        mock_client.messages = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_anthropic_class.return_value = mock_client
        
        provider = AnthropicProvider(anthropic_config)
        
        messages = [Message(role="user", content="Hi there")]
        response = await provider.generate(messages)
        
        assert response.content == "Hello, how can I help you?"
        assert response.finish_reason == "end_turn"
        assert response.usage["prompt_tokens"] == 10
        assert response.usage["completion_tokens"] == 7
        assert response.usage["total_tokens"] == 17
        assert not response.has_tool_calls()
    
    @pytest.mark.asyncio
    @patch('mcp_bigquery.llm.providers.anthropic_provider.AsyncAnthropic')
    async def test_generate_with_system_message(self, mock_anthropic_class, anthropic_config):
        """Test generating with a system message."""
        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = "Response"
        
        mock_response = MagicMock()
        mock_response.content = [mock_text_block]
        mock_response.stop_reason = "end_turn"
        mock_response.usage = None
        
        mock_client = MagicMock()
        mock_client.messages = MagicMock()
        mock_create = AsyncMock(return_value=mock_response)
        mock_client.messages.create = mock_create
        mock_anthropic_class.return_value = mock_client
        
        provider = AnthropicProvider(anthropic_config)
        
        messages = [
            Message(role="system", content="You are a helpful assistant"),
            Message(role="user", content="Hello")
        ]
        
        await provider.generate(messages)
        
        call_args = mock_create.call_args[1]
        assert "system" in call_args
        assert call_args["system"] == "You are a helpful assistant"
        assert len(call_args["messages"]) == 1
        assert call_args["messages"][0]["role"] == "user"
    
    @pytest.mark.asyncio
    @patch('mcp_bigquery.llm.providers.anthropic_provider.AsyncAnthropic')
    async def test_generate_with_tool_calls(self, mock_anthropic_class, anthropic_config):
        """Test generating a response with tool use."""
        mock_tool_block = MagicMock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.id = "call_123"
        mock_tool_block.name = "get_weather"
        mock_tool_block.input = {"location": "SF"}
        
        mock_response = MagicMock()
        mock_response.content = [mock_tool_block]
        mock_response.stop_reason = "tool_use"
        mock_response.usage = None
        
        mock_client = MagicMock()
        mock_client.messages = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_anthropic_class.return_value = mock_client
        
        provider = AnthropicProvider(anthropic_config)
        
        messages = [Message(role="user", content="What's the weather?")]
        tools = [
            ToolDefinition(
                name="get_weather",
                description="Get weather info",
                parameters={"type": "object", "properties": {"location": {"type": "string"}}}
            )
        ]
        
        response = await provider.generate(messages, tools=tools)
        
        assert response.has_tool_calls()
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].id == "call_123"
        assert response.tool_calls[0].name == "get_weather"
        assert response.tool_calls[0].arguments["location"] == "SF"
    
    @pytest.mark.asyncio
    @patch('mcp_bigquery.llm.providers.anthropic_provider.AsyncAnthropic')
    async def test_generate_api_error(self, mock_anthropic_class, anthropic_config):
        """Test handling of Anthropic API errors."""
        from anthropic import AnthropicError
        
        mock_client = MagicMock()
        mock_client.messages = MagicMock()
        mock_client.messages.create = AsyncMock(
            side_effect=AnthropicError("API error")
        )
        mock_anthropic_class.return_value = mock_client
        
        provider = AnthropicProvider(anthropic_config)
        messages = [Message(role="user", content="Test")]
        
        with pytest.raises(LLMGenerationError) as exc_info:
            await provider.generate(messages)
        
        assert "Anthropic generation failed" in str(exc_info.value)
    
    @pytest.mark.asyncio
    @patch('mcp_bigquery.llm.providers.anthropic_provider.AsyncAnthropic')
    async def test_generate_with_max_tokens(self, mock_anthropic_class, anthropic_config):
        """Test that max_tokens is always provided."""
        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = "Response"
        
        mock_response = MagicMock()
        mock_response.content = [mock_text_block]
        mock_response.stop_reason = "end_turn"
        mock_response.usage = None
        
        mock_client = MagicMock()
        mock_client.messages = MagicMock()
        mock_create = AsyncMock(return_value=mock_response)
        mock_client.messages.create = mock_create
        mock_anthropic_class.return_value = mock_client
        
        provider = AnthropicProvider(anthropic_config)
        messages = [Message(role="user", content="Test")]
        
        await provider.generate(messages)
        
        call_args = mock_create.call_args[1]
        assert "max_tokens" in call_args
        assert call_args["max_tokens"] == 4096


class TestAnthropicProviderTokenCounting:
    """Tests for Anthropic provider token counting."""
    
    @patch('mcp_bigquery.llm.providers.anthropic_provider.AsyncAnthropic')
    def test_count_tokens_with_sdk(self, mock_anthropic_class, anthropic_config):
        """Test token counting using SDK."""
        mock_client = MagicMock()
        mock_client.count_tokens.return_value = 5
        mock_anthropic_class.return_value = mock_client
        
        provider = AnthropicProvider(anthropic_config)
        count = provider.count_tokens("Hello world")
        
        assert count == 5
        mock_client.count_tokens.assert_called_once_with("Hello world")
    
    @patch('mcp_bigquery.llm.providers.anthropic_provider.AsyncAnthropic')
    def test_count_tokens_fallback(self, mock_anthropic_class, anthropic_config):
        """Test token counting fallback when SDK fails."""
        mock_client = MagicMock()
        mock_client.count_tokens.side_effect = Exception("SDK error")
        mock_anthropic_class.return_value = mock_client
        
        provider = AnthropicProvider(anthropic_config)
        count = provider.count_tokens("Hello world!")
        
        assert count > 0
        assert count == len("Hello world!") // 4
    
    @patch('mcp_bigquery.llm.providers.anthropic_provider.AsyncAnthropic')
    def test_count_messages_tokens(self, mock_anthropic_class, anthropic_config):
        """Test counting tokens in messages."""
        mock_client = MagicMock()
        mock_client.count_tokens.return_value = 5
        mock_anthropic_class.return_value = mock_client
        
        provider = AnthropicProvider(anthropic_config)
        messages = [
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi"),
        ]
        
        count = provider.count_messages_tokens(messages)
        
        assert count > 0


class TestAnthropicProviderCapabilities:
    """Tests for Anthropic provider capability checks."""
    
    @patch('mcp_bigquery.llm.providers.anthropic_provider.AsyncAnthropic')
    def test_supports_functions_claude3(self, mock_anthropic_class):
        """Test that Claude 3 models support tool use."""
        mock_anthropic_class.return_value = MagicMock()
        
        config = AnthropicProviderConfig(
            api_key="sk-ant-test",
            model="claude-3-5-sonnet-20241022"
        )
        provider = AnthropicProvider(config)
        assert provider.supports_functions()
    
    @patch('mcp_bigquery.llm.providers.anthropic_provider.AsyncAnthropic')
    def test_supports_vision_claude3(self, mock_anthropic_class):
        """Test that Claude 3 supports vision."""
        mock_anthropic_class.return_value = MagicMock()
        
        config = AnthropicProviderConfig(
            api_key="sk-ant-test",
            model="claude-3-opus-20240229"
        )
        provider = AnthropicProvider(config)
        assert provider.supports_vision()
    
    @patch('mcp_bigquery.llm.providers.anthropic_provider.AsyncAnthropic')
    def test_get_model_info(self, mock_anthropic_class):
        """Test getting model information."""
        mock_anthropic_class.return_value = MagicMock()
        
        config = AnthropicProviderConfig(
            api_key="sk-ant-test",
            model="claude-3-5-sonnet-20241022"
        )
        provider = AnthropicProvider(config)
        
        info = provider.get_model_info()
        
        assert info["provider"] == "anthropic"
        assert info["model"] == "claude-3-5-sonnet-20241022"
        assert info["supports_functions"] is True
        assert info["supports_vision"] is True
        assert "max_context_tokens" in info
        assert info["max_context_tokens"] > 0
