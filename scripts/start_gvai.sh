#!/usr/bin/env bash
set -e

mkdir -p .gvai_run logs

echo "Starting dashboard server..."
nohup python -m http.server 8000 > logs/server.log 2>&1 &
echo $! > .gvai_run/server.pid

echo "Starting GV monitor..."
nohup env GVAI_MONITOR_INTERVAL=2 PYTHONPATH=. python scripts/monitor_real_gv.py > logs/monitor.log 2>&1 &
echo $! > .gvai_run/monitor.pid

sleep 2

echo ""
echo "GvAI is running."
echo "Open port 8000 → /dashboard/"
echo ""
echo "Logs:"
echo "tail -f logs/monitor.log"
echo "tail -f logs/server.log"
