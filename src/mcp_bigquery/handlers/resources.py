"""Resource handlers for BigQuery operations."""
import json
from typing import Dict, Any, Tuple, Union
from google.api_core.exceptions import GoogleAPIError
from ..core.json_encoder import CustomJSONEncoder


async def list_resources_handler(bigquery_client, config) -> Union[Dict[str, Any], Tuple[Dict[str, Any], int]]:
    """List all available BigQuery datasets and tables."""
    try:
        print("Listing resources...")
        datasets = list(bigquery_client.list_datasets())
        resources = []

        for dataset in datasets:
            tables = list(bigquery_client.list_tables(dataset.dataset_id))
            for table in tables:
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
    bigquery_client, config, project_id: str, dataset_id: str, table_id: str
) -> Union[Dict[str, Any], Tuple[Dict[str, Any], int]]:
    """Retrieve metadata for a specific BigQuery table."""
    try:
        # Validate project_id matches configured project
        if project_id != config.project_id:
            return {"error": "Project ID mismatch"}, 400

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