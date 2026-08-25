#!/usr/bin/env bash
# =============================================================
# 一键启动 uni-app H5 开发环境（方案 A：VSCode + CLI 工程）
#
# 职责：
#   1. 确保 FastAPI 后端（127.0.0.1:8000）已启动
#   2. 启动 uni-app H5 dev server（http://127.0.0.1:8080，带热更新）
#
# 前置条件：uniapp/ 已是 CLI 工程（package.json + src/，见 T0-1 完成情况）
#
# 用法：bash bysj/scripts/run-h5.sh
# =============================================================
set -euo pipefail

BYsj="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIA="$BYsj/uniapp"
PORT="${PORT:-8080}"
API_PORT=8000

log()  { printf '\033[1;36m[run-h5]\033[0m %s\n' "$*"; }

# ---------- 1. FastAPI 后端 ----------
if ! curl -sf "http://127.0.0.1:${API_PORT}/api/health" >/dev/null 2>&1; then
  log "FastAPI 未启动，正在拉起（127.0.0.1:${API_PORT}）..."
  (cd "$BYsj/server" && nohup ./venv_wsl/bin/python -m uvicorn app.main:app \
      --host 0.0.0.0 --port "${API_PORT}" >/tmp/fastapi_h5.log 2>&1 &)
  for _ in $(seq 1 15); do
    curl -sf "http://127.0.0.1:${API_PORT}/api/health" >/dev/null 2>&1 && break
    sleep 1
  done
  curl -sf "http://127.0.0.1:${API_PORT}/api/health" >/dev/null 2>&1 \
    && log "FastAPI 就绪" || log "FastAPI 未就绪，请检查 /tmp/fastapi_h5.log"
else
  log "FastAPI 已在运行"
fi

# ---------- 2. H5 dev server ----------
if curl -sf "http://127.0.0.1:${PORT}" >/dev/null 2>&1; then
  log "端口 ${PORT} 已有服务，直接使用"
else
  log "启动 H5 dev server（${PORT}，热更新）..."
  (cd "$UNIA" && nohup env NODE_OPTIONS=--openssl-legacy-provider npm run dev:h5 \
      >/tmp/h5_dev.log 2>&1 &)
  for _ in $(seq 1 30); do
    curl -sf "http://127.0.0.1:${PORT}" >/dev/null 2>&1 && break
    sleep 1
  done
fi

log "------------------------------------------------------------"
log "  H5 已就绪："
log "    浏览器访问  http://127.0.0.1:${PORT}"
log "    登录账号    student01 / 123456（演示）"
log "    后端 API    http://127.0.0.1:${API_PORT}"
log "    开发日志    /tmp/h5_dev.log /tmp/fastapi_h5.log"
log "    停止 dev    pkill -f 'vue-cli-service uni-serve'"
log "------------------------------------------------------------"

if command -v xdg-open >/dev/null 2>&1; then
  (xdg-open "http://127.0.0.1:${PORT}" >/dev/null 2>&1 &) || true
fi
