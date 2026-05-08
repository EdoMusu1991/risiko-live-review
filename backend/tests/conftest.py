"""
Configurazione comune dei test pytest.

Convenzioni:
- DB di test in SQLite in-memory (pulito per ogni test).
- Client async httpx per chiamare gli endpoint senza server reale.
- Fixtures async: richiede `pytest-asyncio` con `asyncio_mode = auto`.
"""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.configurazione import Base, get_sessione_db
from app.main import app
from app.modelli import ColoreGiocatore
from app.schemi import GiocatorePartitaCreazione, PartitaCreazione


@pytest.fixture
async def engine_test() -> AsyncGenerator[object, None]:
    """Engine SQLite in-memory, condiviso nel singolo test."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def sessione_test(engine_test: object) -> AsyncGenerator[AsyncSession, None]:
    """Sessione DB pulita per il test."""
    factory = async_sessionmaker(bind=engine_test, expire_on_commit=False)  # type: ignore[arg-type]
    async with factory() as sess:
        yield sess


@pytest.fixture
async def client_test(
    engine_test: object,
) -> AsyncGenerator[AsyncClient, None]:
    """
    Client httpx async che chiama gli endpoint dell'app FastAPI in-process.

    Sostituisce la dependency `get_sessione_db` per usare il DB in-memory
    del test invece di quello reale.
    """
    factory = async_sessionmaker(bind=engine_test, expire_on_commit=False)  # type: ignore[arg-type]

    async def _override_get_sessione() -> AsyncGenerator[AsyncSession, None]:
        async with factory() as sess:
            try:
                yield sess
            except Exception:
                await sess.rollback()
                raise

    app.dependency_overrides[get_sessione_db] = _override_get_sessione

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    app.dependency_overrides.clear()


# === Helper di costruzione dati ===


def crea_dati_partita_minima() -> PartitaCreazione:
    """Costruisce un PartitaCreazione valido con 2 giocatori."""
    return PartitaCreazione(
        data_inizio=datetime(2026, 5, 7, 21, 0, tzinfo=UTC),
        luogo="Test Lab",
        note="Partita di test",
        giocatori=[
            GiocatorePartitaCreazione(
                nome="Edoardo",
                colore=ColoreGiocatore.ROSSO,
                ordine_seduta=1,
            ),
            GiocatorePartitaCreazione(
                nome="Marco",
                colore=ColoreGiocatore.BLU,
                ordine_seduta=2,
            ),
        ],
    )
