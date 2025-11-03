"""Tests for authentication and authorization module."""

import pytest
import jwt
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from mcp_bigquery.core.auth import (
    UserContext,
    AuthenticationError,
    AuthorizationError,
    normalize_identifier,
    extract_dataset_table_from_path,
    verify_token,
    clear_role_cache,
)


@pytest.fixture
def jwt_secret():
    """Test JWT secret."""
    return "test-secret-key-for-testing"


@pytest.fixture
def valid_token(jwt_secret):
    """Create a valid JWT token for testing."""
    payload = {
        "sub": "user-123",
        "email": "test@example.com",
        "aud": "authenticated",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, jwt_secret, algorithm="HS256")


@pytest.fixture
def expired_token(jwt_secret):
    """Create an expired JWT token for testing."""
    payload = {
        "sub": "user-123",
        "email": "test@example.com",
        "aud": "authenticated",
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        "iat": datetime.now(timezone.utc) - timedelta(hours=2),
    }
    return jwt.encode(payload, jwt_secret, algorithm="HS256")


@pytest.fixture
def mock_supabase_kb():
    """Mock SupabaseKnowledgeBase for testing."""
    kb = MagicMock()
    kb.get_user_profile = AsyncMock(return_value={
        "user_id": "user-123",
        "metadata": {"name": "Test User"}
    })
    kb.get_user_roles = AsyncMock(return_value=[
        {"user_id": "user-123", "role_id": "role-1", "role_name": "analyst"},
        {"user_id": "user-123", "role_id": "role-2", "role_name": "viewer"}
    ])
    kb.get_role_permissions = AsyncMock(return_value=[
        {"role_id": "role-1", "permission": "query:execute"},
        {"role_id": "role-1", "permission": "cache:read"}
    ])
    kb.get_role_dataset_access = AsyncMock(return_value=[
        {"role_id": "role-1", "dataset_id": "public_data", "table_id": None},
        {"role_id": "role-1", "dataset_id": "analytics", "table_id": "events"}
    ])
    return kb


class TestNormalizeIdentifier:
    """Tests for identifier normalization."""
    
    def test_simple_identifier(self):
        """Test normalizing a simple identifier."""
        assert normalize_identifier("my_dataset") == "my_dataset"
    
    def test_backtick_quoted(self):
        """Test removing backticks."""
        assert normalize_identifier("`my-dataset`") == "my-dataset"
    
    def test_lowercase_conversion(self):
        """Test conversion to lowercase."""
        assert normalize_identifier("MyDataset") == "mydataset"
    
    def test_whitespace_handling(self):
        """Test trimming whitespace."""
        assert normalize_identifier("  my_dataset  ") == "my_dataset"
    
    def test_empty_string(self):
        """Test handling empty string."""
        assert normalize_identifier("") == ""


class TestExtractDatasetTable:
    """Tests for dataset/table extraction."""
    
    def test_dataset_table_format(self):
        """Test extracting from dataset.table format."""
        dataset, table = extract_dataset_table_from_path("my_dataset.my_table")
        assert dataset == "my_dataset"
        assert table == "my_table"
    
    def test_project_dataset_table_format(self):
        """Test extracting from project.dataset.table format."""
        dataset, table = extract_dataset_table_from_path("project.my_dataset.my_table")
        assert dataset == "my_dataset"
        assert table == "my_table"
    
    def test_single_identifier(self):
        """Test single identifier (table only)."""
        dataset, table = extract_dataset_table_from_path("my_table")
        assert dataset is None
        assert table == "my_table"


class TestVerifyToken:
    """Tests for token verification."""
    
    def test_valid_token(self, valid_token, jwt_secret):
        """Test verifying a valid token."""
        payload = verify_token(valid_token, jwt_secret)
        assert payload["sub"] == "user-123"
        assert payload["email"] == "test@example.com"
    
    def test_expired_token(self, expired_token, jwt_secret):
        """Test that expired tokens raise AuthenticationError."""
        with pytest.raises(AuthenticationError, match="Token has expired"):
            verify_token(expired_token, jwt_secret)
    
    def test_invalid_token(self, jwt_secret):
        """Test that invalid tokens raise AuthenticationError."""
        with pytest.raises(AuthenticationError, match="Invalid token"):
            verify_token("invalid.token.here", jwt_secret)
    
    def test_missing_secret(self, valid_token):
        """Test that missing secret raises AuthenticationError."""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(AuthenticationError, match="SUPABASE_JWT_SECRET not configured"):
                verify_token(valid_token, jwt_secret=None)
    
    def test_token_with_clock_skew(self, jwt_secret):
        """Test that tokens with minor clock skew are accepted due to leeway."""
        # Create a token with iat slightly in the future (simulating clock skew)
        payload = {
            "sub": "user-123",
            "email": "test@example.com",
            "aud": "authenticated",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc) + timedelta(seconds=5),  # 5 seconds in future
        }
        token = jwt.encode(payload, jwt_secret, algorithm="HS256")
        
        # Should succeed due to 10-second leeway
        decoded = verify_token(token, jwt_secret)
        assert decoded["sub"] == "user-123"
        assert decoded["email"] == "test@example.com"


class TestUserContext:
    """Tests for UserContext dataclass."""
    
    def test_has_permission(self):
        """Test permission checking."""
        context = UserContext(
            user_id="user-123",
            permissions={"query:execute", "cache:read"}
        )
        assert context.has_permission("query:execute")
        assert not context.has_permission("admin:write")
    
    def test_can_access_dataset(self):
        """Test dataset access checking."""
        context = UserContext(
            user_id="user-123",
            allowed_datasets={"public_data", "analytics"}
        )
        assert context.can_access_dataset("public_data")
        assert context.can_access_dataset("Public_Data")  # Case insensitive
        assert not context.can_access_dataset("private_data")
    
    def test_wildcard_dataset_access(self):
        """Test wildcard dataset access."""
        context = UserContext(
            user_id="user-123",
            allowed_datasets={"*"}
        )
        assert context.can_access_dataset("any_dataset")
        assert context.can_access_dataset("another_dataset")
    
    def test_can_access_table(self):
        """Test table access checking."""
        context = UserContext(
            user_id="user-123",
            allowed_datasets={"analytics"},
            allowed_tables={"analytics": {"events", "users"}}
        )
        assert context.can_access_table("analytics", "events")
        assert context.can_access_table("analytics", "users")
        assert not context.can_access_table("analytics", "private_table")
    
    def test_can_access_table_all_tables_in_dataset(self):
        """Test table access when dataset is allowed but no specific tables."""
        context = UserContext(
            user_id="user-123",
            allowed_datasets={"analytics"}
        )
        # If dataset is allowed but no specific tables defined, allow all
        assert context.can_access_table("analytics", "any_table")
    
    def test_cannot_access_table_dataset_not_allowed(self):
        """Test table access denied when dataset not allowed."""
        context = UserContext(
            user_id="user-123",
            allowed_datasets={"public_data"}
        )
        assert not context.can_access_table("analytics", "events")
    
    def test_is_expired(self):
        """Test token expiration checking."""
        expired_context = UserContext(
            user_id="user-123",
            token_expires_at=datetime.now(timezone.utc) - timedelta(hours=1)
        )
        assert expired_context.is_expired()
        
        valid_context = UserContext(
            user_id="user-123",
            token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1)
        )
        assert not valid_context.is_expired()
    
    def test_from_token_basic(self, valid_token, jwt_secret):
        """Test creating UserContext from token without Supabase."""
        context = UserContext.from_token(valid_token, jwt_secret=jwt_secret)
        assert context.user_id == "user-123"
        assert context.email == "test@example.com"
        assert context.token_expires_at is not None
    
    def test_from_token_expired(self, expired_token, jwt_secret):
        """Test that expired token raises AuthenticationError."""
        with pytest.raises(AuthenticationError, match="Token has expired"):
            UserContext.from_token(expired_token, jwt_secret=jwt_secret)
    
    def test_from_token_invalid(self, jwt_secret):
        """Test that invalid token raises AuthenticationError."""
        with pytest.raises(AuthenticationError, match="Invalid token"):
            UserContext.from_token("invalid.token", jwt_secret=jwt_secret)
    
    def test_from_token_missing_secret(self, valid_token):
        """Test that missing secret raises AuthenticationError."""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(AuthenticationError, match="SUPABASE_JWT_SECRET not configured"):
                UserContext.from_token(valid_token, jwt_secret=None)


class TestUserContextAsync:
    """Tests for async UserContext methods."""
    
    @pytest.mark.asyncio
    async def test_from_token_async_basic(self, valid_token, jwt_secret):
        """Test creating UserContext from token asynchronously."""
        context = await UserContext.from_token_async(valid_token, jwt_secret=jwt_secret)
        assert context.user_id == "user-123"
        assert context.email == "test@example.com"
    
    @pytest.mark.asyncio
    async def test_from_token_async_with_supabase(self, valid_token, jwt_secret, mock_supabase_kb):
        """Test creating UserContext with Supabase role hydration."""
        context = await UserContext.from_token_async(
            valid_token,
            jwt_secret=jwt_secret,
            supabase_kb=mock_supabase_kb
        )
        
        # Verify basic token data
        assert context.user_id == "user-123"
        assert context.email == "test@example.com"
        
        # Verify roles were loaded
        assert "analyst" in context.roles
        assert "viewer" in context.roles
        
        # Verify permissions were loaded
        assert "query:execute" in context.permissions
        assert "cache:read" in context.permissions
        
        # Verify dataset access was loaded
        assert context.can_access_dataset("public_data")
        assert context.can_access_dataset("analytics")
        
        # Verify table access
        assert context.can_access_table("analytics", "events")
        
        # Verify Supabase KB was called
        mock_supabase_kb.get_user_profile.assert_called_once_with("user-123")
        mock_supabase_kb.get_user_roles.assert_called_once_with("user-123")
    
    @pytest.mark.asyncio
    async def test_from_token_async_expired(self, expired_token, jwt_secret):
        """Test that expired token raises AuthenticationError in async context."""
        with pytest.raises(AuthenticationError, match="Token has expired"):
            await UserContext.from_token_async(expired_token, jwt_secret=jwt_secret)
    
    @pytest.mark.asyncio
    async def test_from_token_async_with_clock_skew(self, jwt_secret):
        """Test that from_token_async accepts tokens with minor clock skew."""
        # Create a token with iat slightly in the future (simulating clock skew)
        payload = {
            "sub": "user-456",
            "email": "skewtest@example.com",
            "aud": "authenticated",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc) + timedelta(seconds=8),  # 8 seconds in future
        }
        token = jwt.encode(payload, jwt_secret, algorithm="HS256")
        
        # Should succeed due to 10-second leeway
        context = await UserContext.from_token_async(token, jwt_secret=jwt_secret)
        assert context.user_id == "user-456"
        assert context.email == "skewtest@example.com"


class TestRoleCache:
    """Tests for role caching functionality."""
    
    def test_cache_clearing(self):
        """Test that cache can be cleared."""
        from mcp_bigquery.core.auth import _set_cached_role_data, _get_cached_role_data
        
        # Set some cache data
        _set_cached_role_data("test_key", {"data": "value"})
        assert _get_cached_role_data("test_key") == {"data": "value"}
        
        # Clear cache
        clear_role_cache()
        assert _get_cached_role_data("test_key") is None
    
    def test_cache_expiration(self):
        """Test that cache entries expire after TTL."""
        from mcp_bigquery.core.auth import _set_cached_role_data, _get_cached_role_data, _role_cache
        
        # Set cache with custom expiration
        cache_key = "test_expiry"
        expired_time = datetime.now(timezone.utc) - timedelta(seconds=1)
        _role_cache[cache_key] = ({"data": "value"}, expired_time)
        
        # Should return None for expired cache
        assert _get_cached_role_data(cache_key) is None
        
        # Expired entry should be removed
        assert cache_key not in _role_cache


@pytest.mark.asyncio
async def test_supabase_kb_integration(mock_supabase_kb):
    """Test integration with SupabaseKnowledgeBase."""
    # Test get_user_profile
    profile = await mock_supabase_kb.get_user_profile("user-123")
    assert profile["user_id"] == "user-123"
    
    # Test get_user_roles
    roles = await mock_supabase_kb.get_user_roles("user-123")
    assert len(roles) == 2
    assert roles[0]["role_name"] == "analyst"
    
    # Test get_role_permissions
    permissions = await mock_supabase_kb.get_role_permissions("role-1")
    assert len(permissions) == 2
    assert permissions[0]["permission"] == "query:execute"
    
    # Test get_role_dataset_access
    access = await mock_supabase_kb.get_role_dataset_access("role-1")
    assert len(access) == 2
    assert access[0]["dataset_id"] == "public_data"
