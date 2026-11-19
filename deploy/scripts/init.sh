#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."

if [[ ! -f .env ]]; then
    printf '缺少 deploy/.env。请在 deploy 目录执行 cp .env.example .env。\n' >&2
    exit 1
fi

docker compose up -d postgres redis minio emqx

printf '等待 PostgreSQL 就绪…\n'
deadline=$((SECONDS + 120))
until docker compose exec -T postgres sh -c \
    'pg_isready -h 127.0.0.1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null 2>&1; do
    if (( SECONDS >= deadline )); then
        printf '等待 PostgreSQL 超时。请查看 docker compose logs postgres。\n' >&2
        exit 1
    fi
    sleep 2
done

docker compose build backend frontend
# The backend image entrypoint applies migrations before this command.
docker compose run --rm --no-deps backend python -m app.db.seed
docker compose up -d backend frontend
