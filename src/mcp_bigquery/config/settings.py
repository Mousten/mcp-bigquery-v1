"""Configuration settings for the MCP BigQuery server."""
import os
import json
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class ServerConfig:
    """Configuration class to store server configurations."""

    def __init__(
        self,
        project_id: str,
        location: str = "US",
        key_file: Optional[str] = None,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
    ):
        self.project_id = project_id
        self.location = location
        self.key_file = key_file
        self.supabase_url = supabase_url
        self.supabase_key = supabase_key

    def validate(self) -> None:
        """Validate the configuration settings."""
        if not self.project_id:
            raise ValueError("Project ID is required.")
        
        if self.key_file and not os.path.isfile(self.key_file):
            raise ValueError(f"Key file '{self.key_file}' not found or inaccessible.")
        
        if self.key_file:
            try:
                with open(self.key_file, "r") as f:
                    key_data = json.load(f)
                if (
                    key_data.get("type") != "service_account"
                    or "project_id" not in key_data
                ):
                    raise ValueError("Invalid service account key file format.")
            except json.JSONDecodeError:
                raise ValueError("Service account key file is not valid JSON.")

    @classmethod
    def from_env(cls) -> "ServerConfig":
        """Create configuration from environment variables."""
        project_id = os.getenv("PROJECT_ID")
        if project_id is None:
            raise ValueError("PROJECT_ID environment variable is required")
        return cls(
            project_id=project_id,
            location=os.getenv("LOCATION", "US"),
            key_file=os.getenv("KEY_FILE"),
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_key=os.getenv("SUPABASE_KEY"),
        )