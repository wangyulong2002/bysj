#!/usr/bin/env bash
# 若依后端一键构建脚本（WSL / Linux 版）
set -e
ROOT="$HOME/vibocoding/bysj/RuoYi-Vue"
cd "$ROOT"
echo "=== [1/2] 清空各模块 target 目录 ==="
python3 - "$ROOT" <<'PY'
import os, sys
root = sys.argv[1]
for mod in ['ruoyi-common','ruoyi-system','ruoyi-framework','ruoyi-quartz','ruoyi-generator','ruoyi-admin']:
    tgt = os.path.join(root, mod, 'target')
    if not os.path.exists(tgt):
        continue
    for r, dirs, files in os.walk(tgt, topdown=False):
        for f in files:
            try: os.remove(os.path.join(r, f))
            except Exception as e: print('skip', os.path.join(r, f), e)
        for d in dirs:
            try: os.rmdir(os.path.join(r, d))
            except Exception: pass
    try: os.rmdir(tgt)
    except Exception: pass
    print('cleaned:', mod)
print('target cleanup done')
PY
echo "=== [2/2] Maven 打包 ruoyi-admin (skipTests) ==="
"$HOME/vibocoding/bysj/scripts/mvnw-custom.sh" -pl ruoyi-admin -am package -DskipTests
echo "=== BUILD DONE ==="
