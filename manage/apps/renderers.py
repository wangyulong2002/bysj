"""管理端统一响应 Renderer + 异常处理（6.4：返回格式与应用端一致 { code, message, data }）。

- 2xx 成功 → `{ code: 0, message: "ok", data }`
- 业务/系统异常 → `{ code, message, data: null }`（错误码对齐 6.1）
- 已带 code/message/data 的 dict 原样透传（供 ViewSet 返回业务 code，如 4091 排课冲突）
"""
from rest_framework import status
from rest_framework.renderers import JSONRenderer


def _extract_message(data) -> str:
    """从 DRF 异常 detail 中提取用户可读消息。"""
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, (list, tuple)) and v:
                msg = str(v[0])
            elif isinstance(v, dict):
                msg = _extract_message(v)
            else:
                msg = str(v)
            # 去掉 DRF 包裹的字段名（如 "class_code: 班级编码不能为空"）
            return msg.replace(f"{k}: ", "", 1)
        return "参数错误"
    if isinstance(data, (list, tuple)):
        return _extract_message(data[0]) if data else "参数错误"
    return str(data) or "参数错误"


def map_http_status_to_code(http_status: int) -> int:
    """DRF 异常 HTTP 状态 → 统一业务错误码（6.1）。"""
    mapping = {
        status.HTTP_400_BAD_REQUEST: 4001,
        status.HTTP_401_UNAUTHORIZED: 4011,
        status.HTTP_403_FORBIDDEN: 4031,
        status.HTTP_404_NOT_FOUND: 4001,
        status.HTTP_409_CONFLICT: 4091,
        status.HTTP_429_TOO_MANY_REQUESTS: 4291,
    }
    return mapping.get(http_status, 5000)


class ApiJSONRenderer(JSONRenderer):
    """统一响应渲染器：所有 /admin/api/** 响应包成 { code, message, data }。"""

    def render(self, data, accepted_media_type=None, renderer_context=None):
        """渲染入口：2xx 包装为 { code:0, message:"ok", data }；异常映射业务错误码。"""
        if renderer_context is None:
            return super().render(data, accepted_media_type, renderer_context)
        response = renderer_context.get("response")
        if isinstance(data, dict) and {"code", "message", "data"} <= set(data):
            rendered = data
        elif response is not None and 200 <= response.status_code < 300:
            rendered = {"code": 0, "message": "ok", "data": data}
        else:
            rendered = {
                "code": map_http_status_to_code(response.status_code if response else 500),
                "message": _extract_message(data),
                "data": None,
            }
        return super().render(rendered, accepted_media_type, renderer_context)
