"""Enhanced tool handlers for BigQuery operations with additional MCP tools."""
import json
import uuid
import re
from typing import Dict, Any, Tuple, Union, List, Optional
from datetime import datetime, timedelta
from google.cloud import bigquery
from google.api_core.exceptions import GoogleAPIError
from ..core.json_encoder import CustomJSONEncoder
from ..core.supabase_client import SupabaseKnowledgeBase
from ..core.auth import UserContext, AuthorizationError, extract_dataset_table_from_path, normalize_identifier


def extract_table_references(sql: str, default_project: Optional[str] = None) -> List[Tuple[Optional[str], Optional[str], Optional[str]]]:
    """Extract table references from SQL query as structured tuples.
    
    Args:
        sql: SQL query to parse
        default_project: Default project ID to use for unqualified references
        
    Returns:
        List of (project_id, dataset_id, table_id) tuples
    """
    pattern = r'(?:FROM|JOIN)\s+`?([a-zA-Z0-9_.-]+)`?'
    matches = re.findall(pattern, sql, re.IGNORECASE)
    references = []
    
    for table_ref in matches:
        parts = table_ref.split('.')
        
        if len(parts) == 3:
            # project.dataset.table
            references.append((parts[0], parts[1], parts[2]))
        elif len(parts) == 2:
            # dataset.table (use default project if provided)
            references.append((default_project, parts[0], parts[1]))
        elif len(parts) == 1:
            # Just table name - can't determine dataset/project
            references.append((None, None, parts[0]))
        else:
            references.append((None, None, None))
    
    return references


def check_table_access(user_context: UserContext, table_references: List[Tuple[Optional[str], Optional[str], Optional[str]]]) -> None:
    """Check if user has access to all tables referenced in query.
    
    Args:
        user_context: User context with permissions
        table_references: List of (project, dataset, table) tuples from SQL
        
    Raises:
        AuthorizationError: If user lacks access to any referenced table
    """
    for project_id, dataset_id, table_id in table_references:
        # Skip if we couldn't parse the reference
        if not dataset_id and not table_id:
            continue
        
        # Check access based on what we extracted
        if dataset_id and table_id:
            # Full dataset.table reference
            if not user_context.can_access_table(dataset_id, table_id):
                raise AuthorizationError(
                    f"Access denied to table {dataset_id}.{table_id}"
                )
        elif dataset_id and not table_id:
            # Dataset-only reference
            if not user_context.can_access_dataset(dataset_id):
                raise AuthorizationError(
                    f"Access denied to dataset {dataset_id}"
                )


async def query_tool_handler(
    bigquery_client,
    event_manager,
    sql: str,
    user_context: UserContext,
    maximum_bytes_billed: int = 314572800,
    knowledge_base: Optional[SupabaseKnowledgeBase] = None,
    use_cache: bool = True,
) -> Union[Dict[str, Any], Tuple[Dict[str, Any], int]]:
    """Enhanced query handler with caching and knowledge base integration.
    
    Args:
        bigquery_client: BigQuery client instance
        event_manager: Event manager for broadcasting events
        sql: SQL query to execute
        user_context: User context with authentication and authorization info
        maximum_bytes_billed: Maximum bytes to bill for the query
        knowledge_base: Optional knowledge base for caching
        use_cache: Whether to use caching
        
    Returns:
        Query result dict or tuple with error
        
    Raises:
        AuthorizationError: If user lacks required permissions
    """
    try:
        query_id = str(uuid.uuid4())
        user_id = user_context.user_id
        tables_accessed = extract_table_references(sql)
        
        # Check query execution permission
        if not user_context.has_permission("query:execute"):
            return {"error": "Missing required permission: query:execute"}, 403
        
        # Check table access authorization
        try:
            check_table_access(user_context, tables_accessed)
        except AuthorizationError as e:
            await event_manager.broadcast(
                "queries",
                "query_authorization_failed",
                {
                    "query_id": query_id,
                    "user_id": user_id,
                    "error": str(e),
                    "sql": sql[:100] + "..." if len(sql) > 100 else sql,
                },
            )
            return {"error": str(e)}, 403

        # Check cache first if enabled and knowledge_base is provided
        cached_result = None
        if use_cache and knowledge_base is not None:
            cached_result = await knowledge_base.get_cached_query(sql, user_id=user_id)
            if cached_result:
                await event_manager.broadcast(
                    "queries",
                    "query_cache_hit",
                    {
                        "query_id": query_id,
                        "sql": sql[:100] + "..." if len(sql) > 100 else sql,
                        "cached_at": cached_result["cached_at"],
                    },
                )
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                {
                                    "query_id": query_id,
                                    "result": cached_result["result"],
                                    "cached": True,
                                    "cached_at": cached_result["cached_at"],
                                    "statistics": cached_result["metadata"],
                                },
                                indent=2,
                                cls=CustomJSONEncoder,
                            ),
                        }
                    ],
                    "isError": False,
                }

        # Proceed with normal query execution
        await event_manager.broadcast(
            "queries",
            "query_start",
            {
                "query_id": query_id,
                "sql": sql,
                "maximum_bytes_billed": maximum_bytes_billed,
                "tables_accessed": tables_accessed,
            },
        )

        # Security check
        sql_upper = sql.upper()
        forbidden_keywords = ["INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER"]
        if any(keyword in sql_upper.split() for keyword in forbidden_keywords):
            if knowledge_base is not None:
                await knowledge_base.save_query_pattern(
                    sql, {}, tables_accessed, False, "Only READ operations are allowed.", user_id
                )
            return {"error": "Only READ operations are allowed."}, 400

        # Execute query
        job_config = bigquery.QueryJobConfig(maximum_bytes_billed=maximum_bytes_billed)
        query_job = bigquery_client.query(sql, job_config=job_config)

        try:
            results = query_job.result()
            rows = [dict(row.items()) for row in results]

            # Prepare statistics
            statistics = {
                "totalBytesProcessed": query_job.total_bytes_processed,
                "totalRows": getattr(query_job, "total_rows", None),
                "duration_ms": (
                    (query_job.ended - query_job.started).total_seconds() * 1000
                    if query_job.ended and query_job.started
                    else None
                ),
                "started": query_job.started.isoformat() if query_job.started else None,
                "ended": query_job.ended.isoformat() if query_job.ended else None,
            }

            # Cache the result if caching is enabled and knowledge_base is provided
            if use_cache and knowledge_base is not None and len(rows) > 0:
                await knowledge_base.cache_query_result(
                    sql, rows, statistics, tables_accessed, user_id=user_id
                )

            # Save query pattern for analysis
            if knowledge_base is not None:
                await knowledge_base.save_query_pattern(
                    sql, statistics, tables_accessed, True, user_id=user_id
                )

                # Check if this query is already a template
                existing_templates = await knowledge_base.get_query_suggestions(tables_accessed, limit=100)
                if not any(t["template_sql"].strip().lower() == sql.strip().lower() for t in existing_templates):
                    await knowledge_base.save_query_template(
                        name=f"Auto Template {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                        description="Auto-saved from successful user query.",
                        template_sql=sql,
                        parameters=[],  # Optionally extract parameters
                        tags=["auto", "user"],
                        user_id=user_id
                    )

            await event_manager.broadcast(
                "queries",
                "query_complete",
                {
                    "query_id": query_id,
                    "job_id": query_job.job_id,
                    "statistics": statistics,
                },
            )

            if knowledge_base is not None and user_id:
                await knowledge_base.increment_common_request(sql)

            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "query_id": query_id,
                                "result": rows,
                                "cached": False,
                                "statistics": statistics,
                            },
                            indent=2,
                            cls=CustomJSONEncoder,
                        ),
                    }
                ],
                "isError": False,
            }

        except Exception as e:
            # Save failed query pattern
            if knowledge_base is not None:
                await knowledge_base.save_query_pattern(
                    sql, {}, tables_accessed, False, str(e), user_id
                )

            await event_manager.broadcast(
                "queries",
                "query_error",
                {
                    "query_id": query_id,
                    "job_id": query_job.job_id if query_job else None,
                    "error": str(e),
                },
            )
            raise

    except GoogleAPIError as e:
        return {"error": f"BigQuery API error: {str(e)}"}, 500
    except Exception as e:
        print(f"Exception in enhanced query handler: {type(e).__name__}: {str(e)}")
        return {"error": f"Unexpected error: {str(e)}"}, 500


async def get_datasets_handler(
    bigquery_client,
    user_context: UserContext
) -> Union[Dict[str, Any], Tuple[Dict[str, Any], int]]:
    """Retrieve the list of datasets the user has access to.
    
    Args:
        bigquery_client: BigQuery client instance
        user_context: User context with authorization info
        
    Returns:
        Dict containing filtered list of accessible datasets
    """
    try:
        # Check permission
        if not user_context.has_permission("dataset:list"):
            # Allow if user has query:execute permission
            if not user_context.has_permission("query:execute"):
                return {"error": "Missing required permission: dataset:list"}, 403
        
        datasets = list(bigquery_client.list_datasets())
        
        # Filter datasets based on user's allowed datasets
        dataset_list = []
        for dataset in datasets:
            dataset_id = normalize_identifier(dataset.dataset_id)
            if user_context.can_access_dataset(dataset_id):
                dataset_list.append({"dataset_id": dataset.dataset_id})
        
        return {"datasets": dataset_list}
    except GoogleAPIError as e:
        return {"error": f"BigQuery API error: {str(e)}"}, 500
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}, 500


async def get_tables_handler(
    bigquery_client,
    dataset_id: str,
    user_context: UserContext
) -> Union[Dict[str, Any], Tuple[Dict[str, Any], int]]:
    """Retrieve tables within a dataset that the user has access to.
    
    Args:
        bigquery_client: BigQuery client instance
        dataset_id: Dataset identifier
        user_context: User context with authorization info
        
    Returns:
        Dict containing filtered list of accessible tables
    """
    try:
        # Check dataset access
        normalized_dataset = normalize_identifier(dataset_id)
        if not user_context.can_access_dataset(normalized_dataset):
            return {"error": f"Access denied to dataset {dataset_id}"}, 403
        
        tables = list(bigquery_client.list_tables(dataset_id))
        
        # Filter tables based on user's allowed tables
        table_list = []
        for table in tables:
            table_id = normalize_identifier(table.table_id)
            if user_context.can_access_table(normalized_dataset, table_id):
                table_list.append({"table_id": table.table_id})
        
        return {"tables": table_list}
    except GoogleAPIError as e:
        return {"error": f"BigQuery API error: {str(e)}"}, 500
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}, 500


async def get_table_schema_handler(
    bigquery_client,
    dataset_id: str,
    table_id: str,
    user_context: UserContext
) -> Union[Dict[str, Any], Tuple[Dict[str, Any], int]]:
    """Retrieve schema details for a specific table.
    
    Args:
        bigquery_client: BigQuery client instance
        dataset_id: Dataset identifier
        table_id: Table identifier
        user_context: User context with authorization info
        
    Returns:
        Dict containing table schema
    """
    try:
        # Check table access
        normalized_dataset = normalize_identifier(dataset_id)
        normalized_table = normalize_identifier(table_id)
        if not user_context.can_access_table(normalized_dataset, normalized_table):
            return {"error": f"Access denied to table {dataset_id}.{table_id}"}, 403
        
        table_ref = bigquery_client.dataset(dataset_id).table(table_id)
        table = bigquery_client.get_table(table_ref)
        schema = [
            {"name": field.name, "type": field.field_type, "mode": field.mode}
            for field in table.schema
        ]
        return {"schema": schema}
    except GoogleAPIError as e:
        return {"error": f"BigQuery API error: {str(e)}"}, 500
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}, 500


# NEW MCP TOOLS

async def get_query_suggestions_handler(
    bigquery_client,
    knowledge_base: SupabaseKnowledgeBase,
    tables_mentioned: Optional[List[str]] = None,
    query_context: Optional[str] = None,
    limit: int = 5
) -> Union[Dict[str, Any], Tuple[Dict[str, Any], int]]:
    """AI-powered query recommendations based on schema and usage patterns."""
    try:
        # Get query suggestions from knowledge base
        suggestions = await knowledge_base.get_query_suggestions(
            tables_mentioned or [], limit
        )
        
        # If we have table context, enhance suggestions with schema info
        enhanced_suggestions = []
        for suggestion in suggestions:
            enhanced_suggestion = suggestion.copy()
            
            # Add context about tables if available
            if tables_mentioned:
                table_schemas = {}
                for table_ref in tables_mentioned:
                    try:
                        parts = table_ref.split('.')
                        if len(parts) >= 2:
                            dataset_id = parts[-2]
                            table_id = parts[-1]
                            
                            table_ref_obj = bigquery_client.dataset(dataset_id).table(table_id)
                            table = bigquery_client.get_table(table_ref_obj)
                            
                            table_schemas[table_ref] = {
                                "columns": [
                                    {
                                        "name": field.name,
                                        "type": field.field_type,
                                        "mode": field.mode,
                                        "description": field.description
                                    }
                                    for field in table.schema
                                ],
                                "num_rows": table.num_rows,
                                "size_bytes": table.num_bytes
                            }
                    except Exception as e:
                        print(f"Error getting schema for {table_ref}: {e}")
                
                enhanced_suggestion["table_schemas"] = table_schemas
            
            enhanced_suggestions.append(enhanced_suggestion)
        
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "suggestions": enhanced_suggestions,
                            "context": query_context,
                            "tables_analyzed": tables_mentioned or [],
                            "generated_at": datetime.now().isoformat()
                        },
                        indent=2,
                        cls=CustomJSONEncoder
                    )
                }
            ],
            "isError": False
        }
        
    except Exception as e:
        return {"error": f"Error getting query suggestions: {str(e)}"}, 500


async def explain_table_handler(
    bigquery_client,
    knowledge_base: SupabaseKnowledgeBase,
    project_id: str,
    dataset_id: str,
    table_id: str,
    user_context: UserContext
) -> Union[Dict[str, Any], Tuple[Dict[str, Any], int]]:
    """Rich table documentation with business context.
    
    Args:
        bigquery_client: BigQuery client instance
        knowledge_base: Knowledge base for documentation
        project_id: Project identifier
        dataset_id: Dataset identifier
        table_id: Table identifier
        user_context: User context with authorization info
        
    Returns:
        Dict containing table explanation
    """
    try:
        # Check table access
        normalized_dataset = normalize_identifier(dataset_id)
        normalized_table = normalize_identifier(table_id)
        if not user_context.can_access_table(normalized_dataset, normalized_table):
            return {"error": f"Access denied to table {dataset_id}.{table_id}"}, 403
        
        # Get table metadata from BigQuery
        table_ref = bigquery_client.dataset(dataset_id).table(table_id)
        table = bigquery_client.get_table(table_ref)
        
        # Get column documentation from knowledge base
        column_docs = await knowledge_base.get_column_documentation(
            project_id, dataset_id, table_id
        )
        if column_docs is None:
            column_docs = {}
        
        # Get schema history
        try:
            # This would require implementing schema history retrieval
            schema_history_result = knowledge_base.supabase.table("schema_snapshots").select(
                "*"
            ).eq("project_id", project_id).eq("dataset_id", dataset_id).eq(
                "table_id", table_id
            ).order("schema_version", desc=True).limit(5).execute()
            
            schema_history = schema_history_result.data if schema_history_result.data else []
        except Exception as e:
            print(f"Error getting schema history: {e}")
            schema_history = []
        
        # Build comprehensive table explanation
        schema_with_docs = []
        for field in table.schema:
            field_info = {
                "name": field.name,
                "type": field.field_type,
                "mode": field.mode,
                "description": field.description or "No description available"
            }
            
            # Add documentation from knowledge base
            if field.name in column_docs:
                field_info.update(column_docs[field.name])
            
            schema_with_docs.append(field_info)
        
        table_explanation = {
            "table_info": {
                "project_id": project_id,
                "dataset_id": dataset_id,
                "table_id": table_id,
                "full_name": f"{project_id}.{dataset_id}.{table_id}",
                "description": table.description or "No description available",
                "created": table.created.isoformat() if table.created else None,
                "modified": table.modified.isoformat() if table.modified else None,
                "num_rows": table.num_rows,
                "size_bytes": table.num_bytes,
                "table_type": table.table_type
            },
            "schema": schema_with_docs,
            "schema_history": schema_history,
            "usage_patterns": {
                "note": "Query usage patterns would be derived from query_history table"
            }
        }
        
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        table_explanation,
                        indent=2,
                        cls=CustomJSONEncoder
                    )
                }
            ],
            "isError": False
        }
        
    except GoogleAPIError as e:
        return {"error": f"BigQuery API error: {str(e)}"}, 500
    except Exception as e:
        return {"error": f"Error explaining table: {str(e)}"}, 500


async def analyze_query_performance_handler(
    knowledge_base: SupabaseKnowledgeBase,
    user_context: UserContext,
    sql: Optional[str] = None,
    tables_accessed: Optional[List[str]] = None,
    time_range_hours: int = 168,  # Last week by default
) -> Union[Dict[str, Any], Tuple[Dict[str, Any], int]]:
    """Historical performance analysis for optimization."""
    try:
        cutoff_time = datetime.now() - timedelta(hours=time_range_hours)
        
        # Build query filters
        query_filters = []
        if sql:
            query_hash = knowledge_base._generate_query_hash(sql)
            # Find similar queries (this is simplified - in practice you'd use fuzzy matching)
            similar_queries = knowledge_base.supabase.table("query_history").select(
                "*"
            ).ilike("sql_query", f"%{sql[:50]}%").gte(
                "created_at", cutoff_time.isoformat()
            ).execute()
        else:
            # Get all queries in time range
            similar_queries = knowledge_base.supabase.table("query_history").select(
                "*"
            ).gte("created_at", cutoff_time.isoformat())
            
            if tables_accessed:
                # Filter by tables accessed (simplified)
                similar_queries = similar_queries.overlaps("tables_accessed", tables_accessed)
            
            # Always filter by user_id for data isolation
            similar_queries = similar_queries.eq("user_id", user_context.user_id)
            
            similar_queries = similar_queries.execute()
        
        if not similar_queries.data:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({
                            "message": "No historical query data found for the specified criteria",
                            "time_range_hours": time_range_hours,
                            "analysis_timestamp": datetime.now().isoformat()
                        }, indent=2)
                    }
                ],
                "isError": False
            }
        
        # Analyze performance patterns
        queries = similar_queries.data
        successful_queries = [q for q in queries if q["success"]]
        failed_queries = [q for q in queries if not q["success"]]
        
        # Calculate statistics
        execution_times = [q["execution_time_ms"] for q in successful_queries if q["execution_time_ms"]]
        bytes_processed = [q["bytes_processed"] for q in successful_queries if q["bytes_processed"]]
        
        analysis = {
            "summary": {
                "total_queries": len(queries),
                "successful_queries": len(successful_queries),
                "failed_queries": len(failed_queries),
                "success_rate": len(successful_queries) / len(queries) * 100 if queries else 0,
                "time_range_hours": time_range_hours
            },
            "performance_metrics": {
                "execution_time_ms": {
                    "min": min(execution_times) if execution_times else None,
                    "max": max(execution_times) if execution_times else None,
                    "avg": sum(execution_times) / len(execution_times) if execution_times else None,
                    "median": sorted(execution_times)[len(execution_times)//2] if execution_times else None
                },
                "bytes_processed": {
                    "min": min(bytes_processed) if bytes_processed else None,
                    "max": max(bytes_processed) if bytes_processed else None,
                    "avg": sum(bytes_processed) / len(bytes_processed) if bytes_processed else None,
                    "total": sum(bytes_processed) if bytes_processed else None
                }
            },
            "error_analysis": {
                "common_errors": {},  # Would be populated with error frequency analysis
                "error_rate_by_table": {}  # Would be populated with table-specific error rates
            },
            "optimization_suggestions": [
                "Consider adding appropriate indexes for frequently queried columns",
                "Use LIMIT clauses for exploratory queries",
                "Consider partitioning tables that are frequently filtered by date",
                "Use clustering for tables with repeated filter patterns"
            ]
        }
        
        # Analyze common error patterns
        error_counts = {}
        for query in failed_queries:
            error_msg = query.get("error_message", "Unknown error")
            # Simplify error message for categorization
            error_category = error_msg.split(':')[0] if ':' in error_msg else error_msg
            error_counts[error_category] = error_counts.get(error_category, 0) + 1
        
        analysis["error_analysis"]["common_errors"] = dict(
            sorted(error_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        )
        
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        analysis,
                        indent=2,
                        cls=CustomJSONEncoder
                    )
                }
            ],
            "isError": False
        }
        
    except Exception as e:
        return {"error": f"Error analyzing query performance: {str(e)}"}, 500


async def get_schema_changes_handler(
    knowledge_base: SupabaseKnowledgeBase,
    project_id: str,
    dataset_id: str,
    table_id: str,
    user_context: UserContext,
    limit: int = 10
) -> Union[Dict[str, Any], Tuple[Dict[str, Any], int]]:
    """Track schema evolution over time."""
    try:
        # Check table access
        normalized_dataset = normalize_identifier(dataset_id)
        normalized_table = normalize_identifier(table_id)
        if not user_context.can_access_table(normalized_dataset, normalized_table):
            return {"error": f"Access denied to table {dataset_id}.{table_id}"}, 403
        
        # Get schema snapshots from knowledge base
        schema_result = knowledge_base.supabase.table("schema_snapshots").select(
            "*"
        ).eq("project_id", project_id).eq("dataset_id", dataset_id).eq(
            "table_id", table_id
        ).order("schema_version", desc=True).limit(limit).execute()
        
        if not schema_result.data:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({
                            "message": f"No schema history found for {project_id}.{dataset_id}.{table_id}",
                            "table_reference": f"{project_id}.{dataset_id}.{table_id}"
                        }, indent=2)
                    }
                ],
                "isError": False
            }
        
        snapshots = schema_result.data
        
        # Analyze changes between versions
        changes = []
        for i in range(len(snapshots) - 1):
            current = snapshots[i]
            previous = snapshots[i + 1]
            
            current_schema = {col["name"]: col for col in current["schema_data"]}
            previous_schema = {col["name"]: col for col in previous["schema_data"]}
            
            version_changes = {
                "from_version": previous["schema_version"],
                "to_version": current["schema_version"],
                "timestamp": current["created_at"],
                "changes": {
                    "added_columns": [],
                    "removed_columns": [],
                    "modified_columns": [],
                    "row_count_change": current["row_count"] - previous["row_count"] if current["row_count"] and previous["row_count"] else None,
                    "size_change_bytes": current["size_bytes"] - previous["size_bytes"] if current["size_bytes"] and previous["size_bytes"] else None
                }
            }
            
            # Find added columns
            for col_name in current_schema:
                if col_name not in previous_schema:
                    version_changes["changes"]["added_columns"].append({
                        "name": col_name,
                        "type": current_schema[col_name]["type"],
                        "mode": current_schema[col_name]["mode"]
                    })
            
            # Find removed columns
            for col_name in previous_schema:
                if col_name not in current_schema:
                    version_changes["changes"]["removed_columns"].append({
                        "name": col_name,
                        "type": previous_schema[col_name]["type"],
                        "mode": previous_schema[col_name]["mode"]
                    })
            
            # Find modified columns
            for col_name in current_schema:
                if col_name in previous_schema:
                    current_col = current_schema[col_name]
                    previous_col = previous_schema[col_name]
                    
                    if (current_col["type"] != previous_col["type"] or 
                        current_col["mode"] != previous_col["mode"]):
                        version_changes["changes"]["modified_columns"].append({
                            "name": col_name,
                            "previous": {
                                "type": previous_col["type"],
                                "mode": previous_col["mode"]
                            },
                            "current": {
                                "type": current_col["type"],
                                "mode": current_col["mode"]
                            }
                        })
            
            changes.append(version_changes)
        
        schema_evolution = {
            "table_reference": f"{project_id}.{dataset_id}.{table_id}",
            "current_version": snapshots[0]["schema_version"] if snapshots else None,
            "total_versions": len(snapshots),
            "schema_snapshots": snapshots,
            "change_history": changes,
            "summary": {
                "total_schema_changes": len(changes),
                "columns_added_total": sum(len(change["changes"]["added_columns"]) for change in changes),
                "columns_removed_total": sum(len(change["changes"]["removed_columns"]) for change in changes),
                "columns_modified_total": sum(len(change["changes"]["modified_columns"]) for change in changes)
            }
        }
        
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        schema_evolution,
                        indent=2,
                        cls=CustomJSONEncoder
                    )
                }
            ],
            "isError": False
        }
        
    except Exception as e:
        return {"error": f"Error getting schema changes: {str(e)}"}, 500


async def cache_management_handler(
    knowledge_base: SupabaseKnowledgeBase,
    user_context: UserContext,
    action: str,
    target: Optional[str] = None,
    project_id: Optional[str] = None,
    dataset_id: Optional[str] = None,
    table_id: Optional[str] = None
) -> Union[Dict[str, Any], Tuple[Dict[str, Any], int]]:
    """Manual cache control (clear, refresh, etc.).
    
    Cache operations are isolated per user to ensure users can only
    manage their own cached content.
    """
    try:
        result: dict[str, Any] = {"action": action, "timestamp": datetime.now().isoformat()}
        user_id = user_context.user_id
        
        if action == "clear_all":
            # Clear all cache entries for the current user only
            clear_result = knowledge_base.supabase.table("query_cache").update({
                "expires_at": datetime.now().isoformat()
            }).eq("user_id", user_id).execute()
            
            result["message"] = "All your cache entries cleared"
            result["affected_entries"] = len(clear_result.data) if clear_result.data else 0
            
        elif action == "clear_table" and project_id and dataset_id and table_id:
            # Clear cache for specific table
            await knowledge_base.invalidate_cache_for_table(project_id, dataset_id, table_id)
            result["message"] = f"Cache cleared for table {project_id}.{dataset_id}.{table_id}"
            result["table"] = f"{project_id}.{dataset_id}.{table_id}"
            
        elif action == "clear_expired":
            # Remove expired cache entries for the current user only
            delete_result = knowledge_base.supabase.table("query_cache").delete().eq(
                "user_id", user_id
            ).lt("expires_at", datetime.now().isoformat()).execute()
            
            result["message"] = "Your expired cache entries removed"
            result["removed_entries"] = len(delete_result.data) if delete_result.data else 0
            
        elif action == "cache_stats":
            # Get cache statistics for the current user only
            total_result = knowledge_base.supabase.table("query_cache").select(
                "id", count="exact", head=True
            ).eq("user_id", user_id).execute()
            active_result = knowledge_base.supabase.table("query_cache").select(
                "id", count="exact", head=True
            ).eq("user_id", user_id).gte("expires_at", datetime.now().isoformat()).execute()
            expired_result = knowledge_base.supabase.table("query_cache").select(
                "id", count="exact", head=True  
            ).eq("user_id", user_id).lt("expires_at", datetime.now().isoformat()).execute()

            # Get hit statistics for the current user
            hits_result = knowledge_base.supabase.table("query_cache").select(
                "hit_count"
            ).eq("user_id", user_id).gte("expires_at", datetime.now().isoformat()).execute()

            hit_counts = [entry["hit_count"] for entry in hits_result.data] if hits_result.data else []

            result["message"] = "Your cache statistics retrieved"
            result["statistics"] = {
                "total_entries": total_result.count if total_result else 0,
                "active_entries": active_result.count if active_result else 0,
                "expired_entries": expired_result.count if expired_result else 0,
                "total_hits": sum(hit_counts),
                "average_hits_per_entry": sum(hit_counts) / len(hit_counts) if hit_counts else 0,
                "cache_hit_rate": "Would require tracking cache misses to calculate"
            }
            
        elif action == "cache_top_queries":
            # Get most frequently accessed cached queries for the current user
            top_queries_result = knowledge_base.supabase.table("query_cache").select(
                "sql_query", "hit_count", "created_at", "expires_at"
            ).eq("user_id", user_id).gte("expires_at", datetime.now().isoformat()).order(
                "hit_count", desc=True
            ).limit(10).execute()
            
            result.update({
                "message": "Top cached queries retrieved",
                "top_queries": top_queries_result.data if top_queries_result.data else []
            })
            
        else:
            return {"error": f"Unknown cache action: {action}. Available actions: clear_all, clear_table, clear_expired, cache_stats, cache_top_queries"}, 400
        
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(result, indent=2, cls=CustomJSONEncoder)
                }
            ],
            "isError": False
        }
        
    except Exception as e:
        return {"error": f"Error in cache management: {str(e)}"}, 500