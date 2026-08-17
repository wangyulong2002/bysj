#!/usr/bin/env bash
# ============================================================
# init_db.sh  数据库一键初始化脚本（T0-4）
# 依据《智慧校园信息管理系统 设计报告》第 5 章 / 子任务 T0-4
#
# 功能：按顺序执行 sql/ 下的初始化脚本，可重复执行（幂等）。
#  1. 00_create_database.sql   创建 campus 数据库（IF NOT EXISTS）
#  2. 01_sys_user_extend.sql   为 ry.sys_user 增加扩展字段（幂等）
#  3. 02_business_tables.sql   创建全部业务表（DROP+CREATE 重建，含 version 列）
#  4. 03_dict_data.sql         初始化字典数据（DELETE+INSERT）
#  5. 04_add_version_columns.sql 乐观锁 version 列迁移（幂等，对已存在库增量补列）
#
# 用法：
#  ../../scripts/init_db.sh                 # 使用默认连接（Docker MySQL 3307）
#  MYSQL_HOST=x MYSQL_PORT=3306 MYSQL_PASS=y ../../scripts/init_db.sh
#
# 注意：02_business_tables.sql 会 DROP 并重建业务表（清空数据），
#       仅用于初始化/开发环境，勿在生产重复执行。
# ============================================================
set -euo pipefail

# ---- 配置（可用环境变量覆盖）----
MYSQL_HOST="${MYSQL_HOST:-127.0.0.1}"
MYSQL_PORT="${MYSQL_PORT:-3307}"
MYSQL_USER="${MYSQL_USER:-root}"
MYSQL_PASS="${MYSQL_PASS:-123456}"

# 脚本所在目录（便于从任意 cwd 调用）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SQL_DIR="$(cd "$SCRIPT_DIR/../sql" && pwd)"

# MySQL 客户端连接参数
MYSQL_ARGS=(-h"$MYSQL_HOST" -P"$MYSQL_PORT" -u"$MYSQL_USER" -p"$MYSQL_PASS")
# 若密码为空，去掉 -p 参数
if [ -z "$MYSQL_PASS" ]; then
  MYSQL_ARGS=(-h"$MYSQL_HOST" -P"$MYSQL_PORT" -u"$MYSQL_USER")
fi

# 优先使用 docker 内 mysql，否则用本机 mysql
if command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^campus-mysql$'; then
  # 容器内 MySQL 监听默认端口（3306）与 unix socket，不再传 -h/-P/-u
  MYSQL_CMD=(docker exec -i campus-mysql mysql -uroot -p"$MYSQL_PASS")
else
  MYSQL_CMD=(mysql "${MYSQL_ARGS[@]}")
fi

run_sql() {
  local file="$1"
  echo "==> 执行: $(basename "$file")"
  "${MYSQL_CMD[@]}" --default-character-set=utf8mb4 < "$file"
  echo "   完成: $(basename "$file")"
}

echo "======================================================"
echo " 智慧校园 数据库初始化开始"
echo " 连接: $MYSQL_USER@$MYSQL_HOST:$MYSQL_PORT"
echo " SQL 目录: $SQL_DIR"
echo "======================================================"

run_sql "$SQL_DIR/00_create_database.sql"
run_sql "$SQL_DIR/01_sys_user_extend.sql"
run_sql "$SQL_DIR/02_business_tables.sql"
run_sql "$SQL_DIR/03_dict_data.sql"
run_sql "$SQL_DIR/04_add_version_columns.sql"

echo "======================================================"
echo " 数据库初始化完成。"
echo " 业务表: USE campus; SHOW TABLES;"
echo " 字典:   SELECT dict_type, dict_label, dict_value FROM ry.sys_dict_data WHERE dict_type LIKE 'campus_%';"
echo "======================================================"
