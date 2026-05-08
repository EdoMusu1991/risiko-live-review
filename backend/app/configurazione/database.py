"""
Connessione database e sessioni SQLAlchemy 2 in modalità async.

L'engine è creato una volta sola al boot dell'app. Le sessioni vengono
fornite via dependency injection di FastAPI (`get_sessione_db`).
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.configurazione.impostazioni import impostazioni


class Base(DeclarativeBase):
    """Classe base per tutti i modelli ORM."""


def _crea_engine() -> AsyncEngine:
    """Crea l'engine async coerente con il database scelto."""
    return create_async_engine(
        impostazioni.database_url,
        echo=impostazioni.database_echo,
        # SQLite richiede check_same_thread=False per uso async
        connect_args={"check_same_thread": False} if impostazioni.is_sqlite else {},
    )


engine: AsyncEngine = _crea_engine()

#: Factory di sessioni async. `expire_on_commit=False` permette di accedere
#: agli oggetti dopo il commit senza riemettere query.
sessione_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_sessione_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency FastAPI che fornisce una sessione DB async.

    Uso negli endpoint:
        async def endpoint(db: AsyncSession = Depends(get_sessione_db)):
            ...
    """
    async with sessione_factory() as sessione:
        try:
            yield sessione
        except Exception:
            await sessione.rollback()
            raise
        finally:
            await sessione.close()
