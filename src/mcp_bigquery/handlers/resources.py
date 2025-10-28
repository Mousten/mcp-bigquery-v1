"""Resource handlers for BigQuery operations."""
import json
from typing import Dict, Any, Tuple, Union
from google.api_core.exceptions import GoogleAPIError
from ..core.json_encoder import CustomJSONEncoder
from ..core.auth import UserContext, normalize_identifier


async def list_resources_handler(
    bigquery_client,
    config,
    user_context: UserContext
) -> Union[Dict[str, Any], Tuple[Dict[str, Any], int]]:
    """List BigQuery datasets and tables the user has access to.
    
    Args:
        bigquery_client: BigQuery client instance
        config: Server configuration
        user_context: User context with authorization info
        
    Returns:
        Dict containing filtered list of accessible resources
    """
    try:
        print("Listing resources...")
        datasets = list(bigquery_client.list_datasets())
        resources = []

        for dataset in datasets:
            dataset_id = normalize_identifier(dataset.dataset_id)
            # Skip datasets user cannot access
            if not user_context.can_access_dataset(dataset_id):
                continue
            
            tables = list(bigquery_client.list_tables(dataset.dataset_id))
            for table in tables:
                table_id = normalize_identifier(table.table_id)
                # Filter tables based on user access
                if user_context.can_access_table(dataset_id, table_id):
                    resources.append({
                        "uri": f"bigquery://{config.project_id}/{dataset.dataset_id}/{table.table_id}",
                        "mimeType": "application/json",
                        "name": f"{dataset.dataset_id}.{table.table_id}",
                    })

        return {"resources": resources}
    except GoogleAPIError as e:
        print(f"BigQuery API error: {str(e)}")
        return {"error": f"BigQuery API error: {str(e)}"}, 500
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return {"error": f"Unexpected error: {str(e)}"}, 500


async def read_resource_handler(
    bigquery_client,
    config,
    project_id: str,
    dataset_id: str,
    table_id: str,
    user_context: UserContext
) -> Union[Dict[str, Any], Tuple[Dict[str, Any], int]]:
    """Retrieve metadata for a specific BigQuery table.
    
    Args:
        bigquery_client: BigQuery client instance
        config: Server configuration
        project_id: Project identifier
        dataset_id: Dataset identifier
        table_id: Table identifier
        user_context: User context with authorization info
        
    Returns:
        Dict containing table metadata
    """
    try:
        # Validate project_id matches configured project
        if project_id != config.project_id:
            return {"error": "Project ID mismatch"}, 400
        
        # Check table access
        normalized_dataset = normalize_identifier(dataset_id)
        normalized_table = normalize_identifier(table_id)
        if not user_context.can_access_table(normalized_dataset, normalized_table):
            return {"error": f"Access denied to table {dataset_id}.{table_id}"}, 403

        # Get table metadata
        table_ref = bigquery_client.dataset(dataset_id).table(table_id)
        table = bigquery_client.get_table(table_ref)

        # Convert schema to dictionary format
        schema_dict = [
            {
                "name": field.name,
                "type": field.field_type,
                "mode": field.mode,
                "description": field.description,
            }
            for field in table.schema
        ]

        # Include additional metadata
        metadata = {
            "schema": schema_dict,
            "numRows": table.num_rows,
            "sizeBytes": table.num_bytes,
            "creationTime": table.created.isoformat() if table.created else None,
            "lastModifiedTime": table.modified.isoformat() if table.modified else None,
            "description": table.description,
        }

        return {
            "contents": [
                {
                    "uri": f"bigquery://{project_id}/{dataset_id}/{table_id}",
                    "mimeType": "application/json",
                    "text": json.dumps(metadata, indent=2, cls=CustomJSONEncoder),
                }
            ]
        }
    except GoogleAPIError as e:
        return {"error": f"BigQuery API error: {str(e)}"}, 500
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}, 500