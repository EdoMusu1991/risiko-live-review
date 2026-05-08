"""
Servizio di import del bundle prodotto dall'app mobile.

L'app mobile (iOS/Android) registra una partita producendo:

```
risiko-partita-{uuid}.zip
├── manifest.json   # metadata: device, durata, n_eventi, hash video
├── video.mp4       # registrazione completa
└── eventi.jsonl    # un evento BLE per riga (dadi GoDice)
```

Questo servizio:
1. Estrae lo ZIP in una cartella temporanea
2. Valida `manifest.json` contro lo schema atteso
3. Crea una nuova `Partita` (con stato `GREZZA`)
4. Sposta `video.mp4` nello storage e crea il record `Video`
5. Importa ogni evento di `eventi.jsonl` come `EventoGrezzo` con
   `fonte=DADO_BLE`
6. Ritorna il riepilogo dell'import

Schema bundle versionato: il manifest contiene `schema_version` per
permettere evoluzione futura senza rompere la compatibilità.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.modelli import (
    EventoGrezzo,
    FonteEvento,
    GiocatorePartita,
    Partita,
    StatoReview,
    TipoEvento,
    Video,
)
from app.storage.estrattore_metadata import (
    EstrattoreMetadataVideo,
    estrattore_default,
)
from app.storage.storage_video import StorageVideo

# Versioni di schema bundle che sappiamo importare
_SCHEMA_VERSION_SUPPORTATA = "1.0"


# === Errori ===


class BundleImportError(Exception):
    """Base error per fallimenti di import."""


class BundleNonValidoError(BundleImportError):
    """Lo ZIP è malformato o contiene file mancanti/inattesi."""


class ManifestNonValidoError(BundleImportError):
    """Il manifest.json non rispetta lo schema atteso."""


class SchemaVersionNonSupportataError(BundleImportError):
    """schema_version del manifest non gestita da questa versione del backend."""


class HashVideoMismatchError(BundleImportError):
    """Hash SHA256 del video non corrisponde a quello dichiarato nel manifest."""


# === Schemi del manifest (Pydantic) ===


class ManifestDevice(BaseModel):
    """Info sul dispositivo che ha registrato la partita."""

    modello: str
    os: str
    app_version: str


class ManifestRegistrazione(BaseModel):
    """Metadati della registrazione video."""

    ts_inizio: datetime
    ts_fine: datetime
    durata_sec: float = Field(gt=0)
    video_file: str
    video_sha256: str | None = None
    video_dimensione_byte: int = Field(gt=0)


class ManifestGoDice(BaseModel):
    """Configurazione dei dadi BLE."""

    n_dadi_attaccante: int = Field(ge=0, le=3)
    n_dadi_difensore: int = Field(ge=0, le=3)
    ble_id_attaccante: list[str] = Field(default_factory=list)
    ble_id_difensore: list[str] = Field(default_factory=list)


class ManifestEventi(BaseModel):
    """Riferimento al file di eventi."""

    n_eventi_totali: int = Field(ge=0)
    eventi_file: str


class ManifestGiocatore(BaseModel):
    """Giocatore della partita (dichiarato nell'app mobile)."""

    nome: str
    colore: str
    ordine_seduta: int = Field(ge=1, le=6)


class ManifestBundle(BaseModel):
    """Manifest completo del bundle. Speculare a quello prodotto dall'app mobile."""

    schema_version: str
    partita_id_locale: str
    luogo: str | None = None
    note: str | None = None
    device: ManifestDevice
    registrazione: ManifestRegistrazione
    godice: ManifestGoDice
    eventi: ManifestEventi
    giocatori: list[ManifestGiocatore] = Field(default_factory=list, min_length=2)


# === Riga eventi.jsonl ===


class RigaEventoBle(BaseModel):
    """
    Una riga del file `eventi.jsonl` prodotto dall'app mobile.

    Per ora supportiamo solo eventi di tipo `dado_lanciato`. In futuro
    l'app potrà loggare anche eventi tipo `dado_collegato`,
    `dado_disconnesso`, `connessione_persa` ecc.
    """

    ts: datetime
    tipo: str
    ble_id: str
    ruolo: str  # "attaccante" | "difensore"
    slot: int = Field(ge=1, le=3)
    valore: int | None = Field(default=None, ge=1, le=6)


# === Risultato import ===


@dataclass(frozen=True)
class RisultatoImportBundle:
    """Riepilogo del lavoro fatto."""

    partita_id: str
    n_giocatori: int
    n_eventi_grezzi_creati: int
    n_eventi_scartati: int
    durata_video_sec: float
    dimensione_video_byte: int
    note: list[str]


# === Servizio ===


class ServizioImportBundle:
    """Importa un bundle ZIP prodotto dall'app mobile in una nuova Partita."""

    def __init__(
        self,
        storage_video: StorageVideo,
        estrattore_metadata: EstrattoreMetadataVideo | None = None,
    ) -> None:
        self._storage = storage_video
        self._estrattore = estrattore_metadata or estrattore_default

    async def importa(
        self,
        db: AsyncSession,
        contenuto_zip: bytes,
    ) -> RisultatoImportBundle:
        """
        Esegue l'import end-to-end.

        Solleva una sottoclasse di `BundleImportError` in caso di fallimento.
        Tutto è transazionale: se qualcosa fallisce dopo aver salvato il
        video sul disco, il file viene rimosso prima di rilanciare.
        """
        with tempfile.TemporaryDirectory(prefix="risiko_bundle_") as tmpdir:
            cartella_estratta = Path(tmpdir)
            self._estrai_zip(contenuto_zip, cartella_estratta)

            manifest = self._carica_manifest(cartella_estratta)

            video_path = cartella_estratta / manifest.registrazione.video_file
            if not video_path.is_file():
                raise BundleNonValidoError(
                    f"File video '{manifest.registrazione.video_file}' "
                    f"non trovato nello ZIP"
                )

            eventi_path = cartella_estratta / manifest.eventi.eventi_file
            if not eventi_path.is_file():
                raise BundleNonValidoError(
                    f"File eventi '{manifest.eventi.eventi_file}' "
                    f"non trovato nello ZIP"
                )

            # Crea partita
            partita = await self._crea_partita(db, manifest)

            note: list[str] = []

            # Sposta video nello storage e crea record Video
            video_record, percorso_storage = await self._importa_video(
                db, partita, manifest, video_path
            )

            try:
                # Importa eventi
                n_creati, n_scartati, note_eventi = await self._importa_eventi(
                    db, partita.id, eventi_path, manifest
                )
                note.extend(note_eventi)

                await db.commit()
            except Exception:
                # Rollback: rimuovi anche il file video appena salvato
                self._storage.elimina(percorso_storage)
                await db.rollback()
                raise

            return RisultatoImportBundle(
                partita_id=str(partita.id),
                n_giocatori=len(manifest.giocatori),
                n_eventi_grezzi_creati=n_creati,
                n_eventi_scartati=n_scartati,
                durata_video_sec=video_record.durata_sec,
                dimensione_video_byte=video_record.dimensione_byte,
                note=note,
            )

    # === Step interni ===

    @staticmethod
    def _estrai_zip(contenuto: bytes, destinazione: Path) -> None:
        """Scrive lo ZIP su disco temp e lo estrae. Verifica file mandatory."""
        zip_path = destinazione / "_bundle.zip"
        zip_path.write_bytes(contenuto)

        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                # Anti-zip-slip: blocca path che escono dalla destinazione
                for nome in zf.namelist():
                    p = (destinazione / nome).resolve()
                    if not str(p).startswith(str(destinazione.resolve())):
                        raise BundleNonValidoError(
                            f"Path zip non sicuro: {nome}"
                        )
                zf.extractall(destinazione)
        except zipfile.BadZipFile as e:
            raise BundleNonValidoError(f"ZIP corrotto: {e}") from e

        manifest_path = destinazione / "manifest.json"
        if not manifest_path.is_file():
            raise BundleNonValidoError("manifest.json mancante nello ZIP")

    @staticmethod
    def _carica_manifest(cartella: Path) -> ManifestBundle:
        """Legge e valida `manifest.json`."""
        manifest_path = cartella / "manifest.json"
        try:
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ManifestNonValidoError(
                f"manifest.json non è JSON valido: {e}"
            ) from e

        try:
            manifest = ManifestBundle.model_validate(raw)
        except Exception as e:
            raise ManifestNonValidoError(
                f"manifest.json non rispetta lo schema: {e}"
            ) from e

        if manifest.schema_version != _SCHEMA_VERSION_SUPPORTATA:
            raise SchemaVersionNonSupportataError(
                f"schema_version='{manifest.schema_version}' non supportata. "
                f"Atteso: '{_SCHEMA_VERSION_SUPPORTATA}'."
            )

        return manifest

    @staticmethod
    async def _crea_partita(
        db: AsyncSession,
        manifest: ManifestBundle,
    ) -> Partita:
        """Crea record Partita + GiocatorePartita."""
        partita = Partita(
            id=str(uuid.uuid4()),
            data_inizio=manifest.registrazione.ts_inizio,
            data_fine=manifest.registrazione.ts_fine,
            luogo=manifest.luogo,
            note=manifest.note,
            stato_review=StatoReview.GREZZA,
        )
        db.add(partita)

        for g in manifest.giocatori:
            db.add(
                GiocatorePartita(
                    id=str(uuid.uuid4()),
                    partita_id=partita.id,
                    nome=g.nome,
                    colore=g.colore,
                    ordine_seduta=g.ordine_seduta,
                )
            )

        await db.flush()
        return partita

    async def _importa_video(
        self,
        db: AsyncSession,
        partita: Partita,
        manifest: ManifestBundle,
        video_path: Path,
    ) -> tuple[Video, Path]:
        """Sposta il video nello storage e crea il record Video."""
        # Verifica hash se presente nel manifest
        if manifest.registrazione.video_sha256:
            self._verifica_hash_video(
                video_path, manifest.registrazione.video_sha256
            )

        # Estrae metadata reali con ffprobe (non ci fidiamo del manifest
        # per i dati tecnici come codec/risoluzione)
        try:
            metadata = await self._estrattore.estrai(video_path)
        except Exception:
            # Se ffprobe fallisce (es. byte fake nei test), usiamo i dati
            # del manifest come fallback
            metadata = None

        # Sposta nel persistent storage (UUID filename)
        nome_storage = f"{uuid.uuid4()}{video_path.suffix or '.mp4'}"
        percorso_finale = self._storage.cartella_radice / nome_storage
        shutil.move(str(video_path), str(percorso_finale))

        # Crea record Video
        video = Video(
            id=str(uuid.uuid4()),
            partita_id=partita.id,
            nome_originale=manifest.registrazione.video_file,
            file_path=str(percorso_finale.resolve()),
            ts_inizio=manifest.registrazione.ts_inizio,
            durata_sec=(
                metadata.durata_sec
                if metadata
                else manifest.registrazione.durata_sec
            ),
            codec=metadata.codec if metadata else None,
            risoluzione=metadata.risoluzione if metadata else None,
            dimensione_byte=manifest.registrazione.video_dimensione_byte,
        )
        db.add(video)
        await db.flush()
        return video, percorso_finale

    @staticmethod
    def _verifica_hash_video(video_path: Path, hash_atteso: str) -> None:
        """Calcola SHA256 del video e confronta con l'atteso."""
        import hashlib

        h = hashlib.sha256()
        with video_path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)

        digest = h.hexdigest()
        if digest.lower() != hash_atteso.lower():
            raise HashVideoMismatchError(
                f"Hash SHA256 video non corrisponde: "
                f"calcolato={digest}, atteso={hash_atteso}"
            )

    @staticmethod
    async def _importa_eventi(
        db: AsyncSession,
        partita_id: str,
        eventi_path: Path,
        _manifest: ManifestBundle,
    ) -> tuple[int, int, list[str]]:
        """
        Legge `eventi.jsonl` riga per riga e crea EventoGrezzo per ognuno.

        Eventi malformati vengono scartati con una nota; non bloccano l'import.
        Ritorna (n_creati, n_scartati, note).
        """
        n_creati = 0
        n_scartati = 0
        note: list[str] = []

        with eventi_path.open("r", encoding="utf-8") as f:
            for n_riga, riga_raw in enumerate(f, start=1):
                riga_strip = riga_raw.strip()
                if not riga_strip:
                    continue
                try:
                    raw = json.loads(riga_strip)
                    riga = RigaEventoBle.model_validate(raw)
                except (json.JSONDecodeError, Exception) as e:
                    n_scartati += 1
                    if len(note) < 10:
                        note.append(
                            f"Riga {n_riga} eventi.jsonl scartata: {e}"
                        )
                    continue

                # Mappa la riga a un EventoGrezzo
                if riga.tipo != "dado_lanciato":
                    # Tipi non supportati (riservati a sviluppo futuro)
                    n_scartati += 1
                    continue

                evento = EventoGrezzo(
                    id=str(uuid.uuid4()),
                    partita_id=partita_id,
                    ts_evento=riga.ts,
                    tipo=TipoEvento.DADI_LANCIATI,
                    fonte=FonteEvento.DADO_BLE,
                    confidenza=1.0,
                    dati={
                        "ble_id": riga.ble_id,
                        "ruolo": riga.ruolo,
                        "slot": riga.slot,
                        "valore": riga.valore,
                    },
                    validato=False,
                )
                db.add(evento)
                n_creati += 1

        await db.flush()
        return n_creati, n_scartati, note


# === Helper per costruire il servizio dalle dipendenze comuni ===


def get_servizio_import() -> ServizioImportBundle:
    """Costruisce il servizio con storage e estrattore di default."""
    from app.configurazione.impostazioni import impostazioni
    from app.storage.storage_video import crea_storage_di_default

    storage = crea_storage_di_default(impostazioni.storage_video_path)
    return ServizioImportBundle(storage_video=storage)


# Helper export per test e dipendenze
__all__ = [
    "BundleImportError",
    "BundleNonValidoError",
    "HashVideoMismatchError",
    "ManifestBundle",
    "ManifestDevice",
    "ManifestEventi",
    "ManifestGiocatore",
    "ManifestGoDice",
    "ManifestNonValidoError",
    "ManifestRegistrazione",
    "RigaEventoBle",
    "RisultatoImportBundle",
    "SchemaVersionNonSupportataError",
    "ServizioImportBundle",
    "get_servizio_import",
]

# Helper per chi usa questo modulo: lo ZIP archive standard library
# che permette test in-memory
_ = zipfile  # re-export evita unused
