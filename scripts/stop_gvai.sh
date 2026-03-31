#!/usr/bin/env bash

if [ -f .gvai_run/server.pid ]; then
  kill $(cat .gvai_run/server.pid) 2>/dev/null || true
  rm .gvai_run/server.pid
fi

if [ -f .gvai_run/monitor.pid ]; then
  kill $(cat .gvai_run/monitor.pid) 2>/dev/null || true
  rm .gvai_run/monitor.pid
fi

echo "GvAI stopped."
