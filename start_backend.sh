#!/usr/bin/env bash
# Skyline — 后端启动脚本
# 用法：在项目根目录 ~/skyline 执行 bash start_backend.sh
# 原因：main.py 使用绝对包路径导入（from routers.xxx），
#       必须将 backend/ 作为工作目录，才能让 Python 正确解析模块。

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"

echo "▶  切换到 backend 目录: $BACKEND_DIR"
cd "$BACKEND_DIR"

echo "▶  启动 Skyline FastAPI 后端 (0.0.0.0:8000) ..."
exec uvicorn main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --reload \
  --log-level info
