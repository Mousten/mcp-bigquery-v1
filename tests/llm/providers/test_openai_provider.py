"""Tests for OpenAI provider implementation."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import ValidationError

from mcp_bigquery.llm.providers import (
    OpenAIProvider,
    OpenAIProviderConfig,
    LLMConfigurationError,
    LLMGenerationError,
    Message,
    ToolDefinition,
)


@pytest.fixture
def openai_config():
    """Create a valid OpenAI config for testing."""
    return OpenAIProviderConfig(
        api_key="sk-test-key-123",
        model="gpt-4o",
        temperature=0.7,
    )


@pytest.fixture
def mock_openai_client():
    """Create a mock OpenAI client."""
    client = MagicMock()
    client.chat = MagicMock()
    client.chat.completions = MagicMock()
    return client


class TestOpenAIProviderConfig:
    """Tests for OpenAI provider configuration."""
    
    def test_config_with_defaults(self):
        """Test config with default values."""
        config = OpenAIProviderConfig(api_key="sk-test")
        assert config.model == "gpt-4o"
        assert config.temperature == 0.7
        assert config.base_url is None
        assert config.organization is None
    
    def test_config_with_custom_values(self):
        """Test config with custom values."""
        config = OpenAIProviderConfig(
            api_key="sk-test",
            model="gpt-3.5-turbo",
            temperature=0.5,
            base_url="https://custom.openai.com",
            organization="org-123",
        )
        assert config.model == "gpt-3.5-turbo"
        assert config.base_url == "https://custom.openai.com"
        assert config.organization == "org-123"


class TestOpenAIProviderInitialization:
    """Tests for OpenAI provider initialization."""
    
    @patch('mcp_bigquery.llm.providers.openai_provider.AsyncOpenAI')
    def test_provider_initialization(self, mock_openai_class, openai_config):
        """Test successful provider initialization."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        provider = OpenAIProvider(openai_config)
        
        assert provider.config == openai_config
        assert provider.provider_name == "openai"
        mock_openai_class.assert_called_once()
    
    @patch('mcp_bigquery.llm.providers.openai_provider.AsyncOpenAI')
    def test_provider_initialization_failure(self, mock_openai_class):
        """Test provider initialization failure."""
        mock_openai_class.side_effect = Exception("Connection failed")
        
        config = OpenAIProviderConfig(api_key="sk-test")
        with pytest.raises(LLMConfigurationError) as exc_info:
            OpenAIProvider(config)
        
        assert "Failed to initialize OpenAI client" in str(exc_info.value)


class TestOpenAIProviderGeneration:
    """Tests for OpenAI provider generation."""
    
    @pytest.mark.asyncio
    @patch('mcp_bigquery.llm.providers.openai_provider.AsyncOpenAI')
    async def test_generate_simple_message(self, mock_openai_class, openai_config):
        """Test generating a simple text response."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock()
        mock_response.choices[0].message.content = "Hello, how can I help you?"
        mock_response.choices[0].message.tool_calls = None
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 7
        mock_response.usage.total_tokens = 17
        
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_openai_class.return_value = mock_client
        
        provider = OpenAIProvider(openai_config)
        
        messages = [Message(role="user", content="Hi there")]
        response = await provider.generate(messages)
        
        assert response.content == "Hello, how can I help you?"
        assert response.finish_reason == "stop"
        assert response.usage["prompt_tokens"] == 10
        assert response.usage["completion_tokens"] == 7
        assert response.usage["total_tokens"] == 17
        assert not response.has_tool_calls()
    
    @pytest.mark.asyncio
    @patch('mcp_bigquery.llm.providers.openai_provider.AsyncOpenAI')
    async def test_generate_with_tool_calls(self, mock_openai_class, openai_config):
        """Test generating a response with tool calls."""
        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_123"
        mock_tool_call.function = MagicMock()
        mock_tool_call.function.name = "get_weather"
        mock_tool_call.function.arguments = '{"location": "SF"}'
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock()
        mock_response.choices[0].message.content = None
        mock_response.choices[0].message.tool_calls = [mock_tool_call]
        mock_response.choices[0].finish_reason = "tool_calls"
        mock_response.usage = None
        
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_openai_class.return_value = mock_client
        
        provider = OpenAIProvider(openai_config)
        
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
    @patch('mcp_bigquery.llm.providers.openai_provider.AsyncOpenAI')
    async def test_generate_api_error(self, mock_openai_class, openai_config):
        """Test handling of OpenAI API errors."""
        from openai import OpenAIError
        
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=OpenAIError("API error")
        )
        mock_openai_class.return_value = mock_client
        
        provider = OpenAIProvider(openai_config)
        messages = [Message(role="user", content="Test")]
        
        with pytest.raises(LLMGenerationError) as exc_info:
            await provider.generate(messages)
        
        assert "OpenAI generation failed" in str(exc_info.value)
    
    @pytest.mark.asyncio
    @patch('mcp_bigquery.llm.providers.openai_provider.AsyncOpenAI')
    async def test_generate_with_temperature_override(self, mock_openai_class, openai_config):
        """Test generating with temperature override."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock()
        mock_response.choices[0].message.content = "Response"
        mock_response.choices[0].message.tool_calls = None
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = None
        
        mock_client = MagicMock()
        mock_create = AsyncMock(return_value=mock_response)
        mock_client.chat.completions.create = mock_create
        mock_openai_class.return_value = mock_client
        
        provider = OpenAIProvider(openai_config)
        messages = [Message(role="user", content="Test")]
        
        await provider.generate(messages, temperature=0.2)
        
        call_args = mock_create.call_args[1]
        assert call_args["temperature"] == 0.2


class TestOpenAIProviderTokenCounting:
    """Tests for OpenAI provider token counting."""
    
    @patch('mcp_bigquery.llm.providers.openai_provider.AsyncOpenAI')
    @patch('mcp_bigquery.llm.providers.openai_provider.tiktoken')
    def test_count_tokens(self, mock_tiktoken, mock_openai_class, openai_config):
        """Test token counting."""
        mock_encoding = MagicMock()
        mock_encoding.encode.return_value = [1, 2, 3, 4, 5]
        mock_tiktoken.encoding_for_model.return_value = mock_encoding
        
        mock_openai_class.return_value = MagicMock()
        
        provider = OpenAIProvider(openai_config)
        count = provider.count_tokens("Hello world")
        
        assert count == 5
        mock_tiktoken.encoding_for_model.assert_called_once_with("gpt-4o")
        mock_encoding.encode.assert_called_once_with("Hello world")
    
    @patch('mcp_bigquery.llm.providers.openai_provider.AsyncOpenAI')
    @patch('mcp_bigquery.llm.providers.openai_provider.tiktoken')
    def test_count_messages_tokens(self, mock_tiktoken, mock_openai_class, openai_config):
        """Test counting tokens in messages."""
        mock_encoding = MagicMock()
        mock_encoding.encode.side_effect = lambda text: [1] * len(text)
        mock_tiktoken.encoding_for_model.return_value = mock_encoding
        
        mock_openai_class.return_value = MagicMock()
        
        provider = OpenAIProvider(openai_config)
        messages = [
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi"),
        ]
        
        count = provider.count_messages_tokens(messages)
        
        assert count > 0
        assert mock_encoding.encode.call_count > 0


class TestOpenAIProviderCapabilities:
    """Tests for OpenAI provider capability checks."""
    
    @patch('mcp_bigquery.llm.providers.openai_provider.AsyncOpenAI')
    def test_supports_functions_gpt4(self, mock_openai_class):
        """Test that GPT-4 models support functions."""
        mock_openai_class.return_value = MagicMock()
        
        config = OpenAIProviderConfig(api_key="sk-test", model="gpt-4o")
        provider = OpenAIProvider(config)
        assert provider.supports_functions()
    
    @patch('mcp_bigquery.llm.providers.openai_provider.AsyncOpenAI')
    def test_supports_functions_gpt35(self, mock_openai_class):
        """Test that GPT-3.5 models support functions."""
        mock_openai_class.return_value = MagicMock()
        
        config = OpenAIProviderConfig(api_key="sk-test", model="gpt-3.5-turbo")
        provider = OpenAIProvider(config)
        assert provider.supports_functions()
    
    @patch('mcp_bigquery.llm.providers.openai_provider.AsyncOpenAI')
    def test_supports_vision_gpt4o(self, mock_openai_class):
        """Test that GPT-4o supports vision."""
        mock_openai_class.return_value = MagicMock()
        
        config = OpenAIProviderConfig(api_key="sk-test", model="gpt-4o")
        provider = OpenAIProvider(config)
        assert provider.supports_vision()
    
    @patch('mcp_bigquery.llm.providers.openai_provider.AsyncOpenAI')
    def test_get_model_info(self, mock_openai_class):
        """Test getting model information."""
        mock_openai_class.return_value = MagicMock()
        
        config = OpenAIProviderConfig(api_key="sk-test", model="gpt-4o")
        provider = OpenAIProvider(config)
        
        info = provider.get_model_info()
        
        assert info["provider"] == "openai"
        assert info["model"] == "gpt-4o"
        assert info["supports_functions"] is True
        assert info["supports_vision"] is True
        assert "max_context_tokens" in info
        assert info["max_context_tokens"] > 0
