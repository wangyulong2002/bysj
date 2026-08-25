#!/usr/bin/env python3
"""微信 code2session 本地 mock 服务（B-01 / T1-4 联调用）。

用法：
    1. 启动本服务：  python scripts/mock_wechat.py            # 默认 127.0.0.1:9000
    2. 将 .env 中 WECHAT_API_BASE_URL 改为： http://127.0.0.1:9000
    3. 重启 FastAPI 后即可联调微信登录（无需真实 AppID/Secret）。

行为约定（便于前端/测试使用）：
    - code 以 `invalid` 开头       → 返回 errcode 40029（凭证无效，模拟失败场景）
    - 其他任意 code（如 `wx_<学号>`）→ 返回 openid=`mock-openid-<code>`，
      同一 code 恒定返回同一 openid，便于测试绑定/解绑闭环。

实现：仅用 Python 标准库（http.server），无第三方依赖。
"""
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

HOST = "127.0.0.1"
PORT = 9000


class MockWechatHandler(BaseHTTPRequestHandler):
    """mock 微信 code2session HTTP 处理器。"""

    def do_GET(self):  # noqa: N802 — http.server 约定命名
        """处理 GET /sns/jscode2session：按约定返回 openid 或错误码。"""
        parsed = urlparse(self.path)
        if parsed.path != "/sns/jscode2session":
            self._send(404, {"errcode": 404, "errmsg": "not found"})
            return

        params = parse_qs(parsed.query)
        code = (params.get("js_code") or [""])[0]
        appid = (params.get("appid") or [""])[0]
        secret = (params.get("secret") or [""])[0]
        grant_type = (params.get("grant_type") or [""])[0]

        if not (code and appid and secret and grant_type == "authorization_code"):
            self._send(400, {"errcode": 41002, "errmsg": "invalid params"})
            return

        if code.startswith("invalid"):
            self._send(200, {"errcode": 40029, "errmsg": "invalid code"})
            return

        self._send(200, {
            "openid": f"mock-openid-{code}",
            "session_key": "mock-session-key",
            "unionid": "",
        })

    def _send(self, status: int, payload: dict):
        """以 JSON 格式发送 HTTP 响应。"""
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):  # 精简日志
        """覆盖默认日志：输出精简的一行访问日志到 stderr。"""
        sys.stderr.write("[mock-wechat] %s\n" % (fmt % args))


if __name__ == "__main__":
    server = HTTPServer((HOST, PORT), MockWechatHandler)
    print(f"mock 微信 code2session 服务已启动: http://{HOST}:{PORT}/sns/jscode2session")
    print("把 .env 的 WECHAT_API_BASE_URL 改为本地址后重启 FastAPI 即可联调")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
