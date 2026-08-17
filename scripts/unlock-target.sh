#!/usr/bin/env bash
# 打包前清理：移除 target 下文件只读/不可变属性（WSL / Linux 版）
set -e
ROOT="${ROOT:-$HOME/vibocoding/bysj/RuoYi-Vue}"
for dir in "$ROOT"/ruoyi-*/target; do
  [ -d "$dir" ] || continue
  find "$dir" -type f 2>/dev/null | while read -r f; do
    attr=$(lsattr "$f" 2>/dev/null || true)
    case "$attr" in *a*) chattr -a "$f" 2>/dev/null && echo "unlock: ${f#$ROOT/}";; esac
  done
done
echo "=== target 属性清理完成 ==="
