#!/usr/bin/env bash
set -e

if [ -f .gvai_run/gateway.pid ]; then
  PID=$(cat .gvai_run/gateway.pid || true)
  if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
    kill "$PID" 2>/dev/null || true
    echo "Stopped gateway ($PID)"
  fi
  rm -f .gvai_run/gateway.pid
fi

echo "Gateway stopped."
