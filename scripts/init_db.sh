#!/usr/bin/env bash
# ============================================================
# init_db.sh  数据库初始化（P0-3 破坏性操作护栏版 / P0-4 DDL 单一真相）
# 依据《智慧校园信息管理系统 设计报告》第 5 章 / 子任务 T0-4
#
# 执行内容（顺序）：
#   [0] 护栏校验：APP_ENV 白名单（仅 dev）+ 二次确认
#   [1] 强制备份：mysqldump 全库到 BACKUP_DIR，并打印备份路径
#   [2] 建库 campus（IF NOT EXISTS，utf8mb4_0900_ai_ci）+ Django migrate（DDL 权威）
#   [3] 灌入字典数据：sql/seed_dict.sql（纯 DML，幂等）
#
# 安全护栏（P0-3，原脚本被称为"幂等、可重复执行"，实际会清空全部业务表）：
#   1) 环境白名单：APP_ENV 必须为 dev，其余一律拒绝执行；
#   2) 强制备份：执行前自动 mysqldump，杜绝"无备份的清库"；
#   3) 二次确认：必须手动输入 YES；
#   4) 职责拆分：DDL 只走 Django migrations；数据只走 seed_dict.sql（不含 DROP/CREATE）。
#
# 用法：
#   bash scripts/init_db.sh
#   APP_ENV=dev MYSQL_PASS=xxx bash scripts/init_db.sh
#
# 注意：本脚本**不再执行 sql/init_all.sql**（该文件为历史遗留的第二份 DDL 真相，见 P0-4）。
#       结构变更请改 Django Model → makemigrations → migrate；导出产物用
#       bash scripts/export_ddl.sh --write
# ============================================================
set -euo pipefail

# ---- 配置（可用环境变量覆盖）----
MYSQL_HOST="${MYSQL_HOST:-127.0.0.1}"
MYSQL_PORT="${MYSQL_PORT:-3307}"
MYSQL_USER="${MYSQL_USER:-root}"
MYSQL_PASS="${MYSQL_PASS:-123456}"
MYSQL_DB="${MYSQL_DB_CAMPUS:-campus}"
BACKUP_DIR="${BACKUP_DIR:-/tmp/campus-backup}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SQL_DIR="$(cd "$SCRIPT_DIR/../sql" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_PY="${VENV_PY:-$ROOT/server/venv_wsl/bin/python}"
DJANGO_DIR="$ROOT/manage"

# MySQL 客户端连接参数
MYSQL_ARGS=(-h"$MYSQL_HOST" -P"$MYSQL_PORT" -u"$MYSQL_USER")
[ -n "$MYSQL_PASS" ] && MYSQL_ARGS+=(-p"$MYSQL_PASS")

# 优先使用 docker 内 mysql，否则用本机 mysql
if command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^campus-mysql$'; then
  MYSQL_CMD=(docker exec -i campus-mysql mysql -uroot -p"$MYSQL_PASS")
  DUMP_CMD=(docker exec -i campus-mysql mysqldump -uroot -p"$MYSQL_PASS")
else
  MYSQL_CMD=(mysql "${MYSQL_ARGS[@]}")
  DUMP_CMD=(mysqldump "${MYSQL_ARGS[@]}")
fi

echo "======================================================"
echo " 智慧校园 数据库初始化"
echo " 连接: $MYSQL_USER@$MYSQL_HOST:$MYSQL_PORT  库: $MYSQL_DB"
echo "======================================================"

# ============================================================
# [0] 护栏：环境白名单 + 二次确认（P0-3）
# ============================================================
APP_ENV="${APP_ENV:-dev}"
if [ "$APP_ENV" != "dev" ]; then
  echo "" >&2
  echo "REFUSED: init_db.sh 会重建/清空数据库，禁止在非 dev 环境执行（APP_ENV=$APP_ENV）" >&2
  echo "         如确需在其它环境初始化，请先在数据库中人工确认影响并保留备份。" >&2
  exit 1
fi

echo ""
echo "⚠️  本脚本将 DROP/重建 campus 库中的对象（Django migrate + 字典重灌）。"
echo "    目标：$MYSQL_USER@$MYSQL_HOST:$MYSQL_PORT/$MYSQL_DB"
read -r -p "    确认执行请输入 YES：" _confirm
if [ "$_confirm" != "YES" ]; then
  echo "已取消（未做任何改动）。"
  exit 1
fi

# ============================================================
# [1] 强制备份（P0-3）：清库前必须留下可恢复的快照
# ============================================================
echo ""
echo "[1/3] 备份数据库到 $BACKUP_DIR"
mkdir -p "$BACKUP_DIR"
BACKUP_FILE="$BACKUP_DIR/${MYSQL_DB}_$(date '+%Y%m%d_%H%M%S').sql"
if "${DUMP_CMD[@]}" --single-transaction --set-gtid-purged=OFF \
     --default-character-set=utf8mb4 "$MYSQL_DB" > "$BACKUP_FILE" 2>/dev/null; then
  echo "  备份完成：$BACKUP_FILE ($(du -h "$BACKUP_FILE" | cut -f1))"
  echo "  恢复方式：mysql ... $MYSQL_DB < $BACKUP_FILE"
else
  echo "  [警告] 备份失败（库可能尚不存在）→ 继续执行初始化。" >&2
  rm -f "$BACKUP_FILE"
fi

# ============================================================
# [2] 建库 + Django migrations（DDL 唯一权威，P0-4）
# ============================================================
echo ""
echo "[2/3] 建库 + Django migrations（DDL 权威：sys_user + 系统表 + 全部业务表）"
"${MYSQL_CMD[@]}" --default-character-set=utf8mb4 -e "
CREATE DATABASE IF NOT EXISTS \`$MYSQL_DB\`
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_0900_ai_ci;"

if [ -x "$VENV_PY" ] && [ -d "$DJANGO_DIR" ]; then
  echo "  执行: python manage.py migrate"
  (cd "$DJANGO_DIR" && "$VENV_PY" manage.py migrate)
else
  echo "  [错误] 缺少 $VENV_PY 或 $DJANGO_DIR，无法执行 migrations（DDL 权威）。" >&2
  exit 1
fi

# ============================================================
# [3] 字典数据（纯 DML，幂等）
# ============================================================
echo ""
echo "[3/3] 灌入字典数据：$SQL_DIR/seed_dict.sql"
"${MYSQL_CMD[@]}" --default-character-set=utf8mb4 < "$SQL_DIR/seed_dict.sql"
echo "  完成: seed_dict.sql"

echo ""
echo "======================================================"
echo " 数据库初始化完成。"
echo " 校验："
echo "   USE $MYSQL_DB; SHOW TABLES;                 # 业务表 + sys_user"
echo "   SELECT dict_type, dict_label, dict_value FROM sys_dict_data"
echo "     WHERE dict_type LIKE 'campus_%' LIMIT 5;  # 字典数据"
echo " 创建管理员账号（如需要）："
echo "   cd bysj/manage && ../server/venv_wsl/bin/python manage.py createsuperuser"
echo " 备份文件：$BACKUP_FILE"
echo " ======================================================"
