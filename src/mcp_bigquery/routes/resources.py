"""FastAPI routes for resource operations."""
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from ..handlers.resources import list_resources_handler, read_resource_handler


def create_resources_router(bigquery_client, config) -> APIRouter:
    """Create router for resource-related endpoints."""
    router = APIRouter(prefix="/resources", tags=["resources"])

    @router.get("/list")
    async def list_resources_fastapi():
        """List all available BigQuery datasets and tables."""
        result = await list_resources_handler(bigquery_client, config)
        if isinstance(result, tuple) and len(result) == 2:
            return JSONResponse(content=result[0], status_code=result[1])
        return result

    return router


def create_bigquery_router(bigquery_client, config) -> APIRouter:
    """Create router for BigQuery resource endpoints."""
    router = APIRouter(prefix="/bigquery", tags=["bigquery"])

    @router.get("/{project_id}/{dataset_id}/{table_id}")
    async def read_resource_fastapi(project_id: str, dataset_id: str, table_id: str):
        """Retrieve metadata for a specific BigQuery table."""
        result = await read_resource_handler(
            bigquery_client, config, project_id, dataset_id, table_id
        )
        if isinstance(result, tuple) and len(result) == 2:
            return JSONResponse(content=result[0], status_code=result[1])
        return result

    return router