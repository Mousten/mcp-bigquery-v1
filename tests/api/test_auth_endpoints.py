"""Tests for authenticated API endpoints."""

import pytest
import jwt
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI, Depends

from mcp_bigquery.core.auth import UserContext
from mcp_bigquery.api.dependencies import create_auth_dependency
from mcp_bigquery.handlers.tools import get_datasets_handler, query_tool_handler
from mcp_bigquery.routes.tools import create_tools_router


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
def mock_bigquery_client():
    """Mock BigQuery client."""
    client = MagicMock()
    dataset1 = MagicMock()
    dataset1.dataset_id = "public_data"
    dataset2 = MagicMock()
    dataset2.dataset_id = "private_data"
    client.list_datasets.return_value = [dataset1, dataset2]
    return client


@pytest.fixture
def mock_event_manager():
    """Mock event manager."""
    manager = MagicMock()
    manager.broadcast = AsyncMock()
    return manager


@pytest.fixture
def mock_supabase_kb():
    """Mock SupabaseKnowledgeBase for testing."""
    kb = MagicMock()
    kb.get_user_profile = AsyncMock(return_value={
        "user_id": "user-123",
        "metadata": {"name": "Test User"}
    })
    kb.get_user_roles = AsyncMock(return_value=[
        {"user_id": "user-123", "role_id": "role-1", "role_name": "analyst"}
    ])
    kb.get_role_permissions = AsyncMock(return_value=[
        {"role_id": "role-1", "permission": "query:execute"},
        {"role_id": "role-1", "permission": "dataset:list"}
    ])
    kb.get_role_dataset_access = AsyncMock(return_value=[
        {"role_id": "role-1", "dataset_id": "public_data", "table_id": None}
    ])
    return kb


@pytest.fixture
def user_context_with_access():
    """User context with access to public_data."""
    return UserContext(
        user_id="user-123",
        email="test@example.com",
        roles=["analyst"],
        permissions={"query:execute", "dataset:list"},
        allowed_datasets={"public_data"}
    )


@pytest.fixture
def user_context_no_access():
    """User context with no dataset access."""
    return UserContext(
        user_id="user-456",
        email="other@example.com",
        roles=["viewer"],
        permissions={"query:execute"},
        allowed_datasets=set()
    )


class TestAuthenticationEndpoints:
    """Tests for endpoint authentication."""
    
    @pytest.mark.asyncio
    async def test_missing_auth_token(self, mock_bigquery_client, mock_event_manager, mock_supabase_kb):
        """Test that requests without auth token receive 401."""
        app = FastAPI()
        router = create_tools_router(mock_bigquery_client, mock_event_manager, mock_supabase_kb)
        app.include_router(router)
        
        client = TestClient(app)
        response = client.get("/tools/datasets")
        
        assert response.status_code == 401
        assert "authentication" in response.json()["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_expired_auth_token(
        self,
        expired_token,
        jwt_secret,
        mock_bigquery_client,
        mock_event_manager,
        mock_supabase_kb
    ):
        """Test that expired tokens receive 401."""
        with patch.dict('os.environ', {'SUPABASE_JWT_SECRET': jwt_secret}):
            app = FastAPI()
            router = create_tools_router(mock_bigquery_client, mock_event_manager, mock_supabase_kb)
            app.include_router(router)
            
            client = TestClient(app)
            response = client.get(
                "/tools/datasets",
                headers={"Authorization": f"Bearer {expired_token}"}
            )
            
            assert response.status_code == 401
            assert "expired" in response.json()["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_invalid_auth_token(self, mock_bigquery_client, mock_event_manager, mock_supabase_kb):
        """Test that invalid tokens receive 401."""
        app = FastAPI()
        router = create_tools_router(mock_bigquery_client, mock_event_manager, mock_supabase_kb)
        app.include_router(router)
        
        client = TestClient(app)
        response = client.get(
            "/tools/datasets",
            headers={"Authorization": "Bearer invalid.token.here"}
        )
        
        assert response.status_code == 401


class TestDatasetAccessControl:
    """Tests for dataset-level access control."""
    
    @pytest.mark.asyncio
    async def test_user_sees_only_allowed_datasets(
        self,
        mock_bigquery_client,
        user_context_with_access
    ):
        """Test that users only see datasets they have access to."""
        result = await get_datasets_handler(mock_bigquery_client, user_context_with_access)
        
        assert "datasets" in result
        datasets = result["datasets"]
        
        # User should only see public_data, not private_data
        dataset_ids = [d["dataset_id"] for d in datasets]
        assert "public_data" in dataset_ids
        assert "private_data" not in dataset_ids
    
    @pytest.mark.asyncio
    async def test_user_with_no_access_sees_empty_list(
        self,
        mock_bigquery_client,
        user_context_no_access
    ):
        """Test that users with no dataset access see empty list."""
        result = await get_datasets_handler(mock_bigquery_client, user_context_no_access)
        
        assert "datasets" in result
        assert len(result["datasets"]) == 0


class TestQueryAccessControl:
    """Tests for query-level access control."""
    
    @pytest.mark.asyncio
    async def test_query_with_unauthorized_table_rejected(
        self,
        mock_bigquery_client,
        mock_event_manager,
        user_context_with_access
    ):
        """Test that queries accessing unauthorized tables are rejected."""
        sql = "SELECT * FROM private_data.secret_table"
        
        result = await query_tool_handler(
            mock_bigquery_client,
            mock_event_manager,
            sql,
            user_context_with_access,
            knowledge_base=None,
            use_cache=False
        )
        
        # Should return error tuple
        assert isinstance(result, tuple)
        error_dict, status_code = result
        assert status_code == 403
        assert "access denied" in error_dict["error"].lower()
    
    @pytest.mark.asyncio
    async def test_query_with_authorized_table_proceeds(
        self,
        mock_bigquery_client,
        mock_event_manager,
        user_context_with_access
    ):
        """Test that queries accessing authorized tables proceed."""
        # Mock the BigQuery client to return a successful result
        mock_job = MagicMock()
        mock_job.job_id = "test-job-id"
        mock_job.total_bytes_processed = 1000
        mock_job.started = datetime.now(timezone.utc)
        mock_job.ended = datetime.now(timezone.utc)
        mock_job.result.return_value = []
        
        mock_bigquery_client.query.return_value = mock_job
        
        sql = "SELECT * FROM public_data.events"
        
        result = await query_tool_handler(
            mock_bigquery_client,
            mock_event_manager,
            sql,
            user_context_with_access,
            knowledge_base=None,
            use_cache=False
        )
        
        # Should return success result
        assert isinstance(result, dict)
        assert "content" in result
        assert result["isError"] is False
    
    @pytest.mark.asyncio
    async def test_query_without_permission_rejected(
        self,
        mock_bigquery_client,
        mock_event_manager
    ):
        """Test that queries without query:execute permission are rejected."""
        user_context = UserContext(
            user_id="user-789",
            permissions=set(),  # No permissions
            allowed_datasets={"public_data"}
        )
        
        sql = "SELECT * FROM public_data.events"
        
        result = await query_tool_handler(
            mock_bigquery_client,
            mock_event_manager,
            sql,
            user_context,
            knowledge_base=None,
            use_cache=False
        )
        
        # Should return error tuple
        assert isinstance(result, tuple)
        error_dict, status_code = result
        assert status_code == 403
        assert "permission" in error_dict["error"].lower()


class TestEndToEndAuthorization:
    """End-to-end authorization tests."""
    
    @pytest.mark.asyncio
    async def test_full_request_lifecycle_with_valid_auth(
        self,
        valid_token,
        jwt_secret,
        mock_bigquery_client,
        mock_event_manager,
        mock_supabase_kb
    ):
        """Test full request lifecycle with valid authentication."""
        with patch.dict('os.environ', {'SUPABASE_JWT_SECRET': jwt_secret}):
            app = FastAPI()
            router = create_tools_router(mock_bigquery_client, mock_event_manager, mock_supabase_kb)
            app.include_router(router)
            
            client = TestClient(app)
            response = client.get(
                "/tools/datasets",
                headers={"Authorization": f"Bearer {valid_token}"}
            )
            
            # Should succeed with user's accessible datasets
            assert response.status_code == 200
            data = response.json()
            assert "datasets" in data
