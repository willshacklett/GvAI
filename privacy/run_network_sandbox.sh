#!/usr/bin/env bash
set -euo pipefail

if [[ $# -eq 0 ]]; then
  echo "usage: $0 COMMAND [ARGS...]" >&2
  exit 64
fi

exec unshare \
  --user \
  --map-root-user \
  --net \
  -- \
  sh -c '
    set -eu

    # The sandbox receives a fresh network namespace.
    # Enable loopback when iproute2 is available.
    # Without it, loopback remains down; there is still
    # no route or external network interface.
    if command -v ip >/dev/null 2>&1; then
      ip link set lo up
    fi

    exec "$@"
  ' sh "$@"
