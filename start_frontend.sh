#!/usr/bin/env bash
# Skyline — 前端启动脚本
# 用法：在项目根目录 ~/skyline 执行 bash start_frontend.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

echo "▶  切换到 frontend 目录: $FRONTEND_DIR"
cd "$FRONTEND_DIR"

echo "▶  启动 Skyline Vite 开发服务器 (0.0.0.0:5173) ..."
exec npm run dev
