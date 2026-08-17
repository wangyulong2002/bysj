"""T0-5 验证：缺配置时给出明确报错（可独立运行，不启动 FastAPI）。

依据设计报告 9.3：启动时校验必填项，缺失给出明确报错。
config.py 在模块级执行 get_settings() -> validate_required()，
因此用子进程隔离两个场景分别验证：
  1) 缺 MYSQL_PASS / JWT_SECRET -> import 即抛 RuntimeError，报错含缺失项名
  2) 配置正常             -> import 成功
"""
import os
import subprocess
import sys

SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable

IMPORT_CODE = (
    "import app.core.config; "
    "print('IMPORT_OK:', app.core.config.settings.APP_NAME)"
)


def run_import(extra_env: dict) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env.update(extra_env)  # 环境变量优先级高于 server/.env
    return subprocess.run(
        [PY, "-c", IMPORT_CODE],
        cwd=SERVER_DIR,
        env=env,
        capture_output=True,
        text=True,
    )


def test_missing_required():
    proc = run_import({"MYSQL_PASS": "", "JWT_SECRET": "please-change-me"})
    assert proc.returncode != 0, "缺配置时不应成功启动"
    assert "缺少必要配置项" in proc.stderr, f"报错不够明确: {proc.stderr[-500:]}"
    assert "MYSQL_PASS" in proc.stderr and "JWT_SECRET" in proc.stderr, \
        f"报错未列出缺失项: {proc.stderr[-500:]}"
    msg = [l for l in proc.stderr.splitlines() if "缺少必要配置项" in l][-1]
    print("[PASS] 缺配置时明确报错:", msg)
    print("       提示指向 server/.env（参考 .env.example）✓")


def test_normal_config_ok():
    proc = run_import({"MYSQL_PASS": "123456", "JWT_SECRET": "real-secret-abc"})
    assert proc.returncode == 0, f"正常配置不应失败: {proc.stderr[-500:]}"
    assert "IMPORT_OK" in proc.stdout
    print("[PASS] 正常配置启动通过:", proc.stdout.strip().splitlines()[-1])


if __name__ == "__main__":
    test_missing_required()
    test_normal_config_ok()
    print("T0-5 配置缺项报错验证通过。")
