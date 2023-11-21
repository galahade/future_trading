#!/usr/bin/env bash
# make shell can exit when error happen with -e
set -e
docker stack rm ft-backtest-black
docker build --tag galahade/future-trading-backtest .
docker stack deploy -c docker-compose-backtest.yml ft-backtest-black