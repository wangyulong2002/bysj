"""配置加载模块（pydantic-settings）。

依据设计报告 9.3 配置项清单。启动时校验必填项，缺失给出明确报错。
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]   # server/
PROJECT_ROOT = BASE_DIR.parent                     # bysj/（项目根，统一 .env 所在）


class Settings(BaseSettings):
    # 配置来源优先级：环境变量 > 项目根 .env > server/.env（本地兼容，已弃用）
    model_config = SettingsConfigDict(
        env_file=(str(PROJECT_ROOT / ".env"), str(BASE_DIR / ".env")),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 服务基础
    APP_NAME: str = "智慧校园信息管理系统"
    APP_ENV: str = "dev"
    DEBUG: bool = True
    API_PREFIX: str = "/api"
    # 对外公共基础地址（签名 URL 直链用，如 http://127.0.0.1:8000；部署改为服务器地址）
    PUBLIC_BASE_URL: str = ""

    # MySQL
    MYSQL_HOST: str = "127.0.0.1"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASS: str = ""
    MYSQL_DB: str = "campus"
    MYSQL_CHARSET: str = "utf8mb4"
    # 统一 .env 的库名键（可选）：配置了则覆盖 MYSQL_DB
    MYSQL_DB_CAMPUS: str | None = None

    # Redis
    REDIS_URL: str = "redis://127.0.0.1:6379/0"

    # JWT
    JWT_SECRET: str = "please-change-me"
    JWT_EXPIRE: int = 7200
    JWT_ALGORITHM: str = "HS256"

    # 火山引擎方舟（RAG，生成+向量化统一，按 Token 计费，9.3/8.2）
    ARK_BASE_URL: str = "https://ark.cn-beijing.volces.com/api/v3"
    ARK_API_KEY: str = ""
    LLM_MODEL: str = "deepseek-chat"
    EMB_MODEL: str = "doubao-embedding"
    EMB_DIM: int = 2048  # doubao-embedding-vision 实测维度（与 RediSearch 索引 DDL 绑定）
    # 生成调用约束（8.4 注入防护第 5 层：限制输出 token；8.6 P95≤4s）
    LLM_TIMEOUT_SECONDS: float = 10.0
    LLM_MAX_TOKENS: int = 1024
    # Embedding 批量大小（T7-1：Worker 切分后整批向量化，8~16 条/批）
    EMB_BATCH_SIZE: int = 16

    # LLM 兜底通道（v2.7/ADR-013：可选，仅生成兜底、Embedding 不兜底；缺省视为未启用）
    AGNES_BASE_URL: str = ""
    AGNES_API_KEY: str = ""
    AGNES_MODEL: str = "agnes-2.5-flash"

    # RAG
    RAG_TOP_N: int = 5
    RAG_KNN_K: int = 10
    RAG_RATE_PER_MIN: int = 10
    RAG_RATE_PER_DAY: int = 100
    RAG_LOG_RETENTION_DAYS: int = 30
    # 检索相关度三档阈值（v2.6/8.4.1，由 T7-7 标定，禁止硬编码到业务代码）
    RAG_SCORE_HIGH: float = 0.75
    RAG_SCORE_LOW: float = 0.45
    # L1 BM25 专有名词兜底豁免档位（8.4：BM25 兜底"XX 宿舍/教授姓名"类专有名词；
    # 融合结果中 BM25 命中排名 ≤ 该值且 best_sim 仍低于 LOW 时，不判 no_context，
    # 转弱相关档调 LLM——修复"内容级细节提问被 L1 误拒"（RAG专项测试报告 §5.1））
    RAG_BM25_GATE_RANK: int = 3
    # 领域围栏开关（v2.6/8.4.1：1 启用 L0 规则闸门 + L2 领域围栏；0 仅保留 L1）
    RAG_STRICT_DOMAIN: int = 1
    # Worker 开关（测试环境置 0，避免 TestClient 拉起后台调度）
    RAG_WORKER_ENABLED: int = 1

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

    # 微信小程序登录（B-01，T1-4）：code2session 换 openid
    WECHAT_APPID: str = ""
    WECHAT_SECRET: str = ""
    WECHAT_API_BASE_URL: str = "https://api.weixin.qq.com"  # 联调可改本地 mock

    # 登录安全
    LOGIN_MAX_FAIL: int = 5
    LOGIN_LOCK_MINUTES: int = 10

    @property
    def database_url(self) -> str:
        """SQLAlchemy 连接串（业务库：优先 MYSQL_DB_CAMPUS，兼容 MYSQL_DB）。"""
        db = self.MYSQL_DB_CAMPUS or self.MYSQL_DB
        return (
            f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASS}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{db}"
            f"?charset={self.MYSQL_CHARSET}"
        )

    @property
    def cors_origins(self) -> list[str]:
        """CORS 白名单：'*' 表示全放行（开发期），否则按逗号拆分。"""
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
        """允许上传的文件扩展名集合（小写去空白）。"""
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
    """获取全局配置单例（缓存 + 启动必填校验）。"""
    settings = Settings()
    settings.validate_required()
    return settings


settings = get_settings()
