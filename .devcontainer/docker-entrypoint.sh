#!/usr/bin/env bash
echo "Start run pipenv install"
cd /workspaces/future_trading || exec "$@"
pipenv install --dev
pipenv requirements > requirements.txt
exec "$@"