#! /usr/bin/env bash

set -e
set -x

(cd ../frontend && bun install --frozen-lockfile && bun run build)

python -m docling.cli.tools models download layout tableformer rapidocr -o docling-models

python -m alembic upgrade head
python app/initial_data.py
