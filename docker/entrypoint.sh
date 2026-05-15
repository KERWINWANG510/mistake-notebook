#!/bin/bash
set -euo pipefail

cd /app

uvicorn app.main:app --host 127.0.0.1 --port 8000 &
UVICORN_PID=$!

for _ in $(seq 1 60); do
  if (true >/dev/tcp/127.0.0.1/8000) 2>/dev/null; then
    break
  fi
  sleep 0.2
done

nginx -g "daemon off;" &
NGINX_PID=$!

cleanup() {
  kill -TERM "$UVICORN_PID" 2>/dev/null || true
  kill -TERM "$NGINX_PID" 2>/dev/null || true
  wait "$UVICORN_PID" 2>/dev/null || true
  wait "$NGINX_PID" 2>/dev/null || true
}
trap cleanup TERM INT

wait "$NGINX_PID"
