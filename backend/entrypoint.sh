#!/bin/sh
# Entrypoint produzione: applica le migrazioni Alembic, poi avvia uvicorn.
#
# `set -e` fa fallire lo script se una migrazione fallisce, in modo che
# il container non parta con uno schema disallineato.

set -e

echo "→ Applico migrazioni Alembic..."
alembic upgrade head

echo "→ Avvio uvicorn su 0.0.0.0:${PORT:-8000}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
