"""
Servizio applicativo che orchestra la pipeline CV completa:
estrazione frame → raddrizzamento → inferenza modello CV → persistenza.

Architettura "client pluggabile":
- `ClientCV` (ABC): contratto astratto del modello CV.
- `ClientCVMock`: genera detection deterministiche dallo stato motore
  (utile per sviluppo UI e test).
- `ClientCVRoboflow`: implementazione reale per l'API Roboflow
  hosted/self-hosted, da configurare quando il modello sara' addestrato.

Quando l'altra sessione (Roboflow) produrra' il modello, basta:
1. Configurare `ROBOFLOW_API_KEY` e `ROBOFLOW_PROJECT_VERSION` nelle
   impostazioni del backend.
2. Sostituire l'iniezione di `ClientCVMock` con `ClientCVRoboflow` in
   `crea_servizio_cv_default()`.

Tutto il resto (persistenza, endpoint, frontend, schema) rimane invariato.

Use case principale:
    servizio = crea_servizio_cv_default(...)
    inferenze = await servizio.analizza_evento(db, partita_id, evento_id)
    # → estrae frame → raddrizza → inferisce → salva → ritorna list[InferenzaCV]
"""

from __future__ import annotations

import hashlib
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modelli import (
    EventoValidato,
    InferenzaCV,
    StatoPartitaRicostruito,
)
from app.servizi.discrepanze_servizio import stato_motore_da_snapshot
from app.servizi.raddrizzamento_servizio import (
    OmografiaNonCalibrataError,
    ServizioRaddrizzamento,
)

# === Tipi ===


TipoPedinaCv = Literal["carro_piccolo", "carro_medio", "carro_grande"]


@dataclass(frozen=True)
class DetectionCV:
    """
    Una singola detection prodotta dal modello CV su un frame raddrizzato.

    Il client CV (Roboflow / mock / altro) ritorna una lista di queste.
    Il servizio le persiste come `InferenzaCV` nel DB.
    """

    territorio: str | None
    colore: str | None
    tipo_pedina_dominante: TipoPedinaCv | None
    n_armate_stimate: int
    bbox: tuple[int, int, int, int]  # x, y, w, h
    confidence: float
    scomposizione: list[dict[str, object]]


class ClientCVError(Exception):
    """Errore generico del client CV."""


class ClientCVNonConfiguratoError(ClientCVError):
    """Il client reale non ha API key/configurazione necessaria."""


# === Contratto astratto ===


class ClientCV(ABC):
    """
    Contratto del modello CV. Riceve un frame raddrizzato (path su disco)
    e ritorna le detection.
    """

    @property
    @abstractmethod
    def versione_modello(self) -> str:
        """Stringa identificativa per il versioning delle inferenze."""

    @abstractmethod
    async def inferisci(
        self,
        percorso_frame_raddrizzato: Path,
    ) -> list[DetectionCV]:
        """
        Esegue inferenza su un frame e ritorna le detection.
        Le bbox sono in coordinate pixel del frame raddrizzato.
        """


# === Implementazione mock ===


class ClientCVMock(ClientCV):
    """
    Client mock per sviluppo/test:
    - Non legge davvero il frame.
    - Genera detection deterministiche basate sull'hash del path file.
    - Si puo' configurare per simulare drift, falsi positivi, ecc.

    Usato in test e per popolare il sistema durante lo sviluppo del
    frontend prima dell'arrivo del modello reale.
    """

    def __init__(
        self,
        *,
        versione: str = "mock-v1",
        n_detection_per_frame: int = 5,
        fattore_drift: float = 0.0,
    ) -> None:
        self._versione = versione
        self._n_detection = n_detection_per_frame
        self._drift = fattore_drift

    @property
    def versione_modello(self) -> str:
        return self._versione

    async def inferisci(
        self,
        percorso_frame_raddrizzato: Path,
    ) -> list[DetectionCV]:
        if not percorso_frame_raddrizzato.exists():
            raise ClientCVError(
                f"Frame non trovato: {percorso_frame_raddrizzato}"
            )

        # Seed deterministico dal path → mock riproducibile
        h = hashlib.md5(
            str(percorso_frame_raddrizzato).encode(), usedforsecurity=False
        ).hexdigest()
        seed = int(h[:8], 16)
        rng = random.Random(seed)

        territori_pool = [
            "kamchatka", "alaska", "ontario", "siberia", "europa_settentrionale",
            "africa_orientale", "argentina", "australia_orientale",
        ]
        colori_pool = ["rosso", "blu", "verde", "giallo"]
        tipi: list[TipoPedinaCv] = ["carro_piccolo", "carro_medio", "carro_grande"]
        valori_armate = {"carro_piccolo": 1, "carro_medio": 5, "carro_grande": 10}

        detection: list[DetectionCV] = []
        for _ in range(self._n_detection):
            tipo = rng.choice(tipi)
            n_armate_base = valori_armate[tipo]
            # Applica drift se richiesto
            n_armate = max(0, n_armate_base + rng.randint(
                -int(self._drift * n_armate_base),
                int(self._drift * n_armate_base),
            ) if self._drift > 0 else n_armate_base)

            detection.append(DetectionCV(
                territorio=rng.choice(territori_pool),
                colore=rng.choice(colori_pool),
                tipo_pedina_dominante=tipo,
                n_armate_stimate=n_armate,
                bbox=(
                    rng.randint(0, 1800),
                    rng.randint(0, 950),
                    rng.randint(40, 120),
                    rng.randint(40, 120),
                ),
                confidence=round(rng.uniform(0.6, 0.95), 3),
                scomposizione=[{
                    "tipo": tipo,
                    "bbox": [0, 0, 30, 30],
                    "confidence": round(rng.uniform(0.6, 0.95), 3),
                }],
            ))
        return detection


# === Implementazione "informata" (per seed_demo_cv) ===


class ClientCVDaStatoMotore(ClientCV):
    """
    Client che genera detection partendo dallo stato motore di una
    partita: emette una detection per ogni territorio controllato,
    eventualmente con drift configurabile.

    Utile per generare inferenze "realistiche" che producono divergenze
    significative quando confrontate con il motore.
    """

    def __init__(
        self,
        stato_motore_callback: object,  # Callable[[Path], list[StatoTerritorioMotore]]
        *,
        versione: str = "informata-v1",
        fattore_drift: float = 0.4,
    ) -> None:
        # Per semplicita' usiamo un callback. Quando integriamo davvero
        # cambieremo la signature.
        self._callback = stato_motore_callback
        self._versione = versione
        self._drift = fattore_drift

    @property
    def versione_modello(self) -> str:
        return self._versione

    async def inferisci(
        self,
        percorso_frame_raddrizzato: Path,
    ) -> list[DetectionCV]:
        # Implementazione minimale: usa stato motore via callback
        raise NotImplementedError(
            "ClientCVDaStatoMotore: usare seed_demo_cv.py per il workflow di seeding."
        )


# === Implementazione Roboflow (placeholder) ===


class ClientCVRoboflow(ClientCV):
    """
    Implementazione reale che chiama l'API Roboflow.

    PLACEHOLDER: l'API esatta dipende dal progetto Roboflow specifico
    (modello hosted vs serverless vs Docker locale). Verra' completata
    quando il modello sara' addestrato e si conoscera'
    `project_id`/`version_number`.

    Configurazione:
    - `api_key`: dal pannello Roboflow settings
    - `project_endpoint`: URL completo dell'endpoint hosted del modello
    - `confidence_minima`: filtra detection sotto soglia (default 0.5)
    - `iou_minimo`: NMS threshold per dedup (default 0.5)
    """

    def __init__(
        self,
        api_key: str,
        project_endpoint: str,
        *,
        versione: str | None = None,
        confidence_minima: float = 0.5,
        iou_minimo: float = 0.5,
    ) -> None:
        if not api_key:
            raise ClientCVNonConfiguratoError("api_key obbligatoria")
        if not project_endpoint:
            raise ClientCVNonConfiguratoError("project_endpoint obbligatorio")
        self._api_key = api_key
        self._endpoint = project_endpoint
        self._confidence_min = confidence_minima
        self._iou_min = iou_minimo
        # La versione viene dedotta dall'endpoint URL se non fornita esplicitamente
        self._versione = versione or _estrai_versione_da_endpoint(project_endpoint)

    @property
    def versione_modello(self) -> str:
        return self._versione

    async def inferisci(
        self,
        percorso_frame_raddrizzato: Path,
    ) -> list[DetectionCV]:
        """
        TODO: implementazione reale Roboflow API.

        Pseudo-codice del flusso atteso:

            import httpx
            with open(percorso_frame_raddrizzato, 'rb') as f:
                async with httpx.AsyncClient() as client:
                    risposta = await client.post(
                        self._endpoint,
                        params={
                            "api_key": self._api_key,
                            "confidence": int(self._confidence_min * 100),
                            "overlap": int(self._iou_min * 100),
                            "format": "json",
                        },
                        files={"file": f},
                    )
            risposta.raise_for_status()
            dati = risposta.json()
            # dati["predictions"] = list di dict con bbox, class, confidence
            # ...mapping a DetectionCV...

        Una volta confermata l'API esatta dal progetto Roboflow,
        sostituire il NotImplementedError sotto con il codice reale.
        """
        raise NotImplementedError(
            "ClientCVRoboflow.inferisci(): da completare quando il modello "
            "Roboflow sara' addestrato. Vedi pseudo-codice nel docstring."
        )


def _estrai_versione_da_endpoint(endpoint: str) -> str:
    """
    Roboflow endpoints hanno formato:
      https://detect.roboflow.com/<project>/<version>
    Estrae l'ultimo segmento come versione, fallback a 'roboflow'.
    """
    segmenti = [s for s in endpoint.rstrip("/").split("/") if s]
    if len(segmenti) >= 2:
        return f"roboflow-{segmenti[-2]}-v{segmenti[-1]}"
    return "roboflow-unknown"


# === Servizio orchestratore ===


class ServizioCVError(Exception):
    """Errore del servizio CV (orchestrazione)."""


class ServizioCV:
    """
    Pipeline completa: per un evento → estrai frame raddrizzato →
    inferisci con il client CV → persisti come InferenzaCV.

    Args:
        servizio_raddrizzamento: usato per ottenere il frame raddrizzato.
        client_cv: implementazione del modello CV.
    """

    def __init__(
        self,
        servizio_raddrizzamento: ServizioRaddrizzamento,
        client_cv: ClientCV,
    ) -> None:
        self._raddrizzamento = servizio_raddrizzamento
        self._client = client_cv

    async def analizza_evento(
        self,
        db: AsyncSession,
        partita_id: str,
        evento_id: str,
        *,
        forza_raddrizzamento: bool = False,
    ) -> list[InferenzaCV]:
        """
        Esegue la pipeline completa per un singolo evento.

        Step:
        1. Ottiene frame raddrizzato (richiede calibrazione preventiva)
        2. Lancia inferenza CV → list[DetectionCV]
        3. Persiste come InferenzaCV nel DB
        4. Ritorna i record creati

        Raises:
            OmografiaNonCalibrataError: la partita non e' calibrata.
            ClientCVError: errore di inferenza.
        """
        # Step 1: frame raddrizzato (con cache + calibrazione preventiva)
        frame_path = await self._raddrizzamento.raddrizza_per_evento(
            db, partita_id, evento_id, forza=forza_raddrizzamento,
        )

        # Step 2: inferenza
        detection = await self._client.inferisci(frame_path)

        # Step 3: persistenza in batch
        # Ottimizzazione: settiamo manualmente creata_il invece di affidarci
        # al server_default + refresh in loop (che farebbe N round-trip).
        # ID e' gia' generato lato Python (uuid4 default).
        from datetime import UTC as _UTC
        from datetime import datetime as _dt

        frame_hash = self._calcola_hash(frame_path)
        ora_creazione = _dt.now(_UTC)
        creati: list[InferenzaCV] = [
            InferenzaCV(
                partita_id=partita_id,
                evento_validato_id=evento_id,
                modello_versione=self._client.versione_modello,
                territorio=det.territorio,
                colore=det.colore,
                tipo_pedina_dominante=det.tipo_pedina_dominante,
                n_armate_stimate=det.n_armate_stimate,
                bbox=list(det.bbox),
                confidence=det.confidence,
                scomposizione=det.scomposizione,
                frame_hash=frame_hash,
                creata_il=ora_creazione,
            )
            for det in detection
        ]
        db.add_all(creati)
        await db.commit()
        # Niente refresh in loop: tutti i campi sono gia' valorizzati.
        return creati

    async def analizza_tutti_eventi(
        self,
        db: AsyncSession,
        partita_id: str,
        *,
        forza_raddrizzamento: bool = False,
    ) -> dict[str, object]:
        """
        Esegue la pipeline su TUTTI gli eventi validati di una partita.

        Returns:
            Riepilogo: n_eventi_totali, n_riusciti, n_falliti, falliti.
        """
        stmt = (
            select(EventoValidato.id)
            .where(EventoValidato.partita_id == partita_id)
            .order_by(EventoValidato.ts_evento)
        )
        risultato = await db.execute(stmt)
        evento_ids = [row[0] for row in risultato.all()]

        n_riusciti = 0
        n_inferenze_totali = 0
        falliti: list[dict[str, str]] = []

        for ev_id in evento_ids:
            try:
                inferenze = await self.analizza_evento(
                    db, partita_id, ev_id,
                    forza_raddrizzamento=forza_raddrizzamento,
                )
                n_riusciti += 1
                n_inferenze_totali += len(inferenze)
            except (OmografiaNonCalibrataError, ServizioCVError) as e:
                falliti.append({"evento_id": ev_id, "errore": str(e)})
            except ClientCVError as e:
                falliti.append({"evento_id": ev_id, "errore": f"CV: {e}"})

        return {
            "n_eventi_totali": len(evento_ids),
            "n_riusciti": n_riusciti,
            "n_falliti": len(falliti),
            "n_inferenze_totali": n_inferenze_totali,
            "modello_versione": self._client.versione_modello,
            "falliti": falliti,
        }

    @staticmethod
    def _calcola_hash(percorso: Path) -> str:
        """SHA-256 troncato a 16 caratteri per dedup/tracking."""
        h = hashlib.sha256()
        with percorso.open("rb") as f:
            for blocco in iter(lambda: f.read(65536), b""):
                h.update(blocco)
        return h.hexdigest()[:16]


# === Helper per snapshot motore (usato da seed) ===


async def carica_stato_motore_per_partita(
    db: AsyncSession,
    partita_id: str,
) -> list[object]:
    """
    Helper riutilizzabile: carica StatoPartitaRicostruito dal DB e lo
    converte in lista di StatoTerritorioMotore.
    Ritorna lista vuota se non c'e' snapshot.
    """
    risultato = await db.execute(
        select(StatoPartitaRicostruito).where(
            StatoPartitaRicostruito.partita_id == partita_id
        )
    )
    snap = risultato.scalar_one_or_none()
    if snap is None or snap.stato_serializzato is None:
        return []
    return list(stato_motore_da_snapshot(snap.stato_serializzato))


# Disabilita F401 sui re-export per evitare warning ruff
__all__ = [
    "ClientCV",
    "ClientCVError",
    "ClientCVMock",
    "ClientCVNonConfiguratoError",
    "ClientCVRoboflow",
    "DetectionCV",
    "ServizioCV",
    "ServizioCVError",
    "carica_stato_motore_per_partita",
]
