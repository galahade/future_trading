#!/usr/bin/env bash
# make shell can exit when error happen with -e
set -e

if [ -e /app/main.py ]; then
    exec python3 /app/main.py
fi
exec "$@"