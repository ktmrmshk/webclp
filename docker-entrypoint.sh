#!/bin/sh
set -e
mkdir -p /app/data
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-3847}"
