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

from app.api import (  # pyright: ignore[reportImplicitRelativeImport]
    announcement,
    auth,
    files,
    health,
    leave,
    message,
    profile,
    score,
    timetable,
)
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
    """应用生命周期：启动/关闭日志（T0-3）。"""
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

# 幂等（3.6/P1-09）：Idempotency-Key 防重复提交
# v2.2（P1-12）：幂等记录迁移 MySQL 唯一表 campus_idempotency_key（Redis 仅缓存），待实施
app.add_middleware(IdempotencyMiddleware)


# ---- 全局异常处理器 ----

@app.exception_handler(BizError)
async def biz_error_handler(request: Request, exc: BizError):
    """业务异常统一处理：转 HTTP 200 + { code, message, data }（6.1）。"""
    return JSONResponse(status_code=200, content=fail(exc.code, exc.message, exc.data))


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    """请求参数校验失败：提取首个字段错误 → 4001。"""
    first = exc.errors()[0] if exc.errors() else {}
    field = ".".join(str(x) for x in first.get("loc", []))
    msg = f"{field}: {first.get('msg', '参数错误')}" if field else "参数错误"
    return JSONResponse(status_code=200, content=fail(ErrorCode.PARAM_ERROR, msg))


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_handler(request: Request, exc: SQLAlchemyError):
    """SQLAlchemy 异常：记录日志 → 5000（数据库操作失败）。"""
    logger.error("SQLAlchemy error: %s", exc, exc_info=True)
    return JSONResponse(status_code=200, content=fail(ErrorCode.SERVER_ERROR, "数据库操作失败"))


@app.exception_handler(StarletteHTTPException)
async def http_handler(request: Request, exc: StarletteHTTPException):
    """Starlette HTTP 异常（404/405 等）：统一转 5000 响应。"""
    return JSONResponse(status_code=200, content=fail(ErrorCode.SERVER_ERROR, exc.detail))


@app.exception_handler(Exception)
async def unknown_handler(request: Request, exc: Exception):
    """兜底异常：记录完整堆栈 → 5000（服务异常）。"""
    logger.error("Unhandled error: %s", exc, exc_info=True)
    return JSONResponse(status_code=200, content=fail(ErrorCode.SERVER_ERROR, "服务异常"))


# ---- 路由 ----
# 健康检查按设计报告 9.6 / T0-6 挂载无前缀 GET /health，同时保留 /api/health 兼容
app.include_router(health.router, tags=["health"])
app.include_router(health.router, prefix=settings.API_PREFIX, tags=["health"])
# 认证（3.4 / T1-2）
app.include_router(auth.router, prefix=settings.API_PREFIX, tags=["auth"])
# 文件上传/下载（5.3.14 / T0-7）
app.include_router(files.router, prefix=settings.API_PREFIX, tags=["files"])
# 课表（4.1 / T2-4/T2-5）+ 班级（T2-6）
app.include_router(timetable.router, prefix=settings.API_PREFIX, tags=["timetable"])
app.include_router(timetable.classes_router, prefix=settings.API_PREFIX, tags=["classes"])
# 公告（4.2 / T3-2/T3-3：列表/详情 + 版本化缓存）
app.include_router(announcement.router, prefix=settings.API_PREFIX, tags=["announcements"])
# 成绩（4.3 / T4：学生查询/教师录入 + 乐观锁 + 审计）
app.include_router(score.router, prefix=settings.API_PREFIX, tags=["scores"])
# 请假（4.4 / T5：提交/撤销/待审批/审批 + 消息联动）
app.include_router(leave.router, prefix=settings.API_PREFIX, tags=["leaves"])
# 站内消息（4.4 / T5-8：列表/未读数/已读）
app.include_router(message.router, prefix=settings.API_PREFIX, tags=["messages"])
# 个人信息（4.5 / M6-T6-1：GET/PUT /api/profile + phone.full）
app.include_router(profile.router, prefix=settings.API_PREFIX, tags=["profile"])


@app.get("/")
def root():
    """根路径：返回服务基本信息与文档入口。"""
    return {"code": 0, "message": "智慧校园信息管理系统 API", "data": {"docs": "/docs"}}
