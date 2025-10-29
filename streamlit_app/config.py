"""Configuration for the Streamlit app."""
import os
from typing import Optional
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class StreamlitConfig(BaseSettings):
    """Configuration for Streamlit app with environment-driven settings.
    
    Environment Variables:
        MCP_BASE_URL: Base URL of the MCP server (default: http://localhost:8000)
        SUPABASE_URL: Supabase project URL (required)
        SUPABASE_KEY: Supabase anonymous key (required)
        SUPABASE_JWT_SECRET: JWT secret for token validation (required)
        PROJECT_ID: Google Cloud project ID (required)
        LLM_PROVIDER: LLM provider type (openai, anthropic, gemini) (default: openai)
        LLM_MODEL: LLM model name (optional, uses provider default)
        OPENAI_API_KEY: OpenAI API key (if using OpenAI)
        ANTHROPIC_API_KEY: Anthropic API key (if using Anthropic)
        GOOGLE_API_KEY: Google API key (if using Gemini)
        ENABLE_RATE_LIMITING: Enable rate limiting (default: true)
        ENABLE_CACHING: Enable response caching (default: true)
        MAX_CONTEXT_TURNS: Maximum conversation turns to include in context (default: 5)
        APP_TITLE: Application title (default: BigQuery Insights)
        APP_ICON: Application icon emoji (default: 📊)
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # MCP Server Configuration
    mcp_base_url: str = Field(
        default="http://localhost:8000",
        description="Base URL of the MCP server"
    )
    
    # Supabase Configuration
    supabase_url: str = Field(..., description="Supabase project URL")
    supabase_key: str = Field(..., description="Supabase anonymous key")
    supabase_jwt_secret: str = Field(..., description="JWT secret for token validation")
    
    # BigQuery Configuration
    project_id: str = Field(..., description="Google Cloud project ID")
    
    # LLM Configuration
    llm_provider: str = Field(default="openai", description="LLM provider type")
    llm_model: Optional[str] = Field(default=None, description="LLM model name")
    
    # API Keys
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")
    anthropic_api_key: Optional[str] = Field(default=None, description="Anthropic API key")
    google_api_key: Optional[str] = Field(default=None, description="Google API key")
    
    # Feature Flags
    enable_rate_limiting: bool = Field(default=True, description="Enable rate limiting")
    enable_caching: bool = Field(default=True, description="Enable response caching")
    
    # Conversation Settings
    max_context_turns: int = Field(default=5, ge=1, le=20, description="Max context turns")
    
    # UI Settings
    app_title: str = Field(default="BigQuery Insights", description="Application title")
    app_icon: str = Field(default="📊", description="Application icon")
    
    @classmethod
    def from_env(cls) -> "StreamlitConfig":
        """Create configuration from environment variables."""
        return cls()
    
    def validate_llm_config(self) -> None:
        """Validate LLM configuration has required API keys."""
        provider = self.llm_provider.lower()
        if provider == "openai" and not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when using OpenAI provider")
        elif provider == "anthropic" and not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required when using Anthropic provider")
        elif provider == "gemini" and not self.google_api_key:
            raise ValueError("GOOGLE_API_KEY is required when using Gemini provider")
