from typing import Any, Dict

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/metrics")
async def metrics(request: Request) -> Dict[str, Any]:
    return await request.app.state.proxy.handle_metrics()
