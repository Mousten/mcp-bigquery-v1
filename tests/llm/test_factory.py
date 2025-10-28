"""Tests for LLM provider factory."""

import os
import pytest
from unittest.mock import patch

from mcp_bigquery.llm.factory import (
    create_provider,
    create_provider_from_env,
)
from mcp_bigquery.llm.providers import (
    OpenAIProvider,
    AnthropicProvider,
    LLMConfigurationError,
)


class TestCreateProvider:
    """Tests for create_provider function."""
    
    @patch('mcp_bigquery.llm.providers.openai_provider.AsyncOpenAI')
    def test_create_openai_provider(self, mock_openai_class):
        """Test creating an OpenAI provider."""
        mock_openai_class.return_value = object()
        
        provider = create_provider("openai", api_key="sk-test")
        
        assert isinstance(provider, OpenAIProvider)
        assert provider.provider_name == "openai"
    
    @patch('mcp_bigquery.llm.providers.anthropic_provider.AsyncAnthropic')
    def test_create_anthropic_provider(self, mock_anthropic_class):
        """Test creating an Anthropic provider."""
        mock_anthropic_class.return_value = object()
        
        provider = create_provider("anthropic", api_key="sk-ant-test")
        
        assert isinstance(provider, AnthropicProvider)
        assert provider.provider_name == "anthropic"
    
    def test_create_provider_invalid_type(self):
        """Test creating provider with invalid type."""
        with pytest.raises(LLMConfigurationError) as exc_info:
            create_provider("invalid_provider", api_key="test")  # type: ignore
        
        assert "Unknown provider type" in str(exc_info.value)
        assert "invalid_provider" in str(exc_info.value)
    
    @patch('mcp_bigquery.llm.providers.openai_provider.AsyncOpenAI')
    def test_create_provider_case_insensitive(self, mock_openai_class):
        """Test that provider type is case-insensitive."""
        mock_openai_class.return_value = object()
        
        provider = create_provider("OPENAI", api_key="sk-test")
        assert isinstance(provider, OpenAIProvider)
        
        provider = create_provider("OpenAI", api_key="sk-test")
        assert isinstance(provider, OpenAIProvider)
    
    @patch('mcp_bigquery.llm.providers.openai_provider.AsyncOpenAI')
    def test_create_provider_with_options(self, mock_openai_class):
        """Test creating provider with custom options."""
        mock_openai_class.return_value = object()
        
        provider = create_provider(
            "openai",
            api_key="sk-test",
            model="gpt-3.5-turbo",
            temperature=0.5,
            max_tokens=1000,
            timeout=120.0,
        )
        
        assert provider.config.model == "gpt-3.5-turbo"
        assert provider.config.temperature == 0.5
        assert provider.config.max_tokens == 1000
        assert provider.config.timeout == 120.0
    
    @patch('mcp_bigquery.llm.providers.openai_provider.AsyncOpenAI')
    def test_create_openai_from_env_var(self, mock_openai_class):
        """Test creating OpenAI provider using env var for API key."""
        mock_openai_class.return_value = object()
        
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-env-key"}):
            provider = create_provider("openai")
            assert provider.config.api_key == "sk-env-key"
    
    @patch('mcp_bigquery.llm.providers.anthropic_provider.AsyncAnthropic')
    def test_create_anthropic_from_env_var(self, mock_anthropic_class):
        """Test creating Anthropic provider using env var for API key."""
        mock_anthropic_class.return_value = object()
        
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-env-key"}):
            provider = create_provider("anthropic")
            assert provider.config.api_key == "sk-ant-env-key"
    
    def test_create_openai_missing_api_key(self):
        """Test error when OpenAI API key is missing."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(LLMConfigurationError) as exc_info:
                create_provider("openai")
            
            assert "OpenAI API key not provided" in str(exc_info.value)
            assert "OPENAI_API_KEY" in str(exc_info.value)
    
    def test_create_anthropic_missing_api_key(self):
        """Test error when Anthropic API key is missing."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(LLMConfigurationError) as exc_info:
                create_provider("anthropic")
            
            assert "Anthropic API key not provided" in str(exc_info.value)
            assert "ANTHROPIC_API_KEY" in str(exc_info.value)


class TestCreateProviderFromEnv:
    """Tests for create_provider_from_env function."""
    
    @patch('mcp_bigquery.llm.providers.openai_provider.AsyncOpenAI')
    def test_create_from_env_default_openai(self, mock_openai_class):
        """Test creating provider from env with default (OpenAI)."""
        mock_openai_class.return_value = object()
        
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            provider = create_provider_from_env()
            assert isinstance(provider, OpenAIProvider)
    
    @patch('mcp_bigquery.llm.providers.anthropic_provider.AsyncAnthropic')
    def test_create_from_env_anthropic(self, mock_anthropic_class):
        """Test creating Anthropic provider from env."""
        mock_anthropic_class.return_value = object()
        
        with patch.dict(os.environ, {
            "LLM_PROVIDER": "anthropic",
            "ANTHROPIC_API_KEY": "sk-ant-test"
        }):
            provider = create_provider_from_env()
            assert isinstance(provider, AnthropicProvider)
    
    @patch('mcp_bigquery.llm.providers.openai_provider.AsyncOpenAI')
    def test_create_from_env_with_model(self, mock_openai_class):
        """Test creating provider from env with model override."""
        mock_openai_class.return_value = object()
        
        with patch.dict(os.environ, {
            "OPENAI_API_KEY": "sk-test",
            "LLM_MODEL": "gpt-3.5-turbo"
        }):
            provider = create_provider_from_env()
            assert provider.config.model == "gpt-3.5-turbo"
    
    @patch('mcp_bigquery.llm.providers.openai_provider.AsyncOpenAI')
    def test_create_from_env_with_temperature(self, mock_openai_class):
        """Test creating provider from env with temperature override."""
        mock_openai_class.return_value = object()
        
        with patch.dict(os.environ, {
            "OPENAI_API_KEY": "sk-test",
            "LLM_TEMPERATURE": "0.3"
        }):
            provider = create_provider_from_env()
            assert provider.config.temperature == 0.3
    
    @patch('mcp_bigquery.llm.providers.openai_provider.AsyncOpenAI')
    def test_create_from_env_with_max_tokens(self, mock_openai_class):
        """Test creating provider from env with max_tokens override."""
        mock_openai_class.return_value = object()
        
        with patch.dict(os.environ, {
            "OPENAI_API_KEY": "sk-test",
            "LLM_MAX_TOKENS": "2000"
        }):
            provider = create_provider_from_env()
            assert provider.config.max_tokens == 2000
    
    @patch('mcp_bigquery.llm.providers.openai_provider.AsyncOpenAI')
    def test_create_from_env_custom_provider_var(self, mock_openai_class):
        """Test using custom environment variable name."""
        mock_openai_class.return_value = object()
        
        with patch.dict(os.environ, {
            "CUSTOM_PROVIDER": "openai",
            "OPENAI_API_KEY": "sk-test"
        }):
            provider = create_provider_from_env(provider_env_var="CUSTOM_PROVIDER")
            assert isinstance(provider, OpenAIProvider)
    
    @patch('mcp_bigquery.llm.providers.anthropic_provider.AsyncAnthropic')
    def test_create_from_env_custom_default(self, mock_anthropic_class):
        """Test using custom default provider."""
        mock_anthropic_class.return_value = object()
        
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"}):
            provider = create_provider_from_env(default_provider="anthropic")
            assert isinstance(provider, AnthropicProvider)
    
    def test_create_from_env_invalid_provider(self):
        """Test error when env var contains invalid provider type."""
        with patch.dict(os.environ, {"LLM_PROVIDER": "invalid"}):
            with pytest.raises(LLMConfigurationError) as exc_info:
                create_provider_from_env()
            
            assert "Invalid provider type" in str(exc_info.value)


class TestProviderInterfaceConsistency:
    """Tests to ensure both providers adhere to the interface."""
    
    @patch('mcp_bigquery.llm.providers.openai_provider.AsyncOpenAI')
    def test_openai_has_required_methods(self, mock_openai_class):
        """Test that OpenAI provider has all required methods."""
        mock_openai_class.return_value = object()
        provider = create_provider("openai", api_key="sk-test")
        
        assert hasattr(provider, "generate")
        assert hasattr(provider, "count_tokens")
        assert hasattr(provider, "count_messages_tokens")
        assert hasattr(provider, "supports_functions")
        assert hasattr(provider, "supports_vision")
        assert hasattr(provider, "get_model_info")
        assert hasattr(provider, "provider_name")
    
    @patch('mcp_bigquery.llm.providers.anthropic_provider.AsyncAnthropic')
    def test_anthropic_has_required_methods(self, mock_anthropic_class):
        """Test that Anthropic provider has all required methods."""
        mock_anthropic_class.return_value = object()
        provider = create_provider("anthropic", api_key="sk-ant-test")
        
        assert hasattr(provider, "generate")
        assert hasattr(provider, "count_tokens")
        assert hasattr(provider, "count_messages_tokens")
        assert hasattr(provider, "supports_functions")
        assert hasattr(provider, "supports_vision")
        assert hasattr(provider, "get_model_info")
        assert hasattr(provider, "provider_name")
    
    @patch('mcp_bigquery.llm.providers.openai_provider.AsyncOpenAI')
    @patch('mcp_bigquery.llm.providers.anthropic_provider.AsyncAnthropic')
    def test_providers_return_consistent_types(self, mock_anthropic_class, mock_openai_class):
        """Test that both providers return consistent types."""
        mock_openai_class.return_value = object()
        mock_anthropic_class.return_value = object()
        
        openai_provider = create_provider("openai", api_key="sk-test")
        anthropic_provider = create_provider("anthropic", api_key="sk-ant-test")
        
        assert isinstance(openai_provider.supports_functions(), bool)
        assert isinstance(anthropic_provider.supports_functions(), bool)
        
        assert isinstance(openai_provider.supports_vision(), bool)
        assert isinstance(anthropic_provider.supports_vision(), bool)
        
        assert isinstance(openai_provider.get_model_info(), dict)
        assert isinstance(anthropic_provider.get_model_info(), dict)
        
        assert isinstance(openai_provider.provider_name, str)
        assert isinstance(anthropic_provider.provider_name, str)
