from typing import Any, Dict

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
async def health(request: Request) -> Dict[str, Any]:
    return await request.app.state.proxy.handle_healthcheck()
