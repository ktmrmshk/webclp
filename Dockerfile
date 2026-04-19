# syntax=docker/dockerfile:1
# ビルドコンテキストはリポジトリ直下（webclip/）を想定: docker build -t webclip .
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install -r requirements.txt

COPY backend/ .

RUN mkdir -p /app/data

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

EXPOSE 3847

ENV PORT=3847 \
    DATABASE_URL=sqlite:////app/data/webclip.db

ENTRYPOINT ["/docker-entrypoint.sh"]
