"""Configuration for the MCP BigQuery client."""

import os
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class ClientConfig(BaseModel):
    """Configuration for MCP BigQuery client.
    
    Attributes:
        base_url: Base URL of the MCP server (e.g., "http://localhost:8000")
        auth_token: JWT token for authentication
        timeout: Request timeout in seconds
        max_retries: Maximum number of retries for failed requests
        retry_delay: Initial delay between retries in seconds (uses exponential backoff)
        verify_ssl: Whether to verify SSL certificates
    """
    
    base_url: str = Field(default="http://localhost:8000")
    auth_token: Optional[str] = None
    timeout: float = Field(default=30.0)
    max_retries: int = Field(default=3)
    retry_delay: float = Field(default=1.0)
    verify_ssl: bool = Field(default=True)
    
    @field_validator('base_url')
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        """Validate and normalize base URL."""
        if not v:
            raise ValueError("base_url cannot be empty")
        
        # Remove trailing slash
        v = v.rstrip('/')
        
        # Ensure it starts with http:// or https://
        if not v.startswith(('http://', 'https://')):
            raise ValueError("base_url must start with http:// or https://")
        
        return v
    
    @field_validator('timeout')
    @classmethod
    def validate_timeout(cls, v: float) -> float:
        """Validate timeout is positive."""
        if v <= 0:
            raise ValueError("timeout must be positive")
        return v
    
    @field_validator('max_retries')
    @classmethod
    def validate_max_retries(cls, v: int) -> int:
        """Validate max_retries is non-negative."""
        if v < 0:
            raise ValueError("max_retries must be non-negative")
        return v
    
    @classmethod
    def from_env(cls, **overrides) -> "ClientConfig":
        """Create configuration from environment variables.
        
        Environment variables:
            MCP_BASE_URL: Base URL of the MCP server
            MCP_AUTH_TOKEN: JWT token for authentication
            MCP_TIMEOUT: Request timeout in seconds
            MCP_MAX_RETRIES: Maximum number of retries
            MCP_RETRY_DELAY: Initial retry delay in seconds
            MCP_VERIFY_SSL: Whether to verify SSL certificates
        
        Args:
            **overrides: Optional overrides for config values
            
        Returns:
            ClientConfig instance
        """
        config_dict = {
            'base_url': os.getenv('MCP_BASE_URL', 'http://localhost:8000'),
            'auth_token': os.getenv('MCP_AUTH_TOKEN'),
            'timeout': float(os.getenv('MCP_TIMEOUT', '30.0')),
            'max_retries': int(os.getenv('MCP_MAX_RETRIES', '3')),
            'retry_delay': float(os.getenv('MCP_RETRY_DELAY', '1.0')),
            'verify_ssl': os.getenv('MCP_VERIFY_SSL', 'true').lower() in ('true', '1', 'yes'),
        }
        
        # Apply overrides
        config_dict.update(overrides)
        
        return cls(**config_dict)
