"""
Configurazione applicazione tramite variabili d'ambiente / .env file.

Tutte le impostazioni runtime sono qui. Niente magic strings hardcoded
nei moduli applicativi.
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Impostazioni(BaseSettings):
    """Impostazioni applicazione, popolate da environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="RISIKO_",
        case_sensitive=False,
    )

    # === Database ===

    #: URL di connessione async al DB.
    #: Postgres: postgresql+asyncpg://user:pass@host:5432/db
    #: SQLite (dev): sqlite+aiosqlite:///./risiko_review.db
    database_url: str = Field(
        default="sqlite+aiosqlite:///./risiko_review.db",
        description="URL di connessione async al database",
    )

    #: Mostra le query SQL nei log (utile in dev, OFF in produzione).
    database_echo: bool = False

    # === Storage video ===

    #: Cartella dove salvare i video caricati. Viene creata se non esiste.
    storage_video_path: Path = Field(
        default=Path("./storage_video"),
        description="Cartella per i file video delle partite",
    )

    #: Cartella dove salvare i frame estratti dai video (cache CV).
    storage_frame_path: Path = Field(
        default=Path("./storage_frame"),
        description="Cartella per i frame estratti dai video (cache analisi CV)",
    )

    #: Cartella dove estrarre i bundle mobile (M14 endpoint).
    #: Su Railway impostare a un volume persistente o S3 mount.
    storage_partite_path: Path = Field(
        default=Path("./storage_partite"),
        description="Cartella di destinazione per i bundle ZIP estratti dall'app mobile",
    )

    #: Dimensione massima upload video (default 10 GB).
    upload_max_size_mb: int = 10240

    # === Scheduler / Cleanup automatico ===

    #: Abilita lo scheduler in-process per il cleanup automatico bundle vecchi.
    #: In produzione (Railway) raccomandato True. In test/dev rimane False
    #: per evitare side-effects nelle suite pytest.
    scheduler_abilitato: bool = False

    #: Giorni dopo i quali un bundle non promosso viene cancellato automaticamente.
    bundle_cleanup_giorni: int = 30

    #: Ora del giorno (HH:MM, fuso server) per il cleanup. Default "03:00".
    bundle_cleanup_ora: str = "03:00"

    # === CV / Roboflow ===

    #: API key Roboflow. Se vuota, il backend usa `ClientCVMock` invece
    #: del client reale Roboflow (utile per dev/test).
    roboflow_api_key: str = ""

    #: Endpoint completo del modello Roboflow allenato. Esempio:
    #: `https://detect.roboflow.com/risiko-plancia/3` (project_id=risiko-plancia,
    #: version=3). Lasciare vuoto per usare il mock.
    roboflow_endpoint: str = ""

    #: Confidence minima sotto la quale Roboflow filtra le detection.
    roboflow_confidence_min: float = 0.5

    #: IoU threshold per NMS dedup di Roboflow.
    roboflow_iou_min: float = 0.5

    # === API ===

    #: Origin CORS consentite (frontend dev server).
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://localhost:3000"],
    )

    #: Prefisso comune di tutti gli endpoint API.
    api_prefix: str = "/api"

    # === Generale ===

    #: Modalità debug: errori dettagliati nelle response, autoreload.
    debug: bool = False

    #: Se True, all'avvio crea le tabelle mancanti via SQLAlchemy
    #: (utile in dev/test). In produzione DEVE essere False: lo schema
    #: è gestito esclusivamente da Alembic.
    auto_create_schema: bool = True

    @property
    def is_sqlite(self) -> bool:
        """True se sto usando SQLite invece di Postgres."""
        return self.database_url.startswith("sqlite")


# Istanza singleton, importata dagli altri moduli.
impostazioni = Impostazioni()
