"""MCP application setup and resource/tool registration with enhanced Supabase integration."""
import logging
from datetime import datetime
from fastmcp import FastMCP
from typing import Optional, List, Dict, Any
from ..handlers.resources import list_resources_handler, read_resource_handler
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
from ..core.supabase_client import SupabaseKnowledgeBase
from postgrest.exceptions import APIError

logger = logging.getLogger(__name__)

def create_mcp_app(bigquery_client, config, event_manager) -> FastMCP:
    mcp_app = FastMCP(
        name="mcp-bigquery-server",
        version="0.2.0",
        description="A FastMCP server for securely accessing BigQuery datasets with intelligent caching, schema evolution tracking, and query analytics via Supabase.",
    )

    # Initialize knowledge base
    knowledge_base = None
    try:
        knowledge_base = SupabaseKnowledgeBase(
            supabase_url=getattr(config, 'SUPABASE_URL', None),
            supabase_key=getattr(config, 'SUPABASE_ANON_KEY', None),
        )
    except Exception as e:
        logger.warning(f"Failed to initialize Supabase knowledge base: {e}")

    _supabase_verified = {"status": False}

    async def ensure_supabase_connection():
        """Ensure Supabase connection is available and verified."""
        if not knowledge_base:
            return False
            
        if not _supabase_verified["status"]:
            try:
                is_connected = await knowledge_base.verify_connection()
                _supabase_verified["status"] = bool(is_connected)
                if is_connected:
                    logger.info("Supabase connection verified")
                else:
                    logger.warning("Supabase connection verification failed")
            except Exception as e:
                logger.error(f"Supabase initialization error: {e}")
                _supabase_verified["status"] = False
        return _supabase_verified["status"]

    async def log_supabase_event(event_type: str, event_data: Dict[str, Any], user_id: Optional[str] = None):
        """Log events to Supabase with proper error handling."""
        if not await ensure_supabase_connection():
            return

        # Type guard for Pylance
        if knowledge_base is None:
            logger.debug("Supabase knowledge base is not initialized; skipping event log.")
            return

        try:
            # Prepare event data
            log_entry = {
                "event_type": event_type,
                "event_data": event_data,
                "created_at": datetime.now().isoformat(),
            }

            # Add user_id if provided
            if user_id:
                log_entry["user_id"] = user_id

            # Insert event log (no await)
            knowledge_base.supabase.table("event_log").insert(log_entry).execute()

        except APIError as e:
            logger.debug(f"Failed to log {event_type} (API Error): {e}")
            if hasattr(e, 'details') and e.details:
                logger.debug(f"API Error details: {e.details}")
        except Exception as e:
            logger.debug(f"Failed to log {event_type}: {e}")

    @mcp_app.resource("resources://list")
    async def list_resources_mcp() -> dict:
        try:
            result = await list_resources_handler(bigquery_client, config)
            if isinstance(result, tuple):
                result, _ = result
            
            # Log event
            await log_supabase_event(
                "resource_list",
                {"resource_count": len(result.get("resources", []))},
                getattr(config, 'DEFAULT_USER_ID', None)
            )
            return result
        except Exception as e:
            logger.error(f"Error listing resources: {e}")
            await log_supabase_event(
                "resource_list_failed",
                {"error": str(e)},
                getattr(config, 'DEFAULT_USER_ID', None)
            )
            raise

    @mcp_app.resource("bigquery://{project_id}/{dataset_id}/{table_id}")
    async def read_resource_mcp(
        project_id: str, dataset_id: str, table_id: str
    ) -> dict:
        try:
            result = await read_resource_handler(
                bigquery_client, config, project_id, dataset_id, table_id
            )
            if isinstance(result, tuple):
                result, _ = result
            
            # Log event
            await log_supabase_event(
                "resource_read",
                {
                    "project_id": project_id,
                    "dataset_id": dataset_id,
                    "table_id": table_id,
                },
                getattr(config, 'DEFAULT_USER_ID', None)
            )
            return result
        except Exception as e:
            logger.error(f"Error reading resource {project_id}.{dataset_id}.{table_id}: {e}")
            await log_supabase_event(
                "resource_read_failed",
                {
                    "project_id": project_id,
                    "dataset_id": dataset_id,
                    "table_id": table_id,
                    "error": str(e)
                },
                getattr(config, 'DEFAULT_USER_ID', None)
            )
            raise

    @mcp_app.tool(
        name="execute_bigquery_sql", 
        description="Execute a read-only SQL query on BigQuery with intelligent caching, performance tracking, and automatic schema detection."
    )
    async def execute_bigquery_sql(
        sql: str, 
        maximum_bytes_billed: int = 314572800,
        use_cache: bool = True,
        user_id: Optional[str] = None,
        force_refresh: bool = False
    ) -> dict:
        effective_user_id = user_id or getattr(config, 'DEFAULT_USER_ID', None)
        effective_use_cache = use_cache and not force_refresh
        supabase_available = await ensure_supabase_connection()
        
        try:
            result = await query_tool_handler(
                bigquery_client=bigquery_client,
                event_manager=event_manager,
                sql=sql,
                maximum_bytes_billed=maximum_bytes_billed,
                knowledge_base=knowledge_base if supabase_available else None,
                use_cache=effective_use_cache and supabase_available,
                user_id=effective_user_id
            )
            if isinstance(result, tuple):
                result, _ = result
            
            # Log successful execution
            await log_supabase_event(
                "query_execution",
                {
                    "sql": sql[:200] + "..." if len(sql) > 200 else sql,  # Truncate long SQL
                    "maximum_bytes_billed": maximum_bytes_billed,
                    "use_cache": effective_use_cache,
                    "force_refresh": force_refresh,
                    "rows_returned": len(result.get("rows", [])) if result.get("rows") else 0,
                    "cached": result.get("cached", False)
                },
                effective_user_id
            )
            return result
        except Exception as e:
            logger.error(f"Error executing BigQuery SQL: {e}")
            await log_supabase_event(
                "query_execution_failed",
                {
                    "sql": sql[:200] + "..." if len(sql) > 200 else sql,
                    "error": str(e)
                },
                effective_user_id
            )
            raise

    @mcp_app.tool(
        name="get_datasets",
        description="Retrieve the list of all datasets in the current project with metadata."
    )
    async def get_datasets() -> dict:
        try:
            result = await get_datasets_handler(bigquery_client)
            if isinstance(result, tuple):
                result, _ = result
            
            await log_supabase_event(
                "datasets_list",
                {"dataset_count": len(result.get("datasets", []))},
                getattr(config, 'DEFAULT_USER_ID', None)
            )
            return result
        except Exception as e:
            logger.error(f"Error getting datasets: {e}")
            await log_supabase_event(
                "datasets_list_failed",
                {"error": str(e)},
                getattr(config, 'DEFAULT_USER_ID', None)
            )
            raise

    @mcp_app.tool(
        name="get_tables", 
        description="Retrieve all tables within a specific dataset with metadata and documentation."
    )
    async def get_tables(dataset_id: str) -> dict:
        try:
            result = await get_tables_handler(bigquery_client, dataset_id)
            if isinstance(result, tuple):
                result, _ = result
            
            # Enhance with column documentation if Supabase is available
            if await ensure_supabase_connection() and result and "tables" in result:
                project_id = getattr(config, 'PROJECT_ID', 'unknown')
                for table in result["tables"]:
                    docs = None  # Ensure docs is always defined
                    try:
                        if knowledge_base is not None:
                            docs = await knowledge_base.get_column_documentation(
                                project_id=project_id,
                                dataset_id=dataset_id,
                                table_id=table.get("table_id")
                            )
                    except Exception as e:
                        logger.debug(f"Failed to get column documentation for {table.get('table_id')}: {e}")
                    if docs:
                        table["column_documentation"] = docs
            
            await log_supabase_event(
                "tables_list",
                {"dataset_id": dataset_id, "table_count": len(result.get("tables", []))},
                getattr(config, 'DEFAULT_USER_ID', None)
            )
            return result
        except Exception as e:
            logger.error(f"Error getting tables for dataset {dataset_id}: {e}")
            await log_supabase_event(
                "tables_list_failed",
                {"dataset_id": dataset_id, "error": str(e)},
                getattr(config, 'DEFAULT_USER_ID', None)
            )
            raise

    @mcp_app.tool(
        name="get_table_schema",
        description="Retrieve comprehensive schema details for a specific table including column documentation and data quality insights."
    )
    async def get_table_schema(
        dataset_id: str, 
        table_id: str,
        include_samples: bool = True,
        include_documentation: bool = True
    ) -> dict:
        try:
            result = await get_table_schema_handler(bigquery_client, dataset_id, table_id)
            if isinstance(result, tuple):
                result, _ = result
            
            # Add documentation if requested and available
            docs = None  # Ensure docs is always defined
            if include_documentation and result and await ensure_supabase_connection():
                project_id = getattr(config, 'PROJECT_ID', 'unknown')
                try:
                    if knowledge_base is not None:
                        docs = await knowledge_base.get_column_documentation(
                            project_id=project_id,
                            dataset_id=dataset_id,
                            table_id=table_id
                        )
                except Exception as e:
                    logger.debug(f"Failed to get column documentation: {e}")
                if docs:
                    result["column_documentation"] = docs
            
            await log_supabase_event(
                "schema_access",
                {
                    "dataset_id": dataset_id,
                    "table_id": table_id,
                    "include_samples": include_samples,
                    "include_documentation": include_documentation,
                },
                getattr(config, 'DEFAULT_USER_ID', None)
            )
            return result
        except Exception as e:
            logger.error(f"Error getting schema for {dataset_id}.{table_id}: {e}")
            await log_supabase_event(
                "schema_access_failed",
                {"dataset_id": dataset_id, "table_id": table_id, "error": str(e)},
                getattr(config, 'DEFAULT_USER_ID', None)
            )
            raise

    @mcp_app.tool(
        name="get_query_suggestions",
        description="Get AI-powered query recommendations based on table schemas, usage patterns, and business context."
    )
    async def get_query_suggestions(
        tables_mentioned: Optional[List[str]] = None,
        query_context: Optional[str] = None,
        limit: int = 5,
        user_id: Optional[str] = None
    ) -> dict:
        effective_user_id = user_id or getattr(config, 'DEFAULT_USER_ID', None)
        supabase_available = await ensure_supabase_connection()
        if not (await ensure_supabase_connection() and knowledge_base is not None):
            return {"error": "Supabase knowledge base unavailable"}
        try:
            result = await get_query_suggestions_handler(
                bigquery_client=bigquery_client,
                knowledge_base=knowledge_base,
                tables_mentioned=tables_mentioned,
                query_context=query_context,
                limit=limit
            )
            if isinstance(result, tuple):
                result, _ = result

            await log_supabase_event(
                "query_suggestions",
                {
                    "tables_mentioned": tables_mentioned,
                    "context_provided": bool(query_context),
                    "suggestions_count": len(result.get("suggestions", [])),
                },
                effective_user_id
            )
            return result
        except Exception as e:
            logger.error(f"Error getting query suggestions: {e}")
            await log_supabase_event(
                "query_suggestions_failed",
                {"error": str(e)},
                effective_user_id
            )
            raise

    @mcp_app.tool(
        name="explain_table",
        description="Get comprehensive table documentation including schema, business context, usage patterns, and data quality insights."
    )
    async def explain_table(
        project_id: str,
        dataset_id: str,
        table_id: str,
        include_usage_stats: bool = True,
        user_id: Optional[str] = None
    ) -> dict:
        effective_user_id = user_id or getattr(config, 'DEFAULT_USER_ID', None)

        supabase_available = await ensure_supabase_connection()
        if not (supabase_available and knowledge_base is not None):
            return {"error": "Supabase knowledge base unavailable"}

        try:
            result = await explain_table_handler(
                bigquery_client=bigquery_client,
                knowledge_base=knowledge_base,
                project_id=project_id,
                dataset_id=dataset_id,
                table_id=table_id
            )
            if isinstance(result, tuple):
                result, _ = result

            await log_supabase_event(
                "table_explanation",
                {
                    "project_id": project_id,
                    "dataset_id": dataset_id,
                    "table_id": table_id,
                    "include_usage_stats": include_usage_stats,
                },
                effective_user_id
            )
            return result
        except Exception as e:
            logger.error(f"Error explaining table {project_id}.{dataset_id}.{table_id}: {e}")
            await log_supabase_event(
                "table_explanation_failed",
                {"project_id": project_id, "dataset_id": dataset_id, "table_id": table_id, "error": str(e)},
                effective_user_id
            )
            raise

    @mcp_app.tool(
        name="analyze_query_performance",
        description="Analyze historical query performance patterns and provide optimization recommendations with cost insights."
    )
    async def analyze_query_performance(
        sql: Optional[str] = None,
        tables_accessed: Optional[List[str]] = None,
        time_range_hours: int = 168,
        user_id: Optional[str] = None,
        include_recommendations: bool = True
    ) -> dict:
        effective_user_id = user_id or getattr(config, 'DEFAULT_USER_ID', None)
        
        supabase_available = await ensure_supabase_connection()
        if not (supabase_available and knowledge_base is not None):
            return {"error": "Supabase knowledge base unavailable"}

        try:
            result = await analyze_query_performance_handler(
                knowledge_base=knowledge_base,
                sql=sql,
                tables_accessed=tables_accessed,
                time_range_hours=time_range_hours,
                user_id=effective_user_id
            )
            if isinstance(result, tuple):
                result, _ = result
            
            await log_supabase_event(
                "performance_analysis",
                {
                    "query_provided": bool(sql),
                    "tables_specified": bool(tables_accessed),
                    "time_range_hours": time_range_hours,
                    "include_recommendations": include_recommendations,
                },
                effective_user_id
            )
            return result
        except Exception as e:
            logger.error(f"Error analyzing query performance: {e}")
            await log_supabase_event(
                "performance_analysis_failed",
                {"error": str(e)},
                effective_user_id
            )
            raise

    @mcp_app.tool(
        name="get_schema_changes",
        description="Track schema evolution and changes over time for specific tables with impact analysis."
    )
    async def get_schema_changes(
        project_id: str,
        dataset_id: str,
        table_id: str,
        limit: int = 10,
        include_impact_analysis: bool = True,
        user_id: Optional[str] = None
    ) -> dict:
        effective_user_id = user_id or getattr(config, 'DEFAULT_USER_ID', None)
        
        try:
            assert knowledge_base is not None
            result = await get_schema_changes_handler(
                knowledge_base=knowledge_base,
                project_id=project_id,
                dataset_id=dataset_id,
                table_id=table_id,
                limit=limit
            )
            if isinstance(result, tuple):
                result, _ = result
            
            await log_supabase_event(
                "schema_changes",
                {
                    "project_id": project_id,
                    "dataset_id": dataset_id,
                    "table_id": table_id,
                    "limit": limit,
                    "include_impact_analysis": include_impact_analysis,
                },
                effective_user_id
            )
            return result
        except Exception as e:
            logger.error(f"Error getting schema changes: {e}")
            await log_supabase_event(
                "schema_changes_failed",
                {"project_id": project_id, "dataset_id": dataset_id, "table_id": table_id, "error": str(e)},
                effective_user_id
            )
            raise

    @mcp_app.tool(
        name="manage_cache",
        description="Comprehensive cache management operations including statistics, cleanup, and targeted invalidation."
    )
    async def manage_cache(
        action: str,
        target: Optional[str] = None,
        project_id: Optional[str] = None,
        dataset_id: Optional[str] = None,
        table_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> dict:
        effective_user_id = user_id or getattr(config, 'DEFAULT_USER_ID', None)

        supabase_available = await ensure_supabase_connection()
        if not (supabase_available and knowledge_base is not None):
            return {"error": "Supabase knowledge base unavailable"}

        try:
            result = await cache_management_handler(
                knowledge_base=knowledge_base,
                action=action,
                target=target,
                project_id=project_id,
                dataset_id=dataset_id,
                table_id=table_id
            )
            if isinstance(result, tuple):
                result, _ = result

            await log_supabase_event(
                "cache_management",
                {
                    "action": action,
                    "target": target,
                    "project_id": project_id,
                    "dataset_id": dataset_id,
                    "table_id": table_id,
                },
                effective_user_id
            )
            return result
        except Exception as e:
            logger.error(f"Error managing cache: {e}")
            await log_supabase_event(
                "cache_management_failed",
                {"action": action, "error": str(e)},
                effective_user_id
            )
            raise

    @mcp_app.tool(
        name="health_check",
        description="Comprehensive system health check including BigQuery, Supabase, and cache status."
    )
    async def health_check(user_id: Optional[str] = None) -> dict:
        effective_user_id = user_id or getattr(config, 'DEFAULT_USER_ID', None)
        
        try:
            supabase_ok = await ensure_supabase_connection()
            
            # Basic BigQuery health check
            bigquery_ok = True
            try:
                # Simple test query to verify BigQuery connectivity
                test_query = "SELECT 1 as test_value"
                job_config = bigquery_client.QueryJobConfig(dry_run=True, use_query_cache=False)
                bigquery_client.query(test_query, job_config=job_config)
            except Exception as e:
                logger.warning(f"BigQuery health check failed: {e}")
                bigquery_ok = False
            
            # Get cache stats if Supabase is available
            cache_stats = {}
            if supabase_ok:
                try:
                    if knowledge_base is not None:
                        cache_stats = await knowledge_base.get_cache_stats()
                except Exception as e:
                    logger.debug(f"Failed to get cache stats: {e}")
            
            health = {
                "bigquery_status": "ok" if bigquery_ok else "error",
                "supabase_status": "ok" if supabase_ok else "unavailable",
                "cache_status": "ok" if supabase_ok else "unavailable",
                "cache_stats": cache_stats,
                "timestamp": datetime.now().isoformat(),
            }
            
            await log_supabase_event(
                "health_check",
                health,
                effective_user_id
            )
            return health
        except Exception as e:
            logger.error(f"Error during health check: {e}")
            await log_supabase_event(
                "health_check_failed",
                {"error": str(e)},
                effective_user_id
            )
            raise

    @mcp_app.tool(
        name="get_user_preferences",
        description="Get user preferences from Supabase. If user_id is not provided, uses 'anonymous' or session id."
    )
    async def get_user_preferences(user_id: Optional[str] = None, session_id: Optional[str] = None) -> dict:
        effective_user_id = user_id or session_id or "anonymous"
        if not await ensure_supabase_connection():
            return {"error": "Supabase unavailable"}
        try:
            assert knowledge_base is not None
            prefs = await knowledge_base.get_user_preferences(effective_user_id)
            return {"user_id": effective_user_id, "preferences": prefs}
        except Exception as e:
            logger.error(f"Error getting user preferences: {e}")
            return {"error": str(e)}

    @mcp_app.tool(
        name="set_user_preferences",
        description="Set or update user preferences in Supabase. If user_id is not provided, uses 'anonymous' or session id."
    )
    async def set_user_preferences(preferences: dict, user_id: Optional[str] = None, session_id: Optional[str] = None) -> dict:
        effective_user_id = user_id or session_id or "anonymous"
        if not await ensure_supabase_connection():
            return {"error": "Supabase unavailable"}
        try:
            assert knowledge_base is not None
            ok = await knowledge_base.set_user_preferences(effective_user_id, preferences)
            return {"user_id": effective_user_id, "success": ok}
        except Exception as e:
            logger.error(f"Error setting user preferences: {e}")
            return {"error": str(e)}

    return mcp_app