#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."

if [[ ! -f .env ]]; then
    printf '缺少 deploy/.env。请在 deploy 目录执行 cp .env.example .env。\n' >&2
    exit 1
fi

docker compose --profile '*' down -v
exec bash scripts/init.sh
