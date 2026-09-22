#!/usr/bin/env bash
# ============================================================
# export_ddl.sh  DDL 单一真相：漂移门禁 + 导出产物（P0-4）
# ------------------------------------------------------------
# 背景（P0-4）：项目声明「DDL 权威为 Django migrations，sql/ 仅导出产物」，
# 但 sql/init_all.sql 中的 21 张表 CREATE TABLE 是**人工维护的第二份真相**，
# 与 4 个迁移文件并存 → 两侧必然漂移（"本地能跑、服务器报 Unknown column"）。
#
# 本脚本把「导出」变成唯一合法的 sql/ 来源：
#   1) 漂移门禁：`makemigrations --check --dry-run`
#      模型已改但未生成迁移 → 非零退出（可直接用于 CI）。
#   2) 导出产物：`--write` 时导出「数据库实际结构（无数据）」到
#      sql/schema_export.sql，作为只读交付/查阅产物。
#
# 约定：sql/schema_export.sql 由本脚本生成，**禁止人工修改**；
#       任何结构变更必须先改 Django Model → makemigrations → migrate。
#
# 用法：
#   bash scripts/export_ddl.sh            # 仅漂移检测（默认，不写文件）
#   bash scripts/export_ddl.sh --write     # 漂移检测 + 导出 sql/schema_export.sql
# ============================================================
set -euo pipefail

MYSQL_HOST="${MYSQL_HOST:-127.0.0.1}"
MYSQL_PORT="${MYSQL_PORT:-3307}"
MYSQL_USER="${MYSQL_USER:-root}"
MYSQL_PASS="${MYSQL_PASS:-123456}"
MYSQL_DB="${MYSQL_DB_CAMPUS:-campus}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SQL_DIR="$ROOT/sql"
DJANGO_DIR="$ROOT/manage"
VENV_PY="${VENV_PY:-$ROOT/server/venv_wsl/bin/python}"

WRITE=0
[ "${1:-}" = "--write" ] && WRITE=1

if [ ! -x "$VENV_PY" ]; then
  echo "[错误] 未找到虚拟环境解释器：$VENV_PY" >&2
  exit 1
fi

echo "======================================================"
echo " DDL 单一真相检查（P0-4）"
echo " 权威：Django migrations（$DJANGO_DIR）"
echo "======================================================"

# ---- 1/2 漂移门禁 ----
echo ""
echo "[1/2] 漂移检测：makemigrations --check --dry-run"
if (cd "$DJANGO_DIR" && "$VENV_PY" manage.py makemigrations --check --dry-run); then
  echo "  [通过] 模型与迁移一致（无未生成的迁移）"
else
  echo "  [失败] 存在未生成的模型变更：请执行 cd manage && python manage.py makemigrations" >&2
  exit 1
fi

# ---- 2/2 导出（可选）----
if [ "$WRITE" -eq 0 ]; then
  echo ""
  echo "[2/2] 跳过导出（未指定 --write）"
  exit 0
fi

OUT="$SQL_DIR/schema_export.sql"
echo ""
echo "[2/2] 导出数据库实际结构 → $OUT"

# 容器内 mysql 工具优先（与 init_db.sh 保持一致的连接策略）
if command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^campus-mysql$'; then
  DUMP_CMD=(docker exec -i campus-mysql mysqldump -uroot -p"$MYSQL_PASS"
            --no-data --skip-comments --single-transaction --set-gtid-purged=OFF "$MYSQL_DB")
else
  DUMP_CMD=(mysqldump -h"$MYSQL_HOST" -P"$MYSQL_PORT" -u"$MYSQL_USER" -p"$MYSQL_PASS"
            --no-data --skip-comments --single-transaction --set-gtid-purged=OFF
            --default-character-set=utf8mb4 "$MYSQL_DB")
fi

{
  echo "-- ============================================================"
  echo "-- schema_export.sql —— 数据库结构导出产物（自动生成，禁止人工修改）"
  echo "-- 生成脚本：scripts/export_ddl.sh --write"
  echo "-- 生成时间：$(date '+%Y-%m-%d %H:%M:%S')"
  echo "-- DDL 权威：Django migrations（变更请改 manage/apps/models.py + makemigrations）"
  echo "-- ============================================================"
  "${DUMP_CMD[@]}"
} > "$OUT"

echo "  [完成] 已写出 $(wc -l < "$OUT") 行"
echo "  提示：该文件为只读产物，请勿人工编辑；结构变更走 Django Model + 迁移。"
