#!/usr/bin/env bash
# make shell can exit when error happen with -e
set -e

if [ -e /app/main.py ]; then
    python3 /app/main.py; exec "$@"
fi
exec "$@"