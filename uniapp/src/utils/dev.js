/**
 * API 地址解析（开发 / 部署多端复用）
 *
 * ── 部署上线（推荐，改一处全端生效）──
 *   在项目根目录 .env.production 中配置：
 *     VUE_APP_API_BASE=http://服务器IP或域名:8000
 *   然后重新构建：
 *     npm run build:h5         → 产物部署到 nginx
 *     npm run build:mp-weixin  → 微信开发者工具上传发布
 *   无需修改任何源码。
 *
 * ── 本地开发（无环境变量时的默认值）──
 *   H5（浏览器）：固定 127.0.0.1
 *   小程序 / 真机：DEV_IP（修改下方一处，多端复用）
 *     模拟器调试保持 127.0.0.1（WSL2 localhost 转发默认开启）；
 *     真机预览改为局域网 IP（如 192.168.x.x）。
 */
const DEPLOY_BASE = process.env.VUE_APP_API_BASE || ''

// #ifdef H5
const API_BASE_URL = DEPLOY_BASE || 'http://127.0.0.1:8000'
// #endif
// #ifndef H5
const DEV_IP = '127.0.0.1' // ← 真机预览时改成局域网 IP，多端复用（开发机 WSL IP）
const API_BASE_URL = DEPLOY_BASE || `http://${DEV_IP}:8000`
// #endif

export { API_BASE_URL }
