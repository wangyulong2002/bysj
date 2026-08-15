"""请求日志中间件：记录方法/路径/耗时/状态码，>1s 标记慢请求（3.6）。"""
import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("campus.request")

SLOW_REQUEST_MS = 1000


class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        cost_ms = (time.perf_counter() - start) * 1000
        slow = " [SLOW]" if cost_ms > SLOW_REQUEST_MS else ""
        logger.info(
            "%s %s -> %d %.1fms%s",
            request.method,
            request.url.path,
            response.status_code,
            cost_ms,
            slow,
        )
        return response
