"""统一时间源（P1-13）。

审核报告 P1-13：时间来源双轨 —— SQL `NOW()`（MySQL 容器默认 UTC）与 Python
`datetime.now()`（进程本地时区，CI/容器内常为 UTC）混用，会在同一张表、同一逻辑
时刻写入两个不同基准的时间；容器重建或跨时区部署后 `create_time` / `update_time`
错位 8 小时，且没有任何约束或校验能发现。

统一策略（两条同时生效，使两端落在同一基准）：
1. **应用侧**：一律使用本模块的 `now()`（显式 Asia/Shanghai），不再裸用
   `datetime.now()`；
2. **数据库侧**：连接会话时区固定 `+08:00`
   （FastAPI 见 `app/core/database.py` 的 `init_command`，Django 见
   `manage/config/settings.py`），使 SQL 的 `NOW()` 与 (1) 同基准。
"""
from datetime import datetime
from zoneinfo import ZoneInfo

#: 全栈统一时区（设计 B-10 / 9.3）
TZ_SHANGHAI = ZoneInfo("Asia/Shanghai")


def now() -> datetime:
    """当前时间（Asia/Shanghai）。

    返回 **naive** datetime（去掉 tzinfo）：与 MySQL `DATETIME` 列、Django
    `USE_TZ=False` 的约定一致，避免驱动做隐式时区换算。
    """
    return datetime.now(TZ_SHANGHAI).replace(tzinfo=None)
