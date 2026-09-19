#!/bin/bash
# proofread.sh 入口 — 术语与格式校验（实际实现见 proofread.py）
# 用法:
#   bash .project/proofread.sh docs/xxx.md   # 单文件
#   bash .project/proofread.sh --all         # 全部
#   bash .project/proofread.sh --all --strict
set -eu
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/proofread.py" "$@"
