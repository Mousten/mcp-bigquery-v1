"""FastAPI routes for tool operations."""
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Body, Query
from fastapi.responses import JSONResponse
from ..handlers.tools import (
    query_tool_handler,
    get_datasets_handler,
    get_tables_handler,
    get_table_schema_handler,
    get_query_suggestions_handler,
    explain_table_handler,
    analyze_query_performance_handler,
    get_schema_changes_handler,
    cache_management_handler,
)


def create_tools_router(bigquery_client, event_manager, knowledge_base) -> APIRouter:
    """Create router for tool-related endpoints."""
    router = APIRouter(prefix="/tools", tags=["tools"])

    @router.post("/query")
    async def query_tool_fastapi(payload: Dict[str, Any] = Body(...)):
        """Execute a read-only SQL query on BigQuery."""
        sql = payload.get("sql", "")
        maximum_bytes_billed = payload.get("maximum_bytes_billed", 1000000000)
        use_cache = payload.get("use_cache", True)
        user_id = payload.get("user_id")
        result = await query_tool_handler(
            bigquery_client, event_manager, sql, maximum_bytes_billed,
            knowledge_base, use_cache, user_id
        )
        if isinstance(result, tuple) and len(result) == 2:
            return JSONResponse(content=result[0], status_code=result[1])
        return result

    @router.post("/execute_bigquery_sql")
    async def execute_bigquery_sql_fastapi(payload: Dict[str, Any] = Body(...)):
        sql = payload.get("sql", "")
        maximum_bytes_billed = payload.get("maximum_bytes_billed", 1000000000)
        use_cache = payload.get("use_cache", True)
        user_id = payload.get("user_id")
        result = await query_tool_handler(
            bigquery_client, event_manager, sql, maximum_bytes_billed,
            knowledge_base, use_cache, user_id
        )
        if isinstance(result, tuple) and len(result) == 2:
            return JSONResponse(content=result[0], status_code=result[1])
        return result

    @router.get("/datasets")
    async def get_datasets_fastapi():
        """Retrieve all datasets."""
        result = await get_datasets_handler(bigquery_client)
        if isinstance(result, tuple) and len(result) == 2:
            return JSONResponse(content=result[0], status_code=result[1])
        return result

    @router.get("/tables")
    async def get_tables_fastapi(dataset_id: str = Query(..., description="Dataset ID")):
        result = await get_tables_handler(bigquery_client, dataset_id)
        if isinstance(result, tuple) and len(result) == 2:
            return JSONResponse(content=result[0], status_code=result[1])
        return result

    @router.post("/get_tables")
    async def get_tables_post_fastapi(payload: Dict[str, Any] = Body(...)):
        """Get tables in a dataset (POST version for MCPTools compatibility)."""
        dataset_id = payload.get("dataset_id")
        if not dataset_id:
            return JSONResponse(content={"error": "dataset_id is required"}, status_code=400)
        result = await get_tables_handler(bigquery_client, dataset_id)
        if isinstance(result, tuple) and len(result) == 2:
            return JSONResponse(content=result[0], status_code=result[1])
        return result

    @router.get("/table_schema")
    async def get_table_schema_fastapi(
        dataset_id: str = Query(...), table_id: str = Query(...), include_samples: bool = Query(True)
    ):
        result = await get_table_schema_handler(bigquery_client, dataset_id, table_id)
        if isinstance(result, tuple) and len(result) == 2:
            return JSONResponse(content=result[0], status_code=result[1])
        return result

    @router.post("/get_table_schema")
    async def get_table_schema_post_fastapi(payload: Dict[str, Any] = Body(...)):
        """Get table schema (POST version for MCPTools compatibility)."""
        dataset_id = payload.get("dataset_id")
        table_id = payload.get("table_id")
        if not dataset_id or not table_id:
            return JSONResponse(
                content={"error": "dataset_id and table_id are required"},
                status_code=400
            )
        result = await get_table_schema_handler(bigquery_client, dataset_id, table_id)
        if isinstance(result, tuple) and len(result) == 2:
            return JSONResponse(content=result[0], status_code=result[1])
        return result

    @router.post("/query_suggestions")
    async def query_suggestions_fastapi(payload: Dict[str, Any] = Body(...)):
        tables_mentioned = payload.get("tables_mentioned")
        query_context = payload.get("query_context")
        limit = payload.get("limit", 5)
        result = await get_query_suggestions_handler(
            bigquery_client=bigquery_client,
            knowledge_base=knowledge_base,
            tables_mentioned=tables_mentioned,
            query_context=query_context,
            limit=limit,
        )
        if isinstance(result, tuple) and len(result) == 2:
            return JSONResponse(content=result[0], status_code=result[1])
        return result

    @router.post("/explain_table")
    async def explain_table_fastapi(payload: Dict[str, Any] = Body(...)):
        project_id = payload.get("project_id")
        dataset_id = payload.get("dataset_id")
        table_id = payload.get("table_id")
        include_usage_stats = payload.get("include_usage_stats", True)
        result = await explain_table_handler(
            bigquery_client, knowledge_base, project_id, dataset_id, table_id
        )
        if isinstance(result, tuple) and len(result) == 2:
            return JSONResponse(content=result[0], status_code=result[1])
        return result

    @router.post("/analyze_query_performance")
    async def analyze_query_performance_fastapi(payload: Dict[str, Any] = Body(...)):
        sql = payload.get("sql")
        tables_accessed = payload.get("tables_accessed")
        time_range_hours = payload.get("time_range_hours", 168)
        user_id = payload.get("user_id")
        result = await analyze_query_performance_handler(
            knowledge_base=knowledge_base,
            sql=sql,
            tables_accessed=tables_accessed,
            time_range_hours=time_range_hours,
            user_id=user_id,
        )
        if isinstance(result, tuple) and len(result) == 2:
            return JSONResponse(content=result[0], status_code=result[1])
        return result

    @router.get("/schema_changes")
    async def get_schema_changes_fastapi(
        project_id: str = Query(...), dataset_id: str = Query(...), table_id: str = Query(...), limit: int = Query(10)
    ):
        result = await get_schema_changes_handler(
            knowledge_base=knowledge_base, project_id=project_id, dataset_id=dataset_id, table_id=table_id, limit=limit
        )
        if isinstance(result, tuple) and len(result) == 2:
            return JSONResponse(content=result[0], status_code=result[1])
        return result

    @router.post("/manage_cache")
    async def manage_cache_fastapi(payload: Dict[str, Any] = Body(...)):
        action = payload.get("action")
        target = payload.get("target")
        project_id = payload.get("project_id")
        dataset_id = payload.get("dataset_id")
        table_id = payload.get("table_id")
        result = await cache_management_handler(
            knowledge_base=knowledge_base, action=action, target=target, project_id=project_id, dataset_id=dataset_id, table_id=table_id
        )
        if isinstance(result, tuple) and len(result) == 2:
            return JSONResponse(content=result[0], status_code=result[1])
        return result

    return router