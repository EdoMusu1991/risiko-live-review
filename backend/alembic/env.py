"""
Environment Alembic.

Configurato in modalità **online async** (Alembic chiama in modo
sincrono ma usa un engine async sotto). Legge `DATABASE_URL` dalle
impostazioni dell'app.

Nota: per via del supporto async, le migrazioni `data` (che eseguono
`op.execute(...)`) usano la connessione passata da `run_migrations_online`.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.configurazione.database import Base
from app.configurazione.impostazioni import impostazioni

# Importa TUTTI i modelli per registrarli su Base.metadata
# (altrimenti l'autogenerate non li vede)
from app.modelli import partita as _modelli_partita  # noqa: F401

# Config Alembic
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Sovrascrive l'URL del database con quello delle impostazioni dell'app
config.set_main_option("sqlalchemy.url", impostazioni.database_url)

# Schema target per autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Esegue le migrazioni in modalità "offline" (genera SQL senza connettersi).

    Utile per produrre script SQL che un DBA può applicare a mano.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Hook sincrono che Alembic usa per eseguire le migrazioni."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        # Render in formato batch automatico: utile per SQLite (limitato sui
        # vincoli ALTER TABLE) e innocuo su Postgres.
        render_as_batch=connection.dialect.name == "sqlite",
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Crea engine async e applica le migrazioni."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Modalità online: si connette al DB e applica le migrazioni."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
