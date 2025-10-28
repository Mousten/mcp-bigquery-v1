"""Tests for base LLM provider interface and models."""

import pytest
from pydantic import ValidationError

from mcp_bigquery.llm.providers import (
    Message,
    ToolCall,
    ToolDefinition,
    GenerationResponse,
    LLMProviderConfig,
    LLMProviderError,
    LLMConfigurationError,
    LLMGenerationError,
)


class TestMessage:
    """Tests for Message model."""
    
    def test_message_creation(self):
        """Test creating a valid message."""
        msg = Message(role="user", content="Hello!")
        assert msg.role == "user"
        assert msg.content == "Hello!"
        assert msg.name is None
    
    def test_message_with_name(self):
        """Test creating a message with name field."""
        msg = Message(role="assistant", content="Hi there!", name="bot")
        assert msg.name == "bot"
    
    def test_invalid_role(self):
        """Test that invalid role raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            Message(role="invalid_role", content="test")
        assert "Role must be one of" in str(exc_info.value)
    
    def test_valid_roles(self):
        """Test all valid roles."""
        valid_roles = ["system", "user", "assistant", "function", "tool"]
        for role in valid_roles:
            msg = Message(role=role, content="test")
            assert msg.role == role


class TestToolCall:
    """Tests for ToolCall model."""
    
    def test_tool_call_creation(self):
        """Test creating a tool call."""
        tool_call = ToolCall(
            id="call_123",
            name="get_weather",
            arguments={"location": "San Francisco"}
        )
        assert tool_call.id == "call_123"
        assert tool_call.name == "get_weather"
        assert tool_call.arguments["location"] == "San Francisco"
    
    def test_tool_call_empty_arguments(self):
        """Test tool call with no arguments."""
        tool_call = ToolCall(id="call_456", name="list_users")
        assert tool_call.arguments == {}


class TestToolDefinition:
    """Tests for ToolDefinition model."""
    
    def test_tool_definition_creation(self):
        """Test creating a tool definition."""
        tool = ToolDefinition(
            name="search",
            description="Search for information",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                },
                "required": ["query"]
            }
        )
        assert tool.name == "search"
        assert tool.description == "Search for information"
        assert tool.parameters["type"] == "object"
    
    def test_tool_definition_no_parameters(self):
        """Test tool definition without parameters."""
        tool = ToolDefinition(
            name="reset",
            description="Reset the system"
        )
        assert tool.parameters == {}
    
    def test_invalid_parameters_type(self):
        """Test that non-dict parameters raises ValidationError."""
        with pytest.raises(ValidationError):
            ToolDefinition(
                name="test",
                description="test",
                parameters="not a dict"  # type: ignore
            )


class TestGenerationResponse:
    """Tests for GenerationResponse model."""
    
    def test_response_with_content(self):
        """Test response with text content."""
        response = GenerationResponse(
            content="Hello, how can I help?",
            finish_reason="stop",
            usage={"prompt_tokens": 10, "completion_tokens": 5}
        )
        assert response.content == "Hello, how can I help?"
        assert response.finish_reason == "stop"
        assert response.usage["prompt_tokens"] == 10
        assert not response.has_tool_calls()
    
    def test_response_with_tool_calls(self):
        """Test response with tool calls."""
        tool_call = ToolCall(
            id="call_789",
            name="calculator",
            arguments={"expression": "2+2"}
        )
        response = GenerationResponse(
            tool_calls=[tool_call],
            finish_reason="tool_calls"
        )
        assert response.has_tool_calls()
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].name == "calculator"
    
    def test_response_defaults(self):
        """Test response with default values."""
        response = GenerationResponse()
        assert response.content is None
        assert response.tool_calls == []
        assert response.usage == {}
        assert response.finish_reason is None
        assert not response.has_tool_calls()


class TestLLMProviderConfig:
    """Tests for LLMProviderConfig model."""
    
    def test_config_creation(self):
        """Test creating a valid config."""
        config = LLMProviderConfig(
            api_key="test-key-123",
            model="gpt-4o"
        )
        assert config.api_key == "test-key-123"
        assert config.model == "gpt-4o"
        assert config.temperature == 0.7
        assert config.timeout == 60.0
    
    def test_config_with_custom_values(self):
        """Test config with custom values."""
        config = LLMProviderConfig(
            api_key="sk-test",
            model="claude-3-opus",
            temperature=0.5,
            max_tokens=1000,
            timeout=30.0
        )
        assert config.temperature == 0.5
        assert config.max_tokens == 1000
        assert config.timeout == 30.0
    
    def test_config_empty_api_key(self):
        """Test that empty API key raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            LLMProviderConfig(api_key="", model="test")
        assert "API key cannot be empty" in str(exc_info.value)
    
    def test_config_whitespace_api_key(self):
        """Test that whitespace-only API key raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            LLMProviderConfig(api_key="   ", model="test")
        assert "API key cannot be empty" in str(exc_info.value)
    
    def test_config_strips_api_key(self):
        """Test that API key is stripped of whitespace."""
        config = LLMProviderConfig(api_key="  sk-test  ", model="test")
        assert config.api_key == "sk-test"
    
    def test_config_temperature_validation(self):
        """Test temperature validation."""
        with pytest.raises(ValidationError):
            LLMProviderConfig(api_key="test", model="test", temperature=-0.1)
        
        with pytest.raises(ValidationError):
            LLMProviderConfig(api_key="test", model="test", temperature=2.1)
        
        config = LLMProviderConfig(api_key="test", model="test", temperature=0.0)
        assert config.temperature == 0.0
        
        config = LLMProviderConfig(api_key="test", model="test", temperature=2.0)
        assert config.temperature == 2.0
    
    def test_config_max_tokens_validation(self):
        """Test max_tokens validation."""
        with pytest.raises(ValidationError):
            LLMProviderConfig(api_key="test", model="test", max_tokens=0)
        
        with pytest.raises(ValidationError):
            LLMProviderConfig(api_key="test", model="test", max_tokens=-1)
        
        config = LLMProviderConfig(api_key="test", model="test", max_tokens=100)
        assert config.max_tokens == 100
    
    def test_config_timeout_validation(self):
        """Test timeout validation."""
        with pytest.raises(ValidationError):
            LLMProviderConfig(api_key="test", model="test", timeout=0.0)
        
        with pytest.raises(ValidationError):
            LLMProviderConfig(api_key="test", model="test", timeout=-1.0)
        
        config = LLMProviderConfig(api_key="test", model="test", timeout=120.0)
        assert config.timeout == 120.0


class TestExceptions:
    """Tests for exception hierarchy."""
    
    def test_exception_hierarchy(self):
        """Test that exceptions have correct inheritance."""
        assert issubclass(LLMProviderError, Exception)
        assert issubclass(LLMConfigurationError, LLMProviderError)
        assert issubclass(LLMGenerationError, LLMProviderError)
    
    def test_exception_messages(self):
        """Test that exceptions can be raised with messages."""
        try:
            raise LLMProviderError("Test error")
        except LLMProviderError as e:
            assert str(e) == "Test error"
        
        try:
            raise LLMConfigurationError("Config error")
        except LLMConfigurationError as e:
            assert str(e) == "Config error"
        
        try:
            raise LLMGenerationError("Generation error")
        except LLMGenerationError as e:
            assert str(e) == "Generation error"
