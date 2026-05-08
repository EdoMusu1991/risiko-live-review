"""
Popola il database con una partita demo e una manciata di eventi BLE
"realistici" da usare per testare il flusso UI di review delle proposte
di aggregazione.

Caso d'uso: stai sviluppando il frontend e vuoi vedere come si comporta
il pannello "Proposte aggregazione dadi" senza dover costruire un bundle
mobile, fare l'import, ecc. Lanci questo script, ottieni l'URL della
partita demo, apri il browser e iteri.

Usage:
    python -m scripts.seed_demo_ble [--n-attacchi 3] [--reset]

Lo script è idempotente per default: se trova una partita "Demo BLE
Seed" esistente, la riusa. Con `--reset` la elimina e la ricrea.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Permette di lanciare lo script come `python scripts/seed_demo_ble.py`
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select

from app.configurazione.database import sessione_factory
from app.modelli import (
    EventoGrezzo,
    FonteEvento,
    GiocatorePartita,
    Partita,
    StatoReview,
    TipoEvento,
)

NOME_PARTITA_SEED = "Demo BLE Seed"


# === Configurazione partita demo ===

GIOCATORI_DEMO: list[tuple[str, str, int]] = [
    # (nome, colore, ordine_seduta)
    ("Edoardo", "rosso", 1),
    ("Marco", "blu", 2),
    ("Alice", "verde", 3),
]


# === Generazione eventi BLE ===


def genera_eventi_attacco(
    *,
    partita_id: str,
    ts_inizio_attacco: datetime,
    ble_attaccante_ids: list[str],
    ble_difensore_ids: list[str],
    valori_attaccante: list[int],
    valori_difensore: list[int],
    delta_dado_sec: float = 0.3,
) -> list[EventoGrezzo]:
    """
    Crea N eventi grezzi BLE per un singolo attacco, distribuiti nel
    tempo a `delta_dado_sec` di distanza l'uno dall'altro.

    Default 0.3s tra dadi → tutti dentro la finestra di clustering
    default (3s) del backend, quindi formeranno un'unica proposta.
    """
    eventi: list[EventoGrezzo] = []
    cursor = ts_inizio_attacco

    # Prima i dadi attaccante
    for slot, (ble_id, valore) in enumerate(
        zip(ble_attaccante_ids, valori_attaccante, strict=True), start=1
    ):
        eventi.append(
            EventoGrezzo(
                partita_id=partita_id,
                ts_evento=cursor,
                tipo=TipoEvento.DADI_LANCIATI,
                fonte=FonteEvento.DADO_BLE,
                confidenza=1.0,
                dati={
                    "ble_id": ble_id,
                    "ruolo": "attaccante",
                    "slot": slot,
                    "valore": valore,
                },
                validato=False,
            )
        )
        cursor += timedelta(seconds=delta_dado_sec)

    # Poi i dadi difensore
    for slot, (ble_id, valore) in enumerate(
        zip(ble_difensore_ids, valori_difensore, strict=True), start=1
    ):
        eventi.append(
            EventoGrezzo(
                partita_id=partita_id,
                ts_evento=cursor,
                tipo=TipoEvento.DADI_LANCIATI,
                fonte=FonteEvento.DADO_BLE,
                confidenza=1.0,
                dati={
                    "ble_id": ble_id,
                    "ruolo": "difensore",
                    "slot": slot,
                    "valore": valore,
                },
                validato=False,
            )
        )
        cursor += timedelta(seconds=delta_dado_sec)

    return eventi


# === Scenari di test ===


def scenari_attacchi(ts_base: datetime) -> list[dict[str, object]]:
    """
    3 attacchi spaziati 30 secondi l'uno dall'altro (>> finestra default
    di 3s, quindi 3 cluster distinti = 3 proposte separate).

    Mix di anomalie realistiche per esercitare il pannello UI:
    - Attacco 1: 3v3 pulito (caso felice)
    - Attacco 2: 2v1 (giocatore conquista territorio quasi sgombro)
    - Attacco 3: 1v0 (territorio neutrale o errore di lettura BLE)
    """
    return [
        # Attacco 1: 3 attaccanti vs 3 difensori, valori plausibili
        {
            "ts_inizio_attacco": ts_base + timedelta(seconds=10),
            "ble_attaccante_ids": ["A1", "A2", "A3"],
            "ble_difensore_ids": ["D1", "D2", "D3"],
            "valori_attaccante": [6, 4, 2],
            "valori_difensore": [5, 3, 1],
        },
        # Attacco 2: 2 attaccanti vs 1 difensore (territorio con pochi armati)
        {
            "ts_inizio_attacco": ts_base + timedelta(seconds=40),
            "ble_attaccante_ids": ["A1", "A2"],
            "ble_difensore_ids": ["D1"],
            "valori_attaccante": [5, 3],
            "valori_difensore": [4],
        },
        # Attacco 3: 1 attaccante vs 0 difensore (anomalia BLE: dado dif
        # caduto fuori, sensore non l'ha registrato)
        {
            "ts_inizio_attacco": ts_base + timedelta(seconds=70),
            "ble_attaccante_ids": ["A1"],
            "ble_difensore_ids": [],
            "valori_attaccante": [6],
            "valori_difensore": [],
        },
    ]


# === Operazione principale ===


async def cerca_partita_seed(db) -> Partita | None:
    risultato = await db.execute(
        select(Partita).where(Partita.note == NOME_PARTITA_SEED)
    )
    return risultato.scalar_one_or_none()


async def elimina_partita_seed(db) -> int:
    """Ritorna numero di partite eliminate (0 o 1)."""
    partita = await cerca_partita_seed(db)
    if partita is None:
        return 0
    await db.delete(partita)
    await db.commit()
    return 1


async def crea_partita_seed(db, n_attacchi: int) -> Partita:
    """Crea partita + giocatori + eventi BLE."""
    ts_base = datetime.now(UTC).replace(microsecond=0)
    partita = Partita(
        data_inizio=ts_base,
        luogo="Il Gufo · Roma (DEMO)",
        note=NOME_PARTITA_SEED,
        stato_review=StatoReview.GREZZA,
    )
    db.add(partita)
    await db.flush()

    for nome, colore, ordine in GIOCATORI_DEMO:
        db.add(
            GiocatorePartita(
                partita_id=partita.id,
                nome=nome,
                colore=colore,
                ordine_seduta=ordine,
            )
        )
    await db.flush()

    scenari = scenari_attacchi(ts_base)[:n_attacchi]
    n_eventi = 0
    for scenario in scenari:
        eventi = genera_eventi_attacco(partita_id=partita.id, **scenario)  # type: ignore[arg-type]
        db.add_all(eventi)
        n_eventi += len(eventi)

    await db.commit()
    print(
        f"✓ Partita seed creata: id={partita.id}, "
        f"{len(GIOCATORI_DEMO)} giocatori, "
        f"{n_attacchi} attacchi → {n_eventi} eventi BLE grezzi"
    )
    return partita


async def main_async(*, n_attacchi: int, reset: bool) -> None:
    async with sessione_factory() as db:
        if reset:
            n = await elimina_partita_seed(db)
            if n > 0:
                print(f"✓ Partita seed precedente eliminata ({n})")

        esistente = await cerca_partita_seed(db)
        if esistente is not None:
            print(
                f"i Partita seed gia esistente: id={esistente.id} "
                "(usa --reset per ricrearla)"
            )
            partita = esistente
        else:
            partita = await crea_partita_seed(db, n_attacchi)

    print()
    print("=" * 60)
    print("FRONTEND URL (default Vite dev server):")
    print(f"  http://localhost:5173/partite/{partita.id}")
    print()
    print("API ROOT (default uvicorn):")
    print(f"  http://localhost:8000/api/partite/{partita.id}")
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo BLE per testing UI")
    parser.add_argument(
        "--n-attacchi",
        type=int,
        default=3,
        choices=[1, 2, 3],
        help="Numero di attacchi da generare (1-3, default 3)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Elimina la partita seed esistente prima di crearne una nuova",
    )
    args = parser.parse_args()

    asyncio.run(main_async(n_attacchi=args.n_attacchi, reset=args.reset))


if __name__ == "__main__":
    main()
