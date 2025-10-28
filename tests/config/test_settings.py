"""Tests for ServerConfig Pydantic model."""

import pytest
import os
import tempfile
import json
from unittest.mock import patch
from pydantic import ValidationError

from mcp_bigquery.config.settings import ServerConfig


class TestServerConfigValidation:
    """Tests for ServerConfig validation."""
    
    def test_valid_config(self):
        """Test creating a valid server config."""
        config = ServerConfig(project_id="my-project")
        assert config.project_id == "my-project"
        assert config.location == "US"
    
    def test_custom_location(self):
        """Test config with custom location."""
        config = ServerConfig(project_id="my-project", location="EU")
        assert config.location == "EU"
    
    def test_empty_project_id_fails(self):
        """Test that empty project_id fails validation."""
        with pytest.raises(ValidationError):
            ServerConfig(project_id="")
    
    def test_whitespace_project_id_fails(self):
        """Test that whitespace-only project_id fails validation."""
        with pytest.raises(ValidationError):
            ServerConfig(project_id="   ")
    
    def test_project_id_trimmed(self):
        """Test that project_id is trimmed."""
        config = ServerConfig(project_id="  my-project  ")
        assert config.project_id == "my-project"
    
    def test_missing_project_id_fails(self):
        """Test that missing project_id fails validation."""
        with pytest.raises(ValidationError):
            ServerConfig()


class TestServerConfigKeyFile:
    """Tests for key file validation."""
    
    def test_valid_key_file(self):
        """Test config with valid key file."""
        # Create a temporary key file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump({
                "type": "service_account",
                "project_id": "my-project",
                "private_key": "test-key"
            }, f)
            key_file = f.name
        
        try:
            config = ServerConfig(project_id="my-project", key_file=key_file)
            assert config.key_file == key_file
        finally:
            os.unlink(key_file)
    
    def test_nonexistent_key_file_fails(self):
        """Test that nonexistent key file fails validation."""
        with pytest.raises(ValidationError, match="not found or inaccessible"):
            ServerConfig(project_id="my-project", key_file="/nonexistent/file.json")
    
    def test_invalid_key_file_format_fails(self):
        """Test that invalid key file format fails validation."""
        # Create a temporary key file with invalid format
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump({"invalid": "format"}, f)
            key_file = f.name
        
        try:
            with pytest.raises(ValidationError, match="Invalid service account key file format"):
                ServerConfig(project_id="my-project", key_file=key_file)
        finally:
            os.unlink(key_file)
    
    def test_invalid_json_key_file_fails(self):
        """Test that malformed JSON in key file fails validation."""
        # Create a temporary key file with invalid JSON
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            f.write("not valid json{")
            key_file = f.name
        
        try:
            with pytest.raises(ValidationError, match="not valid JSON"):
                ServerConfig(project_id="my-project", key_file=key_file)
        finally:
            os.unlink(key_file)


class TestServerConfigSupabase:
    """Tests for Supabase configuration."""
    
    def test_supabase_config(self):
        """Test config with Supabase settings."""
        config = ServerConfig(
            project_id="my-project",
            supabase_url="https://example.supabase.co",
            supabase_key="anon-key",
            supabase_service_key="service-key",
            supabase_jwt_secret="jwt-secret"
        )
        assert config.supabase_url == "https://example.supabase.co"
        assert config.supabase_key == "anon-key"
        assert config.supabase_service_key == "service-key"
        assert config.supabase_jwt_secret == "jwt-secret"
    
    def test_optional_supabase_fields(self):
        """Test that Supabase fields are optional."""
        config = ServerConfig(project_id="my-project")
        assert config.supabase_url is None
        assert config.supabase_key is None
        assert config.supabase_service_key is None
        assert config.supabase_jwt_secret is None


class TestServerConfigFromEnv:
    """Tests for creating config from environment variables."""
    
    def test_from_env_with_project_id(self):
        """Test creating config from environment with PROJECT_ID."""
        with patch.dict(os.environ, {"PROJECT_ID": "my-project"}, clear=True):
            config = ServerConfig.from_env()
            assert config.project_id == "my-project"
            assert config.location == "US"
    
    def test_from_env_with_all_vars(self):
        """Test creating config from environment with all variables."""
        env_vars = {
            "PROJECT_ID": "my-project",
            "LOCATION": "EU",
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_KEY": "anon-key",
            "SUPABASE_SERVICE_KEY": "service-key",
            "SUPABASE_JWT_SECRET": "jwt-secret"
        }
        with patch.dict(os.environ, env_vars, clear=True):
            config = ServerConfig.from_env()
            assert config.project_id == "my-project"
            assert config.location == "EU"
            assert config.supabase_url == "https://example.supabase.co"
            assert config.supabase_key == "anon-key"
            assert config.supabase_service_key == "service-key"
            assert config.supabase_jwt_secret == "jwt-secret"
    
    def test_from_env_missing_project_id_fails(self):
        """Test that missing PROJECT_ID env var fails."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValidationError):
                ServerConfig.from_env()
    
    def test_from_env_case_insensitive(self):
        """Test that environment variables are case insensitive."""
        with patch.dict(os.environ, {"project_id": "my-project"}, clear=True):
            config = ServerConfig.from_env()
            assert config.project_id == "my-project"


class TestServerConfigLegacyValidate:
    """Tests for legacy validate method."""
    
    def test_legacy_validate_method(self):
        """Test that legacy validate method still works."""
        config = ServerConfig(project_id="my-project")
        # Should not raise any errors
        config.validate()
    
    def test_validate_with_invalid_config(self):
        """Test that Pydantic validation happens before validate is called."""
        # Validation now happens at instantiation, not in validate()
        with pytest.raises(ValidationError):
            ServerConfig(project_id="")


class TestServerConfigSerialization:
    """Tests for config serialization."""
    
    def test_model_dump(self):
        """Test serializing config to dict."""
        config = ServerConfig(
            project_id="my-project",
            location="EU",
            supabase_url="https://example.supabase.co"
        )
        data = config.model_dump()
        assert data["project_id"] == "my-project"
        assert data["location"] == "EU"
        assert data["supabase_url"] == "https://example.supabase.co"
    
    def test_model_dump_json(self):
        """Test serializing config to JSON."""
        config = ServerConfig(project_id="my-project")
        json_str = config.model_dump_json()
        assert "my-project" in json_str
        assert "project_id" in json_str
