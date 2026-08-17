"""配置加载模块（pydantic-settings）。

依据设计报告 9.3 配置项清单。启动时校验必填项，缺失给出明确报错。
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]  # server/


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 服务基础
    APP_NAME: str = "智慧校园信息管理系统"
    APP_ENV: str = "dev"
    DEBUG: bool = True
    API_PREFIX: str = "/api"

    # MySQL
    MYSQL_HOST: str = "127.0.0.1"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASS: str = ""
    MYSQL_DB: str = "campus"
    MYSQL_CHARSET: str = "utf8mb4"

    # Redis
    REDIS_URL: str = "redis://127.0.0.1:6379/0"

    # JWT
    JWT_SECRET: str = "please-change-me"
    JWT_EXPIRE: int = 7200
    JWT_ALGORITHM: str = "HS256"

    # LLM（DeepSeek）
    LLM_BASE_URL: str = "https://api.deepseek.com"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "deepseek-chat"

    # Embedding（智谱）
    EMB_BASE_URL: str = "https://open.bigmodel.cn"
    EMB_API_KEY: str = ""
    EMB_MODEL: str = "embedding-2"
    EMB_DIM: int = 1024

    # RAG
    RAG_TOP_N: int = 5
    RAG_KNN_K: int = 10
    RAG_RATE_PER_MIN: int = 10
    RAG_RATE_PER_DAY: int = 100
    RAG_LOG_RETENTION_DAYS: int = 30

    # 文件
    FILE_UPLOAD_DIR: str = "./uploads"
    FILE_MAX_SIZE_MB: int = 10
    FILE_ALLOWED_TYPES: str = "jpg,png,gif,pdf,docx,xlsx"

    # 幂等（3.6/P1-09）：Idempotency-Key 缓存保留秒数
    IDEMPOTENCY_EXPIRE_SECONDS: int = 86400

    # 备份
    BACKUP_DIR: str = "/backup/mysql"
    BACKUP_RETENTION_DAYS: int = 30

    # CORS
    CORS_ALLOWED_ORIGINS: str = "*"

    # 登录安全
    LOGIN_MAX_FAIL: int = 5
    LOGIN_LOCK_MINUTES: int = 10

    @property
    def database_url(self) -> str:
        """SQLAlchemy 连接串。"""
        return (
            f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASS}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DB}"
            f"?charset={self.MYSQL_CHARSET}"
        )

    @property
    def cors_origins(self) -> list[str]:
        if self.CORS_ALLOWED_ORIGINS == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ALLOWED_ORIGINS.split(",") if o.strip()]

    @property
    def file_upload_dir(self) -> Path:
        """上传目录：相对路径解析到项目根（bysj/），独立于 web 可执行路径（9.2）。"""
        p = Path(self.FILE_UPLOAD_DIR)
        if p.is_absolute():
            return p
        return BASE_DIR.parent / p

    @property
    def file_max_size(self) -> int:
        """文件大小上限（字节）。"""
        return int(self.FILE_MAX_SIZE_MB) * 1024 * 1024

    @property
    def file_allowed_types(self) -> set[str]:
        return {t.strip().lower() for t in self.FILE_ALLOWED_TYPES.split(",") if t.strip()}

    def validate_required(self) -> None:
        """启动时校验必填配置项（9.3）。"""
        missing = []
        if not self.MYSQL_PASS:
            missing.append("MYSQL_PASS")
        if not self.JWT_SECRET or self.JWT_SECRET == "please-change-me":
            missing.append("JWT_SECRET")
        if missing:
            raise RuntimeError(
                f"缺少必要配置项: {', '.join(missing)}，请检查 server/.env（参考 .env.example）"
            )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_required()
    return settings


settings = get_settings()
