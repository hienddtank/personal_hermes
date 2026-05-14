from typing import Any, Optional

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse

from .core import forward_headers

router = APIRouter()


@router.post("/v1/chat/completions")
async def chat_completions(
    request: Request,
    x_proxy_mode: Optional[str] = Header(default=None),
) -> Any:
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON body: {exc}") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Request body must be a JSON object.")

    if x_proxy_mode:
        payload = {**payload, "proxy_mode": x_proxy_mode}

    result = await request.app.state.proxy.handle_chat_completion(
        payload,
        forward_headers(request),
    )
    if payload.get("stream", False):
        return StreamingResponse(result, media_type="text/event-stream")
    return result
