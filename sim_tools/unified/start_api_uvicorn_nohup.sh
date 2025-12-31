#!/usr/bin/env bash
set -euo pipefail

VENV="/opt/venv_torch"
APP_DIR="/workspace/unified"
PORT="${PORT:-8000}"
LOG="${APP_DIR}/uvicorn_${PORT}.log"
PID="${APP_DIR}/uvicorn_${PORT}.pid"

# 1) uvicorn/fastapi 없으면 설치
${VENV}/bin/python -c "import uvicorn, fastapi" >/dev/null 2>&1 || \
  ${VENV}/bin/python -m pip install -U uvicorn fastapi

# 2) 이미 떠있으면 종료(중복 실행 방지)
if [ -f "$PID" ] && ps -p "$(cat "$PID")" >/dev/null 2>&1; then
  echo "Already running: PID=$(cat "$PID")"
  exit 0
fi

cd "$APP_DIR"
mkdir -p "${APP_DIR}/outputs"

nohup env OUTPUTS_DIR="${APP_DIR}/outputs" \
  ${VENV}/bin/python -m uvicorn api_server:app --host 0.0.0.0 --port "$PORT" \
  > "$LOG" 2>&1 &

echo $! > "$PID"
echo "Started: PID=$(cat "$PID"), log=$LOG"