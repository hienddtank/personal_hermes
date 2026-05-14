from typing import Dict

from fastapi import APIRouter, Request
from fastapi.responses import Response

HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}
REQUEST_SKIP_HEADERS = HOP_BY_HOP_HEADERS | {"host", "content-length"}
RESPONSE_SKIP_HEADERS = HOP_BY_HOP_HEADERS | {"content-encoding", "content-length"}

router = APIRouter()


def forwardable_request_headers(request: Request) -> Dict[str, str]:
    return {
        name: value
        for name, value in request.headers.items()
        if name.lower() not in REQUEST_SKIP_HEADERS
    }


def forwardable_response_headers(headers: Dict[str, str]) -> Dict[str, str]:
    return {
        name: value
        for name, value in headers.items()
        if name.lower() not in RESPONSE_SKIP_HEADERS
    }


@router.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
)
async def passthrough(request: Request, path: str) -> Response:
    proxy = request.app.state.proxy
    upstream_url = f"{proxy.lmstudio_base_url.rstrip('/')}/{path}"
    if request.url.query:
        upstream_url = f"{upstream_url}?{request.url.query}"

    upstream_response = await proxy.client.request(
        request.method,
        upstream_url,
        content=await request.body(),
        headers=forwardable_request_headers(request),
    )

    return Response(
        content=b"" if request.method == "HEAD" else upstream_response.content,
        status_code=upstream_response.status_code,
        headers=forwardable_response_headers(dict(upstream_response.headers)),
        media_type=upstream_response.headers.get("content-type"),
    )
