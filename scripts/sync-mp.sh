#!/usr/bin/env bash
# =============================================================
# 同步 uni-app 小程序产物 → Windows 侧（微信开发者工具项目目录）
#
# 背景：微信开发者工具（Windows）无法直接读取 WSL 的 UNC 路径，
#       需要把 dist/dev/mp-weixin 产物放到 Windows 文件系统。
#
# 用法：
#   bash bysj/scripts/sync-mp.sh             # 同步一次
#   bash bysj/scripts/sync-mp.sh --watch     # 持续监听（配合 npm run dev:mp-weixin）
#
# 配合流程：
#   终端1: cd bysj/uniapp && npm run dev:mp-weixin   # 编译
#   终端2: bash bysj/scripts/sync-mp.sh --watch      # 自动同步
#   微信开发者工具打开 D:\bysj-mp-weixin，改代码保存后自动同步、手动点编译刷新
# =============================================================
set -euo pipefail

BYsj="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$BYsj/uniapp/dist/dev/mp-weixin"
DST="/mnt/d/bysj-mp-weixin"
MARKER="/tmp/.bysj_mp_sync_mark"
INTERVAL="${SYNC_INTERVAL:-2}"  # 监听轮询间隔（秒）

# 排除微信开发者工具自身生成/易变的文件，避免误删
EXCLUDES=(
  --exclude 'project.private.config.json'
  --exclude '.idea/'
  --exclude '.vscode/'
  --exclude 'node_modules/'
  --exclude 'miniprogram_npm/'
  --exclude '*.log'
)

log()  { printf '\033[1;36m[sync-mp]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[sync-mp]\033[0m %s\n' "$*" >&2; exit 1; }

[ -d "$SRC" ] || die "产物目录不存在：$SRC（请先运行 npm run dev:mp-weixin / build:mp-weixin）"
mkdir -p "$DST"

do_sync() {
  rsync -a --delete "${EXCLUDES[@]}" "$SRC/" "$DST/" 2>/dev/null \
    && touch "$MARKER" \
    && log "已同步 → ${DST}（$(date +%H:%M:%S)）"
}

# ---------- 一次性同步 ----------
if [ "${1:-}" != "--watch" ]; then
  do_sync
  log "完成。微信开发者工具打开项目：D:\\bysj-mp-weixin"
  exit 0
fi

# ---------- 监听模式 ----------
touch "$MARKER"
log "监听 ${SRC} 的变化（每 ${INTERVAL}s 检测，Ctrl+C 退出）..."
while true; do
  if find "$SRC" -type f -newer "$MARKER" 2>/dev/null | grep -q .; then
    do_sync
  fi
  sleep "$INTERVAL"
done
