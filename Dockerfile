# syntax = docker/dockerfile:1.2
FROM python:3.10-bullseye

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt
ENV TZ Asia/Shanghai

COPY . .
CMD python3 main.py


