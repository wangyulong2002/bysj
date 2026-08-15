#!/usr/bin/env bash
# 打包前清理：移除 RuoYi-Vue 各模块 target 下文件的 append-only 属性（沙箱自动附加导致 Maven 无法覆盖写入）
set -e
ROOT="F:/PythonProject/vibocoding/bysj/RuoYi-Vue"
for dir in "$ROOT"/ruoyi-*/target; do
  [ -d "$dir" ] || continue
  find "$dir" -type f 2>/dev/null | while read -r f; do
    attr=$(lsattr "$f" 2>/dev/null || true)
    case "$attr" in *a*) chattr -a "$f" 2>/dev/null && echo "unlock: ${f#$ROOT/}";; esac
  done
done
echo "=== target 属性清理完成 ==="
