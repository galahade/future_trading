# syntax = docker/dockerfile:1.4
FROM --platform=$BUILDPLATFORM python:3.11-bullseye AS builder

# Why use Tini https://github.com/krallin/tini/issues/8
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    # Remove imagemagick due to https://security-tracker.debian.org/tracker/CVE-2019-10131
    && apt-get purge -y imagemagick imagemagick-6-common \
    && apt-get -y install --no-install-recommends tini

WORKDIR /app
COPY requirements.txt requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip3 install -r requirements.txt
ENV TZ Asia/Shanghai
COPY . .
ENTRYPOINT ["entrypoint.sh"]
