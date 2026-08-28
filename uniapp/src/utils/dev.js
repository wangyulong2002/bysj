/**
 * API 地址解析 —— 一次配置，全端通用
 *
 * 唯一地址源：项目根 `.env` 的 `PUBLIC_BASE_URL`（如 http://192.168.0.100:8000）
 *   - 后端签名 URL（头像等直链）由 server/config.py 读取同一变量
 *   - 前端构建由 Makefile 自动注入（make h5-build / make mp-build）
 *   - 部署/真机：只改根 .env 一处 → 重新构建 → H5 / 小程序 / 签名 URL 全部生效
 *
 * 本文件规则：
 *   1) 构建时（make h5-build / make mp-build）VUE_APP_API_BASE 由 Makefile 注入；
 *   2) 未注入时回退默认 http://127.0.0.1:8000（本地模拟器/H5 开发，同机同端口）。
 *   无需再手动改本文件（真机/部署改根 .env 即可）。
 */
const API_BASE_URL = process.env.VUE_APP_API_BASE || 'http://127.0.0.1:8000'

export { API_BASE_URL }
