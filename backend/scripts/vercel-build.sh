#! /usr/bin/env bash

set -e
set -x

(cd ../frontend && bun install --frozen-lockfile && bun run build)

python -m alembic upgrade head
