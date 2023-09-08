#!/usr/bin/env bash
# make shell can exit when error happen with -e
set -e

if [ -e main.py ]; then
    exec tini -- python3 main.py "$@"
fi

exec "$@"