"""T0-6 健康检查测试（9.6）。"""
from app.api.health import health


def test_health_structure():
    result = health()
    assert result["status"] in ("UP", "DEGRADED", "DOWN")
    checks = result["checks"]
    # 9.6 规定的四类检查键
    for key in ("app", "mysql", "redis", "rag_index"):
        assert key in checks
        assert "status" in checks[key]


def test_health_endpoint_via_api(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("UP", "DEGRADED", "DOWN")
    assert set(body["checks"]) >= {"app", "mysql", "redis", "rag_index"}
