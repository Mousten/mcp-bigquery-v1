"""Async HTTP client for invoking the MCP BigQuery server.

This module provides a client for calling the MCP BigQuery REST API
with automatic JWT authentication, retry logic, and typed responses.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Set
from datetime import datetime, timezone

import httpx
from pydantic import BaseModel, Field

from ..core.auth import AuthenticationError, AuthorizationError


logger = logging.getLogger(__name__)


class QueryResult(BaseModel):
    """Result of a BigQuery query execution."""
    query_id: Optional[str] = None
    rows: List[Dict[str, Any]] = Field(default_factory=list)
    statistics: Optional[Dict[str, Any]] = None
    cached: bool = False
    cached_at: Optional[str] = None
    error: Optional[str] = None


class DatasetInfo(BaseModel):
    """Information about a BigQuery dataset."""
    dataset_id: str
    project_id: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    created: Optional[datetime] = None
    modified: Optional[datetime] = None


class TableInfo(BaseModel):
    """Information about a BigQuery table."""
    table_id: str
    dataset_id: str
    project_id: Optional[str] = None
    table_type: Optional[str] = None
    num_rows: Optional[int] = None
    num_bytes: Optional[int] = None
    created: Optional[datetime] = None
    modified: Optional[datetime] = None
    description: Optional[str] = None


class TableSchema(BaseModel):
    """Schema information for a BigQuery table."""
    table_id: str
    dataset_id: str
    project_id: Optional[str] = None
    schema_fields: List[Dict[str, Any]] = Field(default_factory=list)
    num_rows: Optional[int] = None
    num_bytes: Optional[int] = None
    description: Optional[str] = None
    sample_rows: List[Dict[str, Any]] = Field(default_factory=list)


class HealthStatus(BaseModel):
    """Server health status."""
    status: str
    timestamp: float
    connections: Optional[Dict[str, Any]] = None


class MCPBigQueryClient:
    """Async HTTP client for the MCP BigQuery server.
    
    This client wraps the REST API endpoints with automatic authentication,
    retry logic, and typed response models.
    
    Args:
        base_url: Base URL of the MCP BigQuery server (e.g., "http://localhost:8000")
        auth_token: Optional Supabase JWT for authentication
        session_id: Optional session identifier for tracking
        max_retries: Maximum number of retry attempts for failed requests
        timeout: Request timeout in seconds
        
    Example:
        >>> async with MCPBigQueryClient("http://localhost:8000", auth_token="jwt") as client:
        ...     result = await client.execute_sql("SELECT 1 as num")
        ...     print(result.rows)
    """
    
    def __init__(
        self,
        base_url: str,
        auth_token: Optional[str] = None,
        session_id: Optional[str] = None,
        max_retries: int = 3,
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token
        self.session_id = session_id
        self.max_retries = max_retries
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        
    async def __aenter__(self) -> "MCPBigQueryClient":
        """Async context manager entry."""
        await self.connect()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
        
    async def connect(self):
        """Initialize the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
            
    async def close(self):
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests including authentication."""
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        if self.session_id:
            headers["X-Session-ID"] = self.session_id
        return headers
        
    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        retry_count: int = 0,
    ) -> Dict[str, Any]:
        """Make an HTTP request with retry logic.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path (e.g., "/tools/query")
            params: Optional query parameters
            json: Optional JSON body
            retry_count: Current retry attempt
            
        Returns:
            Response JSON as dict
            
        Raises:
            AuthenticationError: If authentication fails (401)
            AuthorizationError: If authorization fails (403)
            httpx.HTTPError: For other HTTP errors
        """
        if self._client is None:
            await self.connect()
            
        url = f"{self.base_url}{path}"
        headers = self._get_headers()
        
        try:
            response = await self._client.request(
                method=method,
                url=url,
                params=params,
                json=json,
                headers=headers,
            )
            
            # Handle authentication and authorization errors
            if response.status_code == 401:
                error_data = response.json() if response.content else {"error": "Unauthorized"}
                raise AuthenticationError(error_data.get("error", "Authentication failed"))
                
            if response.status_code == 403:
                error_data = response.json() if response.content else {"error": "Forbidden"}
                raise AuthorizationError(error_data.get("error", "Authorization failed"))
                
            # Raise for other HTTP errors
            response.raise_for_status()
            
            # Return JSON response
            return response.json()
            
        except httpx.TimeoutException as e:
            logger.warning(f"Request timeout for {method} {url}: {e}")
            if retry_count < self.max_retries:
                wait_time = 2 ** retry_count
                logger.info(f"Retrying in {wait_time}s (attempt {retry_count + 1}/{self.max_retries})")
                await asyncio.sleep(wait_time)
                return await self._request(method, path, params, json, retry_count + 1)
            raise
            
        except httpx.NetworkError as e:
            logger.warning(f"Network error for {method} {url}: {e}")
            if retry_count < self.max_retries:
                wait_time = 2 ** retry_count
                logger.info(f"Retrying in {wait_time}s (attempt {retry_count + 1}/{self.max_retries})")
                await asyncio.sleep(wait_time)
                return await self._request(method, path, params, json, retry_count + 1)
            raise
            
        except (AuthenticationError, AuthorizationError):
            # Don't retry auth errors
            raise
            
        except httpx.HTTPStatusError as e:
            # Don't retry client errors (4xx) - these are validation/permission errors
            if 400 <= e.response.status_code < 500:
                logger.warning(f"Client error {e.response.status_code} - not retrying")
                raise
            
            # For 5xx errors, retry
            if e.response.status_code >= 500 and retry_count < self.max_retries:
                wait_time = 2 ** retry_count
                logger.info(f"Server error, retrying in {wait_time}s (attempt {retry_count + 1}/{self.max_retries})")
                await asyncio.sleep(wait_time)
                return await self._request(method, path, params, json, retry_count + 1)
            raise
            
    async def execute_sql(
        self,
        sql: str,
        maximum_bytes_billed: int = 1000000000,
        use_cache: bool = True,
    ) -> QueryResult:
        """Execute a read-only SQL query on BigQuery.
        
        Args:
            sql: SQL query to execute
            maximum_bytes_billed: Maximum bytes to bill (default: 1GB)
            use_cache: Whether to use query result caching
            
        Returns:
            QueryResult with rows and statistics
            
        Raises:
            AuthenticationError: If authentication fails
            AuthorizationError: If user lacks required permissions
        """
        response = await self._request(
            "POST",
            "/tools/query",
            json={
                "sql": sql,
                "maximum_bytes_billed": maximum_bytes_billed,
                "use_cache": use_cache,
            },
        )
        
        # Handle both MCP-style and direct responses
        if "content" in response:
            # MCP-style response
            content = response["content"][0]["text"]
            import json
            data = json.loads(content)
            return QueryResult(
                query_id=data.get("query_id"),
                rows=data.get("result", []),
                statistics=data.get("statistics"),
                cached=data.get("cached", False),
                cached_at=data.get("cached_at"),
            )
        elif "result" in response:
            # Direct response
            return QueryResult(
                rows=response.get("result", []),
                statistics=response.get("statistics"),
            )
        elif "error" in response:
            # Error response
            return QueryResult(error=response["error"], rows=[])
        else:
            # Assume the response is the result
            return QueryResult(rows=response if isinstance(response, list) else [])
            
    async def get_datasets(self) -> List[DatasetInfo]:
        """Retrieve all datasets the user has access to.
        
        Returns:
            List of DatasetInfo objects
            
        Raises:
            AuthenticationError: If authentication fails
            AuthorizationError: If user lacks required permissions
        """
        response = await self._request("GET", "/tools/datasets")
        
        # Handle MCP-style response
        if "content" in response:
            content = response["content"][0]["text"]
            import json
            data = json.loads(content)
            datasets = data.get("datasets", [])
        else:
            datasets = response.get("datasets", [])
            
        return [
            DatasetInfo(
                dataset_id=ds.get("datasetId") or ds.get("dataset_id", ""),
                project_id=ds.get("projectId") or ds.get("project_id"),
                location=ds.get("location"),
                description=ds.get("description"),
                created=self._parse_datetime(ds.get("created")),
                modified=self._parse_datetime(ds.get("modified")),
            )
            for ds in datasets
        ]
    
    async def list_datasets(self) -> List[DatasetInfo]:
        """Alias for get_datasets() for compatibility with tool registry.
        
        Returns:
            List of DatasetInfo objects
        """
        return await self.get_datasets()
        
    async def get_tables(self, dataset_id: str) -> List[TableInfo]:
        """Get all tables in a dataset.
        
        Args:
            dataset_id: Dataset identifier
            
        Returns:
            List of TableInfo objects
            
        Raises:
            AuthenticationError: If authentication fails
            AuthorizationError: If user lacks required permissions
        """
        response = await self._request("GET", "/tools/tables", params={"dataset_id": dataset_id})
        
        # Handle MCP-style response
        if "content" in response:
            content = response["content"][0]["text"]
            import json
            data = json.loads(content)
            tables = data.get("tables", [])
        else:
            tables = response.get("tables", [])
            
        return [
            TableInfo(
                table_id=tbl.get("tableId") or tbl.get("table_id", ""),
                dataset_id=dataset_id,
                project_id=tbl.get("projectId") or tbl.get("project_id"),
                table_type=tbl.get("type") or tbl.get("table_type"),
                num_rows=tbl.get("numRows") or tbl.get("num_rows"),
                num_bytes=tbl.get("numBytes") or tbl.get("num_bytes"),
                created=self._parse_datetime(tbl.get("created")),
                modified=self._parse_datetime(tbl.get("modified")),
                description=tbl.get("description"),
            )
            for tbl in tables
        ]
    
    async def list_tables(self, dataset_id: str) -> List[TableInfo]:
        """Alias for get_tables() for compatibility with tool registry.
        
        Args:
            dataset_id: Dataset identifier
            
        Returns:
            List of TableInfo objects
        """
        return await self.get_tables(dataset_id)
        
    async def get_table_schema(
        self,
        dataset_id: str,
        table_id: str,
        include_samples: bool = True,
    ) -> TableSchema:
        """Get schema information for a table.
        
        Args:
            dataset_id: Dataset identifier
            table_id: Table identifier
            include_samples: Whether to include sample rows
            
        Returns:
            TableSchema with field definitions and optional samples
            
        Raises:
            AuthenticationError: If authentication fails
            AuthorizationError: If user lacks required permissions
        """
        response = await self._request(
            "GET",
            "/tools/table_schema",
            params={
                "dataset_id": dataset_id,
                "table_id": table_id,
                "include_samples": include_samples,
            },
        )
        
        # Handle MCP-style response
        if "content" in response:
            content = response["content"][0]["text"]
            import json
            data = json.loads(content)
        else:
            data = response
            
        return TableSchema(
            table_id=table_id,
            dataset_id=dataset_id,
            project_id=data.get("projectId") or data.get("project_id"),
            schema_fields=data.get("schema", []),
            num_rows=data.get("numRows") or data.get("num_rows"),
            num_bytes=data.get("numBytes") or data.get("num_bytes"),
            description=data.get("description"),
            sample_rows=data.get("sampleRows", []) or data.get("sample_rows", []),
        )
        
    async def health_check(self) -> HealthStatus:
        """Check server health status.
        
        Returns:
            HealthStatus with server status information
        """
        response = await self._request("GET", "/health")
        return HealthStatus(**response)
        
    async def explain_table(
        self,
        project_id: str,
        dataset_id: str,
        table_id: str,
        include_usage_stats: bool = True,
    ) -> Dict[str, Any]:
        """Get detailed explanation and metadata for a table.
        
        Args:
            project_id: Project identifier
            dataset_id: Dataset identifier
            table_id: Table identifier
            include_usage_stats: Whether to include usage statistics
            
        Returns:
            Dict with table explanation and metadata
        """
        response = await self._request(
            "POST",
            "/tools/explain_table",
            json={
                "project_id": project_id,
                "dataset_id": dataset_id,
                "table_id": table_id,
                "include_usage_stats": include_usage_stats,
            },
        )
        
        # Handle MCP-style response
        if "content" in response:
            content = response["content"][0]["text"]
            import json
            return json.loads(content)
        return response
        
    async def analyze_query_performance(
        self,
        sql: str,
        tables_accessed: Optional[List[str]] = None,
        time_range_hours: int = 168,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Analyze query performance and get optimization suggestions.
        
        Args:
            sql: SQL query to analyze
            tables_accessed: Optional list of tables accessed by query
            time_range_hours: Time range for historical analysis (default: 7 days)
            user_id: Optional user ID for user-specific analysis
            
        Returns:
            Dict with performance analysis and recommendations
        """
        response = await self._request(
            "POST",
            "/tools/analyze_query_performance",
            json={
                "sql": sql,
                "tables_accessed": tables_accessed,
                "time_range_hours": time_range_hours,
                "user_id": user_id,
            },
        )
        
        # Handle MCP-style response
        if "content" in response:
            content = response["content"][0]["text"]
            import json
            return json.loads(content)
        return response
        
    async def manage_cache(
        self,
        action: str,
        target: Optional[str] = None,
        project_id: Optional[str] = None,
        dataset_id: Optional[str] = None,
        table_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Manage query result cache.
        
        Args:
            action: Cache action (e.g., "clear", "stats")
            target: Cache target (e.g., "all", "table", "query")
            project_id: Optional project ID for scoped operations
            dataset_id: Optional dataset ID for scoped operations
            table_id: Optional table ID for scoped operations
            
        Returns:
            Dict with cache operation result
        """
        response = await self._request(
            "POST",
            "/tools/manage_cache",
            json={
                "action": action,
                "target": target,
                "project_id": project_id,
                "dataset_id": dataset_id,
                "table_id": table_id,
            },
        )
        
        # Handle MCP-style response
        if "content" in response:
            content = response["content"][0]["text"]
            import json
            return json.loads(content)
        return response
        
    async def get_query_suggestions(
        self,
        tables_mentioned: Optional[List[str]] = None,
        query_context: Optional[str] = None,
        limit: int = 5,
    ) -> Dict[str, Any]:
        """Get query suggestions based on context and tables.
        
        Args:
            tables_mentioned: Optional list of tables for context
            query_context: Optional text context for suggestions
            limit: Maximum number of suggestions to return
            
        Returns:
            Dict with query suggestions
        """
        response = await self._request(
            "POST",
            "/tools/query_suggestions",
            json={
                "tables_mentioned": tables_mentioned,
                "query_context": query_context,
                "limit": limit,
            },
        )
        
        # Handle MCP-style response
        if "content" in response:
            content = response["content"][0]["text"]
            import json
            return json.loads(content)
        return response
        
    @staticmethod
    def _parse_datetime(value: Any) -> Optional[datetime]:
        """Parse datetime from various formats.
        
        Args:
            value: Datetime value as string, int, or datetime
            
        Returns:
            Parsed datetime or None
        """
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                return None
        if isinstance(value, (int, float)):
            try:
                return datetime.fromtimestamp(value, tz=timezone.utc)
            except (ValueError, OSError):
                return None
        return None
