"""FastAPI 应用入口（T0-3 骨架）。

- 统一响应 { code, message, data }（6.1）
- 全局异常处理器（业务/Pydantic/SQLAlchemy/未知）
- CORS（开发期 *，配置项可切换白名单）
- 请求日志中间件（>1s 慢请求）
- SQLAlchemy 2.x + Redis 客户端
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import files, health  # pyright: ignore[reportImplicitRelativeImport]
from app.core.config import settings  # pyright: ignore[reportImplicitRelativeImport]
from app.core.errors import BizError, ErrorCode  # pyright: ignore[reportImplicitRelativeImport]
from app.core.idempotency import IdempotencyMiddleware  # pyright: ignore[reportImplicitRelativeImport]
from app.core.middleware import RequestLogMiddleware  # pyright: ignore[reportImplicitRelativeImport]
from app.core.response import fail  # pyright: ignore[reportImplicitRelativeImport]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("campus")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=== %s 启动 (env=%s) ===", settings.APP_NAME, settings.APP_ENV)
    yield
    logger.info("=== %s 关闭 ===", settings.APP_NAME)


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    debug=settings.DEBUG,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS（3.6：开发期 *，上线白名单）
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False if "*" in settings.cors_origins else True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 请求日志
app.add_middleware(RequestLogMiddleware)

# 幂等（3.6/P1-09）：Idempotency-Key 防重复提交（Redis 故障降级直通）
app.add_middleware(IdempotencyMiddleware)


# ---- 全局异常处理器 ----

@app.exception_handler(BizError)
async def biz_error_handler(request: Request, exc: BizError):
    return JSONResponse(status_code=200, content=fail(exc.code, exc.message, exc.data))


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    field = ".".join(str(x) for x in first.get("loc", []))
    msg = f"{field}: {first.get('msg', '参数错误')}" if field else "参数错误"
    return JSONResponse(status_code=200, content=fail(ErrorCode.PARAM_ERROR, msg))


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_handler(request: Request, exc: SQLAlchemyError):
    logger.error("SQLAlchemy error: %s", exc, exc_info=True)
    return JSONResponse(status_code=200, content=fail(ErrorCode.SERVER_ERROR, "数据库操作失败"))


@app.exception_handler(StarletteHTTPException)
async def http_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(status_code=200, content=fail(ErrorCode.SERVER_ERROR, exc.detail))


@app.exception_handler(Exception)
async def unknown_handler(request: Request, exc: Exception):
    logger.error("Unhandled error: %s", exc, exc_info=True)
    return JSONResponse(status_code=200, content=fail(ErrorCode.SERVER_ERROR, "服务异常"))


# ---- 路由 ----
# 健康检查按设计报告 9.6 / T0-6 挂载无前缀 GET /health，同时保留 /api/health 兼容
app.include_router(health.router, tags=["health"])
app.include_router(health.router, prefix=settings.API_PREFIX, tags=["health"])
# 文件上传/下载（5.3.14 / T0-7）
app.include_router(files.router, prefix=settings.API_PREFIX, tags=["files"])


@app.get("/")
def root():
    return {"code": 0, "message": "智慧校园信息管理系统 API", "data": {"docs": "/docs"}}
