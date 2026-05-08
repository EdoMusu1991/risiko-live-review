# Dockerfile produzione per Risiko Live Review backend.
#
# Build multi-stage:
# 1. `builder` installa le dipendenze Python in un venv
# 2. `runtime` copia solo il venv + il codice, senza toolchain di build
#
# Ottimizzato per Railway / piattaforme container generic.
# Lo schema DB viene applicato all'avvio del container via `alembic upgrade head`
# (vedi entrypoint.sh).

# ============================================================================
# Stage 1: builder
# ============================================================================
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Dipendenze di sistema solo per il build (compilation gcc per psycopg, ecc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copia solo i file di metadata per sfruttare la cache layer
COPY pyproject.toml ./
COPY README.md ./

# Crea venv e installa dipendenze (senza dev)
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
RUN pip install --upgrade pip setuptools wheel

# Installa il pacchetto stesso (legge pyproject.toml)
COPY app ./app
COPY risiko_engine ./risiko_engine
COPY alembic ./alembic
COPY alembic.ini ./
RUN pip install -e .

# ============================================================================
# Stage 2: runtime
# ============================================================================
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}" \
    RISIKO_AUTO_CREATE_SCHEMA=false

WORKDIR /app

# ffprobe per estrazione metadata video (solo runtime, no toolchain)
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Crea utente non-root
RUN groupadd -r risiko && useradd -r -g risiko risiko

# Copia venv dal builder
COPY --from=builder /opt/venv /opt/venv

# Copia il codice applicativo
COPY --chown=risiko:risiko app ./app
COPY --chown=risiko:risiko risiko_engine ./risiko_engine
COPY --chown=risiko:risiko alembic ./alembic
COPY --chown=risiko:risiko alembic.ini ./
COPY --chown=risiko:risiko entrypoint.sh ./

RUN chmod +x ./entrypoint.sh

# Storage video: cartella scrivibile dall'utente non-root.
# In Railway il filesystem non è persistente — questa è una soluzione
# temporanea finché non si integra un object storage (S3/R2).
RUN mkdir -p /app/storage_video && chown -R risiko:risiko /app/storage_video

USER risiko

# Healthcheck (Railway lo usa per autodetect)
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl --fail http://localhost:${PORT:-8000}/healthz || exit 1

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
