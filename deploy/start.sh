#!/usr/bin/env bash
# 川蜀大剧院 后端启动脚本
set -e
cd "$(dirname "$0")/../backend"
if [ -d ".venv" ]; then source .venv/bin/activate; fi
export PYTHONUNBUFFERED=1
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
