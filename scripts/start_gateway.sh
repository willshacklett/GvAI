#!/usr/bin/env bash
set -e

python -m pip install -r gateway/requirements.txt

echo "Starting GvAI Gateway on port 8010..."
nohup python -m uvicorn gateway.app:app --host 0.0.0.0 --port 8010 > logs/gateway.log 2>&1 &
echo $! > .gvai_run/gateway.pid

echo "GvAI Gateway running on port 8010"
echo "Health: /health"
echo "GV state: /gv/state"
echo "Chat: POST /chat"
