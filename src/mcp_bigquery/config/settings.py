"""Configuration settings for the MCP BigQuery server."""
import os
import json
from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class ServerConfig(BaseSettings):
    """Configuration class to store server configurations.
    
    Environment Variables:
        PROJECT_ID: Google Cloud project ID (required)
        LOCATION: BigQuery location (default: US)
        KEY_FILE: Path to service account key file
        SUPABASE_URL: Supabase project URL
        SUPABASE_KEY: Supabase anonymous key
        SUPABASE_SERVICE_KEY: Supabase service role key (for RLS bypass)
        SUPABASE_JWT_SECRET: JWT secret for validating Supabase tokens
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    project_id: str = Field(..., description="Google Cloud project ID")
    location: str = Field(default="US", description="BigQuery location")
    key_file: Optional[str] = Field(default=None, description="Path to service account key file")
    supabase_url: Optional[str] = Field(default=None, description="Supabase project URL")
    supabase_key: Optional[str] = Field(default=None, description="Supabase anonymous key")
    supabase_service_key: Optional[str] = Field(default=None, description="Supabase service role key")
    supabase_jwt_secret: Optional[str] = Field(default=None, description="JWT secret for token validation")

    @field_validator('project_id')
    @classmethod
    def validate_project_id(cls, v: str) -> str:
        """Validate project_id is not empty."""
        if not v or not v.strip():
            raise ValueError("Project ID is required and cannot be empty")
        return v.strip()

    @field_validator('key_file')
    @classmethod
    def validate_key_file(cls, v: Optional[str]) -> Optional[str]:
        """Validate key file exists and is accessible."""
        if v and not os.path.isfile(v):
            raise ValueError(f"Key file '{v}' not found or inaccessible")
        return v

    @model_validator(mode='after')
    def validate_key_file_format(self) -> 'ServerConfig':
        """Validate service account key file format if provided."""
        if self.key_file:
            try:
                with open(self.key_file, "r") as f:
                    key_data = json.load(f)
                if (
                    key_data.get("type") != "service_account"
                    or "project_id" not in key_data
                ):
                    raise ValueError("Invalid service account key file format")
            except json.JSONDecodeError:
                raise ValueError("Service account key file is not valid JSON")
        return self

    def validate(self) -> None:
        """Legacy validate method for backward compatibility."""
        # Validation is now done automatically by Pydantic
        pass

    @classmethod
    def from_env(cls) -> "ServerConfig":
        """Create configuration from environment variables."""
        return cls()