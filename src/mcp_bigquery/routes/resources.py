"""FastAPI routes for resource operations."""
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from ..handlers.resources import list_resources_handler, read_resource_handler
from ..core.auth import UserContext
from ..api.dependencies import create_auth_dependency


def create_resources_router(bigquery_client, config, knowledge_base=None) -> APIRouter:
    """Create router for resource-related endpoints."""
    router = APIRouter(prefix="/resources", tags=["resources"])
    
    # Create auth dependency with knowledge base for role loading
    get_current_user = create_auth_dependency(knowledge_base)

    @router.get("/list")
    async def list_resources_fastapi(current_user: UserContext = Depends(get_current_user)):
        """List all available BigQuery datasets and tables the user has access to."""
        result = await list_resources_handler(bigquery_client, config, current_user)
        if isinstance(result, tuple) and len(result) == 2:
            return JSONResponse(content=result[0], status_code=result[1])
        return result

    return router


def create_bigquery_router(bigquery_client, config, knowledge_base=None) -> APIRouter:
    """Create router for BigQuery resource endpoints."""
    router = APIRouter(prefix="/bigquery", tags=["bigquery"])
    
    # Create auth dependency with knowledge base for role loading
    get_current_user = create_auth_dependency(knowledge_base)

    @router.get("/{project_id}/{dataset_id}/{table_id}")
    async def read_resource_fastapi(
        project_id: str,
        dataset_id: str,
        table_id: str,
        current_user: UserContext = Depends(get_current_user)
    ):
        """Retrieve metadata for a specific BigQuery table."""
        result = await read_resource_handler(
            bigquery_client, config, project_id, dataset_id, table_id, current_user
        )
        if isinstance(result, tuple) and len(result) == 2:
            return JSONResponse(content=result[0], status_code=result[1])
        return result

    return router