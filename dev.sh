#!/usr/bin/env bash
# make shell can exit when error happen with -e
set -e
docker stack rm ft-dev || echo "There is no stack named ft-dev"
docker build --tag galahade/future-trading-dev .
docker stack deploy -c docker-compose.yml ft-dev