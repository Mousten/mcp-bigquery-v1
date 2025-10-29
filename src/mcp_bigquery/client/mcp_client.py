"""MCP BigQuery client for interacting with the MCP BigQuery server."""

import asyncio
import json
from typing import Dict, Any, List, Optional, AsyncIterator
import httpx

from .config import ClientConfig
from .exceptions import (
    AuthenticationError,
    AuthorizationError,
    ValidationError,
    ServerError,
    NetworkError,
)


class MCPClient:
    """Async client for interacting with the MCP BigQuery server.
    
    This client provides a high-level interface to the MCP BigQuery server's
    REST API, handling authentication, retries, and error handling.
    
    Example:
        ```python
        from mcp_bigquery.client import MCPClient, ClientConfig
        
        config = ClientConfig(
            base_url="http://localhost:8000",
            auth_token="your-jwt-token"
        )
        
        async with MCPClient(config) as client:
            datasets = await client.list_datasets()
            result = await client.execute_sql("SELECT 1")
        ```
    """
    
    def __init__(self, config: ClientConfig):
        """Initialize the MCP client.
        
        Args:
            config: Client configuration
        """
        self.config = config
        self._client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self) -> "MCPClient":
        """Async context manager entry."""
        await self._ensure_client()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def _ensure_client(self):
        """Ensure HTTP client is initialized."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.config.timeout,
                verify=self.config.verify_ssl,
                headers=self._get_headers()
            )
    
    async def close(self):
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
    
    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers including authentication."""
        headers = {
            "Content-Type": "application/json",
        }
        
        if self.config.auth_token:
            headers["Authorization"] = f"Bearer {self.config.auth_token}"
        
        return headers
    
    async def _make_request(
        self,
        method: str,
        path: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        retry_count: int = 0
    ) -> Dict[str, Any]:
        """Make an HTTP request with retry logic.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path (e.g., "/tools/datasets")
            json_data: Optional JSON body for POST requests
            params: Optional query parameters
            retry_count: Current retry attempt
            
        Returns:
            Response JSON
            
        Raises:
            AuthenticationError: On 401 responses
            AuthorizationError: On 403 responses
            ValidationError: On 400 responses
            ServerError: On 500+ responses
            NetworkError: On network failures
        """
        await self._ensure_client()
        
        url = f"{self.config.base_url}{path}"
        
        try:
            response = await self._client.request(
                method=method,
                url=url,
                json=json_data,
                params=params
            )
            
            # Handle HTTP error responses
            if response.status_code == 401:
                error_detail = self._extract_error(response)
                raise AuthenticationError(
                    f"Authentication failed: {error_detail}"
                )
            elif response.status_code == 403:
                error_detail = self._extract_error(response)
                raise AuthorizationError(
                    f"Authorization failed: {error_detail}"
                )
            elif response.status_code == 400:
                error_detail = self._extract_error(response)
                raise ValidationError(
                    f"Validation failed: {error_detail}"
                )
            elif response.status_code >= 500:
                error_detail = self._extract_error(response)
                
                # Retry on server errors
                if retry_count < self.config.max_retries:
                    delay = self.config.retry_delay * (2 ** retry_count)
                    await asyncio.sleep(delay)
                    return await self._make_request(
                        method, path, json_data, params, retry_count + 1
                    )
                
                raise ServerError(
                    f"Server error (status {response.status_code}): {error_detail}"
                )
            elif response.status_code >= 400:
                error_detail = self._extract_error(response)
                raise ServerError(
                    f"HTTP error {response.status_code}: {error_detail}"
                )
            
            # Parse successful response
            try:
                return response.json()
            except json.JSONDecodeError:
                return {"result": response.text}
        
        except httpx.TimeoutException as e:
            # Retry on timeout
            if retry_count < self.config.max_retries:
                delay = self.config.retry_delay * (2 ** retry_count)
                await asyncio.sleep(delay)
                return await self._make_request(
                    method, path, json_data, params, retry_count + 1
                )
            raise NetworkError(f"Request timeout: {str(e)}")
        
        except httpx.NetworkError as e:
            # Retry on network errors
            if retry_count < self.config.max_retries:
                delay = self.config.retry_delay * (2 ** retry_count)
                await asyncio.sleep(delay)
                return await self._make_request(
                    method, path, json_data, params, retry_count + 1
                )
            raise NetworkError(f"Network error: {str(e)}")
        
        except (AuthenticationError, AuthorizationError, ValidationError) as e:
            # Don't retry auth/validation errors
            raise
    
    def _extract_error(self, response: httpx.Response) -> str:
        """Extract error message from response."""
        try:
            data = response.json()
            if "error" in data:
                return data["error"]
            elif "detail" in data:
                return data["detail"]
            return str(data)
        except Exception:
            return response.text or f"HTTP {response.status_code}"
    
    async def execute_sql(
        self,
        sql: str,
        maximum_bytes_billed: int = 1000000000,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """Execute a SQL query on BigQuery.
        
        Args:
            sql: SQL query to execute
            maximum_bytes_billed: Maximum bytes to bill for the query
            use_cache: Whether to use BigQuery cache
            
        Returns:
            Query result with rows and metadata
            
        Raises:
            AuthenticationError: If authentication fails
            AuthorizationError: If user lacks permissions
            ValidationError: If query is invalid
            ServerError: On server errors
        """
        return await self._make_request(
            method="POST",
            path="/tools/execute_bigquery_sql",
            json_data={
                "sql": sql,
                "maximum_bytes_billed": maximum_bytes_billed,
                "use_cache": use_cache
            }
        )
    
    async def list_datasets(self) -> Dict[str, Any]:
        """List all datasets the user has access to.
        
        Returns:
            Dictionary with datasets list
            
        Raises:
            AuthenticationError: If authentication fails
            AuthorizationError: If user lacks permissions
            ServerError: On server errors
        """
        return await self._make_request(
            method="GET",
            path="/tools/datasets"
        )
    
    async def list_tables(self, dataset_id: str) -> Dict[str, Any]:
        """List tables in a dataset.
        
        Args:
            dataset_id: Dataset identifier
            
        Returns:
            Dictionary with tables list
            
        Raises:
            AuthenticationError: If authentication fails
            AuthorizationError: If user lacks permissions
            ValidationError: If dataset_id is invalid
            ServerError: On server errors
        """
        return await self._make_request(
            method="POST",
            path="/tools/get_tables",
            json_data={"dataset_id": dataset_id}
        )
    
    async def get_table_schema(
        self,
        dataset_id: str,
        table_id: str,
        include_samples: bool = True
    ) -> Dict[str, Any]:
        """Get schema information for a table.
        
        Args:
            dataset_id: Dataset identifier
            table_id: Table identifier
            include_samples: Whether to include sample data
            
        Returns:
            Dictionary with schema information
            
        Raises:
            AuthenticationError: If authentication fails
            AuthorizationError: If user lacks permissions
            ValidationError: If parameters are invalid
            ServerError: On server errors
        """
        return await self._make_request(
            method="POST",
            path="/tools/get_table_schema",
            json_data={
                "dataset_id": dataset_id,
                "table_id": table_id,
                "include_samples": include_samples
            }
        )
    
    async def explain_table(
        self,
        project_id: str,
        dataset_id: str,
        table_id: str,
        include_usage_stats: bool = True
    ) -> Dict[str, Any]:
        """Get detailed explanation of a table with usage statistics.
        
        Args:
            project_id: Google Cloud project ID
            dataset_id: Dataset identifier
            table_id: Table identifier
            include_usage_stats: Whether to include usage statistics
            
        Returns:
            Dictionary with table explanation and stats
            
        Raises:
            AuthenticationError: If authentication fails
            AuthorizationError: If user lacks permissions
            ServerError: On server errors
        """
        return await self._make_request(
            method="POST",
            path="/tools/explain_table",
            json_data={
                "project_id": project_id,
                "dataset_id": dataset_id,
                "table_id": table_id,
                "include_usage_stats": include_usage_stats
            }
        )
    
    async def get_query_suggestions(
        self,
        tables_mentioned: Optional[List[str]] = None,
        query_context: Optional[str] = None,
        limit: int = 5
    ) -> Dict[str, Any]:
        """Get query suggestions based on context.
        
        Args:
            tables_mentioned: List of table names to consider
            query_context: Context description for suggestions
            limit: Maximum number of suggestions to return
            
        Returns:
            Dictionary with query suggestions
            
        Raises:
            ServerError: On server errors
        """
        return await self._make_request(
            method="POST",
            path="/tools/query_suggestions",
            json_data={
                "tables_mentioned": tables_mentioned,
                "query_context": query_context,
                "limit": limit
            }
        )
    
    async def analyze_query_performance(
        self,
        sql: str,
        tables_accessed: Optional[List[str]] = None,
        time_range_hours: int = 168,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze query performance and get recommendations.
        
        Args:
            sql: SQL query to analyze
            tables_accessed: List of tables accessed by the query
            time_range_hours: Time range for historical analysis
            user_id: Optional user ID for filtering
            
        Returns:
            Dictionary with performance analysis
            
        Raises:
            ServerError: On server errors
        """
        return await self._make_request(
            method="POST",
            path="/tools/analyze_query_performance",
            json_data={
                "sql": sql,
                "tables_accessed": tables_accessed,
                "time_range_hours": time_range_hours,
                "user_id": user_id
            }
        )
    
    async def get_schema_changes(
        self,
        project_id: str,
        dataset_id: str,
        table_id: str,
        limit: int = 10
    ) -> Dict[str, Any]:
        """Get schema change history for a table.
        
        Args:
            project_id: Google Cloud project ID
            dataset_id: Dataset identifier
            table_id: Table identifier
            limit: Maximum number of changes to return
            
        Returns:
            Dictionary with schema change history
            
        Raises:
            ServerError: On server errors
        """
        return await self._make_request(
            method="GET",
            path="/tools/schema_changes",
            params={
                "project_id": project_id,
                "dataset_id": dataset_id,
                "table_id": table_id,
                "limit": limit
            }
        )
    
    async def manage_cache(
        self,
        action: str,
        target: Optional[str] = None,
        project_id: Optional[str] = None,
        dataset_id: Optional[str] = None,
        table_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Manage query cache.
        
        Args:
            action: Cache action (e.g., "clear", "get_stats")
            target: Cache target (e.g., "all", "queries", "metadata")
            project_id: Optional project ID for scoped operations
            dataset_id: Optional dataset ID for scoped operations
            table_id: Optional table ID for scoped operations
            
        Returns:
            Dictionary with cache operation result
            
        Raises:
            ServerError: On server errors
        """
        return await self._make_request(
            method="POST",
            path="/tools/manage_cache",
            json_data={
                "action": action,
                "target": target,
                "project_id": project_id,
                "dataset_id": dataset_id,
                "table_id": table_id
            }
        )
    
    async def stream_events(
        self,
        channel: str = "system"
    ) -> AsyncIterator[Dict[str, Any]]:
        """Stream events from the server via NDJSON.
        
        Args:
            channel: Event channel to subscribe to
            
        Yields:
            Event dictionaries as they arrive
            
        Raises:
            AuthenticationError: If authentication fails
            NetworkError: On network failures
        """
        await self._ensure_client()
        
        url = f"{self.config.base_url}/stream/ndjson/"
        
        try:
            async with self._client.stream(
                "GET",
                url,
                params={"channel": channel}
            ) as response:
                if response.status_code == 401:
                    raise AuthenticationError("Authentication failed for streaming")
                elif response.status_code >= 400:
                    raise NetworkError(
                        f"Failed to connect to stream: HTTP {response.status_code}"
                    )
                
                async for line in response.aiter_lines():
                    if not line or line.strip() == "":
                        # Skip empty lines (heartbeats)
                        continue
                    
                    try:
                        event = json.loads(line)
                        yield event
                    except json.JSONDecodeError:
                        # Skip malformed lines
                        continue
        
        except httpx.NetworkError as e:
            raise NetworkError(f"Stream connection error: {str(e)}")
