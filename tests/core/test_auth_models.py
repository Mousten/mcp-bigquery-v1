"""Tests for Pydantic models in auth module."""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from mcp_bigquery.core.auth import (
    UserProfile,
    UserRole,
    RolePermission,
    DatasetAccess,
    UserContext,
)


class TestUserProfile:
    """Tests for UserProfile Pydantic model."""
    
    def test_valid_user_profile(self):
        """Test creating a valid user profile."""
        profile = UserProfile(
            user_id="user-123",
            metadata={"name": "Test User", "role": "admin"}
        )
        assert profile.user_id == "user-123"
        assert profile.metadata["name"] == "Test User"
    
    def test_user_profile_with_timestamps(self):
        """Test user profile with timestamps."""
        now = datetime.now(timezone.utc)
        profile = UserProfile(
            user_id="user-123",
            metadata={},
            created_at=now,
            updated_at=now
        )
        assert profile.created_at == now
        assert profile.updated_at == now
    
    def test_user_profile_defaults(self):
        """Test user profile with default values."""
        profile = UserProfile(user_id="user-123")
        assert profile.metadata == {}
        assert profile.created_at is None
        assert profile.updated_at is None


class TestUserRole:
    """Tests for UserRole Pydantic model."""
    
    def test_valid_user_role(self):
        """Test creating a valid user role."""
        role = UserRole(
            user_id="user-123",
            role_id="role-1",
            role_name="analyst"
        )
        assert role.user_id == "user-123"
        assert role.role_id == "role-1"
        assert role.role_name == "analyst"
    
    def test_user_role_with_timestamp(self):
        """Test user role with timestamp."""
        now = datetime.now(timezone.utc)
        role = UserRole(
            user_id="user-123",
            role_id="role-1",
            role_name="analyst",
            assigned_at=now
        )
        assert role.assigned_at == now


class TestRolePermission:
    """Tests for RolePermission Pydantic model."""
    
    def test_valid_role_permission(self):
        """Test creating a valid role permission."""
        perm = RolePermission(
            role_id="role-1",
            permission="query:execute"
        )
        assert perm.role_id == "role-1"
        assert perm.permission == "query:execute"
    
    def test_role_permission_with_description(self):
        """Test role permission with description."""
        perm = RolePermission(
            role_id="role-1",
            permission="query:execute",
            description="Allow executing BigQuery queries"
        )
        assert perm.description == "Allow executing BigQuery queries"


class TestDatasetAccess:
    """Tests for DatasetAccess Pydantic model."""
    
    def test_valid_dataset_access(self):
        """Test creating valid dataset access."""
        access = DatasetAccess(
            role_id="role-1",
            dataset_id="analytics"
        )
        assert access.role_id == "role-1"
        assert access.dataset_id == "analytics"
        assert access.table_id is None
        assert access.access_level == "read"
    
    def test_dataset_access_with_table(self):
        """Test dataset access with specific table."""
        access = DatasetAccess(
            role_id="role-1",
            dataset_id="analytics",
            table_id="events"
        )
        assert access.table_id == "events"
    
    def test_dataset_access_with_custom_level(self):
        """Test dataset access with custom access level."""
        access = DatasetAccess(
            role_id="role-1",
            dataset_id="analytics",
            access_level="write"
        )
        assert access.access_level == "write"
    
    def test_empty_dataset_id_fails(self):
        """Test that empty dataset_id fails validation."""
        with pytest.raises(ValidationError):
            DatasetAccess(
                role_id="role-1",
                dataset_id=""
            )
    
    def test_whitespace_dataset_id_fails(self):
        """Test that whitespace-only dataset_id fails validation."""
        with pytest.raises(ValidationError):
            DatasetAccess(
                role_id="role-1",
                dataset_id="   "
            )


class TestUserContextValidation:
    """Tests for UserContext Pydantic model validation."""
    
    def test_valid_user_context(self):
        """Test creating a valid user context."""
        context = UserContext(
            user_id="user-123",
            email="test@example.com"
        )
        assert context.user_id == "user-123"
        assert context.email == "test@example.com"
    
    def test_empty_user_id_fails(self):
        """Test that empty user_id fails validation."""
        with pytest.raises(ValidationError):
            UserContext(user_id="")
    
    def test_whitespace_user_id_fails(self):
        """Test that whitespace-only user_id fails validation."""
        with pytest.raises(ValidationError):
            UserContext(user_id="   ")
    
    def test_invalid_email_fails(self):
        """Test that invalid email fails validation."""
        with pytest.raises(ValidationError):
            UserContext(user_id="user-123", email="not-an-email")
    
    def test_user_id_trimmed(self):
        """Test that user_id is trimmed."""
        context = UserContext(user_id="  user-123  ")
        assert context.user_id == "user-123"
    
    def test_user_context_with_all_fields(self):
        """Test user context with all fields populated."""
        now = datetime.now(timezone.utc)
        context = UserContext(
            user_id="user-123",
            email="test@example.com",
            roles=["analyst", "viewer"],
            permissions={"query:execute", "cache:read"},
            allowed_datasets={"analytics", "public_data"},
            allowed_tables={"analytics": {"events", "users"}},
            metadata={"name": "Test User"},
            token_expires_at=now
        )
        assert len(context.roles) == 2
        assert len(context.permissions) == 2
        assert len(context.allowed_datasets) == 2
        assert "analytics" in context.allowed_tables
        assert len(context.allowed_tables["analytics"]) == 2
        assert context.token_expires_at == now
    
    def test_user_context_json_serialization(self):
        """Test that user context can be serialized to JSON."""
        context = UserContext(
            user_id="user-123",
            email="test@example.com",
            roles=["analyst"],
            permissions={"query:execute"}
        )
        # Pydantic v2 uses model_dump instead of dict
        data = context.model_dump()
        assert data["user_id"] == "user-123"
        assert data["email"] == "test@example.com"
        assert "analyst" in data["roles"]
    
    def test_user_context_json_deserialization(self):
        """Test that user context can be deserialized from JSON."""
        data = {
            "user_id": "user-123",
            "email": "test@example.com",
            "roles": ["analyst"],
            "permissions": ["query:execute"],
            "allowed_datasets": ["analytics"],
            "allowed_tables": {},
            "metadata": {}
        }
        context = UserContext(**data)
        assert context.user_id == "user-123"
        assert context.email == "test@example.com"


class TestPydanticModelInteraction:
    """Tests for interaction between Pydantic models."""
    
    def test_multiple_models_together(self):
        """Test creating multiple related models."""
        profile = UserProfile(user_id="user-123", metadata={"name": "Test"})
        role = UserRole(user_id="user-123", role_id="role-1", role_name="analyst")
        perm = RolePermission(role_id="role-1", permission="query:execute")
        access = DatasetAccess(role_id="role-1", dataset_id="analytics")
        
        # Verify relationships
        assert profile.user_id == role.user_id
        assert role.role_id == perm.role_id
        assert role.role_id == access.role_id
    
    def test_model_validation_chain(self):
        """Test that validation works across related models."""
        # Create valid models
        role = UserRole(user_id="user-123", role_id="role-1", role_name="analyst")
        
        # Try to create invalid access for the role
        with pytest.raises(ValidationError):
            DatasetAccess(role_id=role.role_id, dataset_id="")
