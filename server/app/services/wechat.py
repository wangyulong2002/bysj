"""微信小程序服务（B-01 / T1-4）：code2session 换 openid。

- 调用微信官方 `GET /sns/jscode2session`（配置项 WECHAT_API_BASE_URL，9.3）。
- 联调可把 `WECHAT_API_BASE_URL` 指向本地 mock 服务（B-01），无需真实 AppID。
- 失败统一抛 BizError（4001 凭证无效 / 5000 微信服务不可用）。
"""
import logging

import httpx

from app.core.config import settings
from app.core.errors import BizError, ErrorCode

logger = logging.getLogger("campus.wechat")

WECHAT_HTTP_TIMEOUT = 5.0  # 秒


def code2session(code: str) -> dict:
    """微信登录 code 换取 openid（code2session）。

    返回微信响应（含 `openid`/`session_key`）；失败抛业务异常：
    - 未配置 AppID/Secret → 5000（明确提示配置缺失）
    - 网络/HTTP 错误 → 5000（微信服务不可用）
    - 微信返回 errcode → 4001（凭证无效或已过期）
    """
    if not settings.WECHAT_APPID or not settings.WECHAT_SECRET:
        logger.error("微信登录未配置：缺少 WECHAT_APPID / WECHAT_SECRET（9.3，T1-4）")
        raise BizError(ErrorCode.SERVER_ERROR, "微信登录未配置，请联系管理员")

    url = f"{settings.WECHAT_API_BASE_URL}/sns/jscode2session"
    params = {
        "appid": settings.WECHAT_APPID,
        "secret": settings.WECHAT_SECRET,
        "js_code": code,
        "grant_type": "authorization_code",
    }
    try:
        resp = httpx.get(url, params=params, timeout=WECHAT_HTTP_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPError as exc:  # 网络/超时/非 2xx
        logger.warning("微信 code2session 请求失败: %s", exc)
        raise BizError(ErrorCode.SERVER_ERROR, "微信服务暂时不可用，请稍后再试") from exc
    except ValueError as exc:  # 响应非 JSON
        logger.warning("微信 code2session 响应解析失败: %s", exc)
        raise BizError(ErrorCode.SERVER_ERROR, "微信服务响应异常，请稍后再试") from exc

    if data.get("errcode"):
        logger.warning(
            "微信 code2session 业务错误: errcode=%s errmsg=%s",
            data.get("errcode"), data.get("errmsg"),
        )
        raise BizError(ErrorCode.PARAM_ERROR, "微信登录凭证无效或已过期，请重新授权")

    openid = data.get("openid")
    if not openid:
        logger.warning("微信 code2session 未返回 openid: %s", data)
        raise BizError(ErrorCode.SERVER_ERROR, "微信登录失败，请重试")

    return data
