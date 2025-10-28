from typing import Any, Dict, Optional, Union
from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse


def create_preferences_router(knowledge_base) -> APIRouter:
    router = APIRouter(prefix="/preferences", tags=["preferences"])

    @router.post("/get")
    async def get_user_preferences_api(
        user_id: Optional[str] = Body(None),
        session_id: Optional[str] = Body(None)
    ):
        if not user_id and not session_id:
            return JSONResponse(
                content={"error": "Either user_id or session_id must be provided"},
                status_code=400
            )
        
        # Prioritize user_id if available
        identifier = user_id if user_id else session_id
        
        try:
            preferences = await knowledge_base.get_user_preferences(identifier)
            if preferences:
                return {"preferences": preferences}
            else:
                return {"preferences": {}}
        except Exception as e:
            return JSONResponse(content={"error": str(e)}, status_code=500)

    @router.post("/set")
    async def set_user_preferences_api(
        preferences: Dict[str, Any] = Body(...),
        user_id: Optional[str] = Body(None),
        session_id: Optional[str] = Body(None)
    ):
        if not user_id and not session_id:
            return JSONResponse(
                content={"error": "Either user_id or session_id must be provided"},
                status_code=400
            )
        
        # Prioritize user_id if available
        identifier = user_id if user_id else session_id

        try:
            success = await knowledge_base.set_user_preferences(identifier, preferences)
            if success:
                return {"message": "Preferences updated successfully"}
            else:
                return JSONResponse(content={"error": "Failed to update preferences"}, status_code=500)
        except Exception as e:
            return JSONResponse(content={"error": str(e)}, status_code=500)

    return router
