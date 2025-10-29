"""Tests for BigQuery RBAC enforcement including table access and cache isolation."""
import pytest
from unittest.mock import Mock, AsyncMock, MagicMock
from typing import List, Tuple, Optional
from datetime import datetime, timezone

from src.mcp_bigquery.core.auth import UserContext, AuthorizationError
from src.mcp_bigquery.handlers.tools import (
    extract_table_references,
    check_table_access,
    query_tool_handler,
    get_datasets_handler,
    get_tables_handler,
    get_table_schema_handler,
)
from src.mcp_bigquery.core.supabase_client import SupabaseKnowledgeBase


@pytest.fixture
def user_with_limited_access():
    """User with access to only specific datasets/tables."""
    return UserContext(
        user_id="user123",
        email="user@example.com",
        roles=["analyst"],
        permissions={"query:execute", "dataset:list"},
        allowed_datasets={"public_data", "analytics"},
        allowed_tables={
            "public_data": {"customers", "orders"},
            "analytics": {"*"}  # All tables in analytics
        }
    )


@pytest.fixture
def user_with_wildcard_access():
    """User with wildcard access to all datasets."""
    return UserContext(
        user_id="admin123",
        email="admin@example.com",
        roles=["admin"],
        permissions={"query:execute", "dataset:list", "dataset:admin"},
        allowed_datasets={"*"},
        allowed_tables={}
    )


@pytest.fixture
def user_with_no_access():
    """User with no dataset access."""
    return UserContext(
        user_id="restricted123",
        email="restricted@example.com",
        roles=["viewer"],
        permissions=set(),
        allowed_datasets=set(),
        allowed_tables={}
    )


class TestTableReferenceParsing:
    """Test table reference extraction from SQL."""
    
    def test_extract_simple_table_reference(self):
        """Test extracting simple table reference."""
        sql = "SELECT * FROM dataset.table"
        refs = extract_table_references(sql)
        assert len(refs) == 1
        assert refs[0] == (None, "dataset", "table")
    
    def test_extract_fully_qualified_reference(self):
        """Test extracting fully qualified table reference."""
        sql = "SELECT * FROM project.dataset.table"
        refs = extract_table_references(sql)
        assert len(refs) == 1
        assert refs[0] == ("project", "dataset", "table")
    
    def test_extract_multiple_tables(self):
        """Test extracting multiple table references from JOIN."""
        sql = """
        SELECT * FROM project1.dataset1.table1 t1
        JOIN project2.dataset2.table2 t2 ON t1.id = t2.id
        """
        refs = extract_table_references(sql)
        assert len(refs) == 2
        assert ("project1", "dataset1", "table1") in refs
        assert ("project2", "dataset2", "table2") in refs
    
    def test_extract_with_default_project(self):
        """Test extraction with default project."""
        sql = "SELECT * FROM dataset.table"
        refs = extract_table_references(sql, default_project="myproject")
        assert len(refs) == 1
        assert refs[0] == ("myproject", "dataset", "table")
    
    def test_extract_case_insensitive(self):
        """Test case-insensitive FROM/JOIN matching."""
        sql = "select * from dataset.table join other.table2"
        refs = extract_table_references(sql)
        assert len(refs) == 2


class TestPermissionChecks:
    """Test permission checking logic."""
    
    def test_allowed_table_access(self, user_with_limited_access):
        """Test access to allowed table succeeds."""
        refs = [(None, "public_data", "customers")]
        # Should not raise
        check_table_access(user_with_limited_access, refs)
    
    def test_forbidden_table_access(self, user_with_limited_access):
        """Test access to forbidden table is denied."""
        refs = [(None, "restricted_data", "secret_table")]
        with pytest.raises(AuthorizationError) as exc_info:
            check_table_access(user_with_limited_access, refs)
        assert "Access denied" in str(exc_info.value)
        assert "restricted_data" in str(exc_info.value)
    
    def test_wildcard_table_access(self, user_with_limited_access):
        """Test wildcard access to all tables in a dataset."""
        refs = [(None, "analytics", "any_table")]
        # Should not raise - analytics has wildcard access
        check_table_access(user_with_limited_access, refs)
    
    def test_wildcard_dataset_access(self, user_with_wildcard_access):
        """Test wildcard access to any dataset."""
        refs = [(None, "any_dataset", "any_table")]
        # Should not raise - user has wildcard dataset access
        check_table_access(user_with_wildcard_access, refs)
    
    def test_no_access_user(self, user_with_no_access):
        """Test user with no access is denied."""
        refs = [(None, "public_data", "customers")]
        with pytest.raises(AuthorizationError):
            check_table_access(user_with_no_access, refs)
    
    def test_multiple_tables_mixed_access(self, user_with_limited_access):
        """Test query with mix of allowed and forbidden tables."""
        refs = [
            (None, "public_data", "customers"),  # Allowed
            (None, "restricted_data", "secret")  # Forbidden
        ]
        with pytest.raises(AuthorizationError) as exc_info:
            check_table_access(user_with_limited_access, refs)
        assert "restricted_data" in str(exc_info.value)


class TestQueryHandlerRBAC:
    """Test RBAC in query handler."""
    
    @pytest.mark.asyncio
    async def test_query_with_allowed_tables(self, user_with_limited_access):
        """Test query execution with allowed tables."""
        # Mock BigQuery client
        mock_client = Mock()
        mock_job = Mock()
        mock_job.job_id = "job123"
        mock_job.total_bytes_processed = 1024
        mock_job.started = datetime.now(timezone.utc)
        mock_job.ended = datetime.now(timezone.utc)
        mock_result = [{"id": 1, "name": "test"}]
        mock_job.result.return_value = [Mock(items=lambda: mock_result[0].items())]
        mock_client.query.return_value = mock_job
        
        # Mock event manager
        mock_event_manager = Mock()
        mock_event_manager.broadcast = AsyncMock()
        
        sql = "SELECT * FROM public_data.customers"
        
        result = await query_tool_handler(
            bigquery_client=mock_client,
            event_manager=mock_event_manager,
            sql=sql,
            user_context=user_with_limited_access,
            knowledge_base=None,
            use_cache=False
        )
        
        # Should succeed
        assert "error" not in result or result.get("isError") is False
        mock_client.query.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_query_with_forbidden_tables(self, user_with_limited_access):
        """Test query execution with forbidden tables returns 403."""
        mock_client = Mock()
        mock_event_manager = Mock()
        mock_event_manager.broadcast = AsyncMock()
        
        sql = "SELECT * FROM restricted_data.secret_table"
        
        result = await query_tool_handler(
            bigquery_client=mock_client,
            event_manager=mock_event_manager,
            sql=sql,
            user_context=user_with_limited_access,
            knowledge_base=None,
            use_cache=False
        )
        
        # Should return error with 403 status
        assert isinstance(result, tuple)
        error_dict, status_code = result
        assert status_code == 403
        assert "Access denied" in error_dict["error"]
    
    @pytest.mark.asyncio
    async def test_query_without_permission(self, user_with_no_access):
        """Test query execution without query:execute permission."""
        mock_client = Mock()
        mock_event_manager = Mock()
        mock_event_manager.broadcast = AsyncMock()
        
        sql = "SELECT * FROM public_data.customers"
        
        result = await query_tool_handler(
            bigquery_client=mock_client,
            event_manager=mock_event_manager,
            sql=sql,
            user_context=user_with_no_access,
            knowledge_base=None,
            use_cache=False
        )
        
        # Should return error with 403 status
        assert isinstance(result, tuple)
        error_dict, status_code = result
        assert status_code == 403
        assert "permission" in error_dict["error"].lower()


class TestDatasetListingRBAC:
    """Test RBAC in dataset listing."""
    
    @pytest.mark.asyncio
    async def test_list_datasets_filtered(self, user_with_limited_access):
        """Test dataset listing is filtered by user permissions."""
        mock_client = Mock()
        mock_datasets = [
            Mock(dataset_id="public_data"),
            Mock(dataset_id="analytics"),
            Mock(dataset_id="restricted_data"),
            Mock(dataset_id="private_data"),
        ]
        mock_client.list_datasets.return_value = mock_datasets
        
        result = await get_datasets_handler(mock_client, user_with_limited_access)
        
        # Should only return allowed datasets
        assert "datasets" in result
        dataset_ids = [d["dataset_id"] for d in result["datasets"]]
        assert "public_data" in dataset_ids
        assert "analytics" in dataset_ids
        assert "restricted_data" not in dataset_ids
        assert "private_data" not in dataset_ids
    
    @pytest.mark.asyncio
    async def test_list_datasets_wildcard(self, user_with_wildcard_access):
        """Test dataset listing with wildcard access."""
        mock_client = Mock()
        mock_datasets = [
            Mock(dataset_id="dataset1"),
            Mock(dataset_id="dataset2"),
            Mock(dataset_id="dataset3"),
        ]
        mock_client.list_datasets.return_value = mock_datasets
        
        result = await get_datasets_handler(mock_client, user_with_wildcard_access)
        
        # Should return all datasets
        assert "datasets" in result
        assert len(result["datasets"]) == 3


class TestTableListingRBAC:
    """Test RBAC in table listing."""
    
    @pytest.mark.asyncio
    async def test_list_tables_with_access(self, user_with_limited_access):
        """Test table listing for allowed dataset."""
        mock_client = Mock()
        mock_tables = [
            Mock(table_id="customers"),
            Mock(table_id="orders"),
            Mock(table_id="products"),
        ]
        mock_client.list_tables.return_value = mock_tables
        
        result = await get_tables_handler(
            mock_client,
            "public_data",
            user_with_limited_access
        )
        
        # Should only return allowed tables
        assert "tables" in result
        table_ids = [t["table_id"] for t in result["tables"]]
        assert "customers" in table_ids
        assert "orders" in table_ids
        # products not in allowed_tables, so shouldn't be returned
        # (when specific tables are defined, only those are allowed)
        assert "products" not in table_ids
    
    @pytest.mark.asyncio
    async def test_list_tables_without_dataset_access(self, user_with_limited_access):
        """Test table listing for forbidden dataset returns 403."""
        mock_client = Mock()
        
        result = await get_tables_handler(
            mock_client,
            "restricted_data",
            user_with_limited_access
        )
        
        # Should return error with 403 status
        assert isinstance(result, tuple)
        error_dict, status_code = result
        assert status_code == 403
        assert "Access denied" in error_dict["error"]
    
    @pytest.mark.asyncio
    async def test_list_tables_wildcard_access(self, user_with_limited_access):
        """Test table listing with wildcard table access."""
        mock_client = Mock()
        mock_tables = [
            Mock(table_id="table1"),
            Mock(table_id="table2"),
            Mock(table_id="table3"),
        ]
        mock_client.list_tables.return_value = mock_tables
        
        result = await get_tables_handler(
            mock_client,
            "analytics",  # Has wildcard access
            user_with_limited_access
        )
        
        # Should return all tables (wildcard access)
        assert "tables" in result
        assert len(result["tables"]) == 3


class TestTableSchemaRBAC:
    """Test RBAC in table schema retrieval."""
    
    @pytest.mark.asyncio
    async def test_get_schema_with_access(self, user_with_limited_access):
        """Test schema retrieval for allowed table."""
        mock_client = Mock()
        mock_table = Mock()
        mock_table.schema = [
            Mock(name="id", field_type="INTEGER", mode="REQUIRED"),
            Mock(name="name", field_type="STRING", mode="NULLABLE"),
        ]
        mock_client.dataset.return_value.table.return_value = Mock()
        mock_client.get_table.return_value = mock_table
        
        result = await get_table_schema_handler(
            mock_client,
            "public_data",
            "customers",
            user_with_limited_access
        )
        
        # Should succeed
        assert "schema" in result
        assert len(result["schema"]) == 2
    
    @pytest.mark.asyncio
    async def test_get_schema_without_access(self, user_with_limited_access):
        """Test schema retrieval for forbidden table returns 403."""
        mock_client = Mock()
        
        result = await get_table_schema_handler(
            mock_client,
            "restricted_data",
            "secret_table",
            user_with_limited_access
        )
        
        # Should return error with 403 status
        assert isinstance(result, tuple)
        error_dict, status_code = result
        assert status_code == 403
        assert "Access denied" in error_dict["error"]


class TestCacheIsolation:
    """Test cache isolation per user."""
    
    @pytest.mark.asyncio
    async def test_cache_requires_user_id_for_read(self):
        """Test cache read requires user_id."""
        mock_supabase = Mock()
        kb = SupabaseKnowledgeBase.__new__(SupabaseKnowledgeBase)
        kb.supabase = mock_supabase
        kb._connection_verified = True
        
        # Try to read cache without user_id
        result = await kb.get_cached_query("SELECT * FROM table", user_id=None)
        
        # Should return None (not allowed)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_cache_requires_user_id_for_write(self):
        """Test cache write requires user_id."""
        mock_supabase = Mock()
        kb = SupabaseKnowledgeBase.__new__(SupabaseKnowledgeBase)
        kb.supabase = mock_supabase
        kb._connection_verified = True
        
        # Try to write cache without user_id
        result = await kb.cache_query_result(
            "SELECT * FROM table",
            [{"id": 1}],
            {},
            ["table"],
            user_id=None
        )
        
        # Should return False (not allowed)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_cache_read_filtered_by_user(self):
        """Test cache reads are filtered by user_id."""
        mock_supabase = Mock()
        mock_query = Mock()
        mock_query.eq.return_value = mock_query
        mock_query.gte.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.execute.return_value = Mock(data=[])
        
        mock_table = Mock()
        mock_table.select.return_value = mock_query
        mock_supabase.table.return_value = mock_table
        
        kb = SupabaseKnowledgeBase.__new__(SupabaseKnowledgeBase)
        kb.supabase = mock_supabase
        kb._connection_verified = True
        
        await kb.get_cached_query("SELECT * FROM table", user_id="user123")
        
        # Verify user_id filter was applied
        calls = [str(call) for call in mock_query.eq.call_args_list]
        assert any("user_id" in str(call) and "user123" in str(call) for call in calls)
    
    @pytest.mark.asyncio
    async def test_cache_write_includes_user_id(self):
        """Test cache writes include user_id."""
        mock_supabase = Mock()
        mock_insert = Mock()
        mock_insert.execute.return_value = Mock(data=[{"id": "cache123"}])
        mock_table = Mock()
        mock_table.insert.return_value = mock_insert
        mock_supabase.table.return_value = mock_table
        
        kb = SupabaseKnowledgeBase.__new__(SupabaseKnowledgeBase)
        kb.supabase = mock_supabase
        kb._connection_verified = True
        kb._insert_table_dependencies = AsyncMock()
        
        await kb.cache_query_result(
            "SELECT * FROM table",
            [{"id": 1}],
            {},
            ["table"],
            user_id="user123"
        )
        
        # Verify user_id was included in cache data
        insert_call = mock_table.insert.call_args
        cache_data = insert_call[0][0]
        assert cache_data["user_id"] == "user123"


class TestIntegrationScenarios:
    """Integration tests for complete RBAC scenarios."""
    
    @pytest.mark.asyncio
    async def test_user_can_only_see_their_cached_queries(self):
        """Test users can only see their own cached query results."""
        # This would be an integration test with actual Supabase
        # For now, it's a placeholder showing the requirement
        pass
    
    @pytest.mark.asyncio
    async def test_forbidden_query_not_cached(self, user_with_limited_access):
        """Test forbidden queries are rejected before caching."""
        mock_client = Mock()
        mock_event_manager = Mock()
        mock_event_manager.broadcast = AsyncMock()
        
        sql = "SELECT * FROM restricted_data.secret"
        
        result = await query_tool_handler(
            bigquery_client=mock_client,
            event_manager=mock_event_manager,
            sql=sql,
            user_context=user_with_limited_access,
            knowledge_base=None,
            use_cache=True
        )
        
        # Should fail with 403 before executing query or caching
        assert isinstance(result, tuple)
        _, status_code = result
        assert status_code == 403
        # Verify query was never executed
        mock_client.query.assert_not_called()
