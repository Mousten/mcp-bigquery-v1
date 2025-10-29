"""Tests for client configuration."""

import os
import pytest
from pydantic import ValidationError

from mcp_bigquery.client.config import ClientConfig


class TestClientConfig:
    """Tests for ClientConfig."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = ClientConfig()
        assert config.base_url == "http://localhost:8000"
        assert config.auth_token is None
        assert config.timeout == 30.0
        assert config.max_retries == 3
        assert config.retry_delay == 1.0
        assert config.verify_ssl is True
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = ClientConfig(
            base_url="https://api.example.com",
            auth_token="test-token",
            timeout=60.0,
            max_retries=5,
            retry_delay=2.0,
            verify_ssl=False
        )
        assert config.base_url == "https://api.example.com"
        assert config.auth_token == "test-token"
        assert config.timeout == 60.0
        assert config.max_retries == 5
        assert config.retry_delay == 2.0
        assert config.verify_ssl is False
    
    def test_base_url_normalization(self):
        """Test base URL normalization removes trailing slashes."""
        config = ClientConfig(base_url="http://localhost:8000/")
        assert config.base_url == "http://localhost:8000"
        
        config = ClientConfig(base_url="http://localhost:8000///")
        assert config.base_url == "http://localhost:8000"
    
    def test_base_url_validation_empty(self):
        """Test base URL validation rejects empty strings."""
        with pytest.raises(ValidationError) as exc_info:
            ClientConfig(base_url="")
        assert "base_url cannot be empty" in str(exc_info.value)
    
    def test_base_url_validation_protocol(self):
        """Test base URL validation requires http:// or https://."""
        with pytest.raises(ValidationError) as exc_info:
            ClientConfig(base_url="localhost:8000")
        assert "must start with http:// or https://" in str(exc_info.value)
    
    def test_timeout_validation(self):
        """Test timeout validation requires positive value."""
        with pytest.raises(ValidationError) as exc_info:
            ClientConfig(timeout=0)
        assert "timeout must be positive" in str(exc_info.value)
        
        with pytest.raises(ValidationError) as exc_info:
            ClientConfig(timeout=-1)
        assert "timeout must be positive" in str(exc_info.value)
    
    def test_max_retries_validation(self):
        """Test max_retries validation requires non-negative value."""
        config = ClientConfig(max_retries=0)
        assert config.max_retries == 0
        
        with pytest.raises(ValidationError) as exc_info:
            ClientConfig(max_retries=-1)
        assert "max_retries must be non-negative" in str(exc_info.value)
    
    def test_from_env_defaults(self, monkeypatch):
        """Test loading configuration from environment with defaults."""
        # Clear relevant env vars
        for key in ['MCP_BASE_URL', 'MCP_AUTH_TOKEN', 'MCP_TIMEOUT', 
                    'MCP_MAX_RETRIES', 'MCP_RETRY_DELAY', 'MCP_VERIFY_SSL']:
            monkeypatch.delenv(key, raising=False)
        
        config = ClientConfig.from_env()
        assert config.base_url == "http://localhost:8000"
        assert config.auth_token is None
        assert config.timeout == 30.0
        assert config.max_retries == 3
        assert config.retry_delay == 1.0
        assert config.verify_ssl is True
    
    def test_from_env_custom(self, monkeypatch):
        """Test loading configuration from environment with custom values."""
        monkeypatch.setenv('MCP_BASE_URL', 'https://api.example.com')
        monkeypatch.setenv('MCP_AUTH_TOKEN', 'test-token')
        monkeypatch.setenv('MCP_TIMEOUT', '60.0')
        monkeypatch.setenv('MCP_MAX_RETRIES', '5')
        monkeypatch.setenv('MCP_RETRY_DELAY', '2.0')
        monkeypatch.setenv('MCP_VERIFY_SSL', 'false')
        
        config = ClientConfig.from_env()
        assert config.base_url == "https://api.example.com"
        assert config.auth_token == "test-token"
        assert config.timeout == 60.0
        assert config.max_retries == 5
        assert config.retry_delay == 2.0
        assert config.verify_ssl is False
    
    def test_from_env_verify_ssl_variants(self, monkeypatch):
        """Test verify_ssl accepts various truthy/falsy values."""
        for value in ['true', 'True', 'TRUE', '1', 'yes']:
            monkeypatch.setenv('MCP_VERIFY_SSL', value)
            config = ClientConfig.from_env()
            assert config.verify_ssl is True, f"Failed for value: {value}"
        
        for value in ['false', 'False', 'FALSE', '0', 'no', 'anything']:
            monkeypatch.setenv('MCP_VERIFY_SSL', value)
            config = ClientConfig.from_env()
            assert config.verify_ssl is False, f"Failed for value: {value}"
    
    def test_from_env_with_overrides(self, monkeypatch):
        """Test from_env with override parameters."""
        monkeypatch.setenv('MCP_BASE_URL', 'http://env.example.com')
        monkeypatch.setenv('MCP_TIMEOUT', '60.0')
        
        config = ClientConfig.from_env(
            base_url='http://override.example.com',
            auth_token='override-token'
        )
        
        # Overrides take precedence
        assert config.base_url == "http://override.example.com"
        assert config.auth_token == "override-token"
        # Non-overridden values come from env
        assert config.timeout == 60.0
