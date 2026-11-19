#!/bin/sh
set -eu

python -m alembic -c /srv/alembic.ini upgrade head
exec "$@"
