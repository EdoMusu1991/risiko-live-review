"""
Popola la partita demo (creata da seed_demo_ble.py) con inferenze CV
finte + calcolo discrepanze, in modo da testare la UI di review
divergenze senza dover ancora avere il modello CV reale.

Genera 3 tipi di inferenze:
1. **Match perfetto**: territorio + colore + n_armate corrispondenti
   allo stato motore. Non genera divergenze.
2. **Mismatch leggero (delta=1)**: la CV vede 1 armata in piu'/meno del motore.
3. **Mismatch grave (delta>=3)**: scenario "evento mancante" simulato.

L'output e' un set realistico di divergenze ordinate per delta_assoluto,
ottimo per validare la UI prima di avere inferenze vere.

Usage:
    python -m scripts.seed_demo_cv [--reset]
"""

from __future__ import annotations

import argparse
import asyncio
import random
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.configurazione import impostazioni
from app.modelli import (
    DivergenzaInferita,
    InferenzaCV,
    Partita,
    StatoPartitaRicostruito,
)
from app.servizi.discrepanze_servizio import (
    calcola_discrepanze,
    stato_motore_da_snapshot,
)

# Versione del modello sintetico (per filtri lato API)
MODELLO_VERSIONE_DEMO = "demo-seed-v1"

# Per riproducibilita'
RANDOM_SEED = 42


def _crea_engine():
    return create_async_engine(impostazioni.database_url)


async def cerca_partita_demo(db) -> Partita | None:
    """Cerca una partita 'Demo BLE Seed' (creata da seed_demo_ble.py)."""
    risultato = await db.execute(
        select(Partita).where(Partita.luogo == "Demo BLE Seed")
    )
    return risultato.scalar_one_or_none()


async def elimina_inferenze_demo(db, partita_id: str) -> int:
    """Cancella le inferenze e divergenze del seed precedente."""
    risultato = await db.execute(
        select(InferenzaCV).where(
            InferenzaCV.partita_id == partita_id,
            InferenzaCV.modello_versione == MODELLO_VERSIONE_DEMO,
        )
    )
    n_inf = 0
    for inf in risultato.scalars().all():
        await db.delete(inf)
        n_inf += 1

    ris_div = await db.execute(
        select(DivergenzaInferita).where(
            DivergenzaInferita.partita_id == partita_id
        )
    )
    n_div = 0
    for div in ris_div.scalars().all():
        await db.delete(div)
        n_div += 1

    await db.commit()
    return n_inf + n_div


async def carica_stato_motore(db, partita_id: str):
    """
    Carica lo stato motore dalla tabella StatoPartitaRicostruito.
    Se non c'e', solleva.
    """
    risultato = await db.execute(
        select(StatoPartitaRicostruito).where(
            StatoPartitaRicostruito.partita_id == partita_id
        )
    )
    snap = risultato.scalar_one_or_none()
    if snap is None or snap.stato_serializzato is None:
        raise RuntimeError(
            "Partita demo senza stato ricostruito. Esegui prima:\n"
            "  curl -X POST http://localhost:8000/api/partite/<id>/ricostruisci"
        )
    return stato_motore_da_snapshot(snap.stato_serializzato)


async def genera_inferenze_demo(
    db, partita_id: str, stato_motore: list, *, fattore_drift: float = 0.4,
) -> int:
    """
    Crea inferenze CV finte basate sullo stato motore.

    Args:
        fattore_drift: probabilita' (0..1) che ogni territorio abbia
            una divergenza CV ↔ motore. Default 0.4 (40% disallineate).

    Returns:
        Numero di inferenze inserite.
    """
    rng = random.Random(RANDOM_SEED)
    n_creati = 0

    for stato in stato_motore:
        if stato.n_armate == 0:
            continue

        # Decide se questa entry avra' una divergenza
        deve_divergere = rng.random() < fattore_drift

        if not deve_divergere:
            # Match perfetto
            n_armate_cv = stato.n_armate
            confidence = rng.uniform(0.85, 0.98)
        else:
            # Divergenza random, delta tra 1 e 3
            delta = rng.choice([-3, -2, -1, 1, 2, 3])
            n_armate_cv = max(0, stato.n_armate + delta)
            confidence = rng.uniform(0.55, 0.82)

        # Decide il tipo di pedina dominante (per realismo, dipende da n_armate)
        if n_armate_cv >= 10:
            tipo = "carro_grande"
        elif n_armate_cv >= 5:
            tipo = "carro_medio"
        else:
            tipo = "carro_piccolo"

        inferenza = InferenzaCV(
            partita_id=partita_id,
            evento_validato_id=None,  # snapshot, non legata a evento
            modello_versione=MODELLO_VERSIONE_DEMO,
            territorio=stato.territorio,
            colore=stato.colore,
            tipo_pedina_dominante=tipo,
            n_armate_stimate=n_armate_cv,
            bbox=[
                rng.randint(50, 1800),
                rng.randint(50, 950),
                rng.randint(40, 120),
                rng.randint(40, 120),
            ],
            confidence=round(confidence, 3),
            scomposizione=[
                {
                    "tipo": tipo,
                    "bbox": [0, 0, 30, 30],
                    "confidence": round(confidence, 3),
                }
            ],
            frame_hash=None,
        )
        db.add(inferenza)
        n_creati += 1

    # Aggiungi 1-2 inferenze "fantasma" su territori non controllati dal motore
    # (simulano falsi positivi del modello)
    territori_motore = {s.territorio for s in stato_motore}
    territori_finti = ["madagascar", "argentina", "egitto", "siberia"]
    territori_falsi = [t for t in territori_finti if t not in territori_motore]
    for terr in territori_falsi[:2]:
        db.add(InferenzaCV(
            partita_id=partita_id,
            evento_validato_id=None,
            modello_versione=MODELLO_VERSIONE_DEMO,
            territorio=terr,
            colore=rng.choice(["rosso", "blu", "verde", "giallo"]),
            tipo_pedina_dominante="carro_piccolo",
            n_armate_stimate=rng.randint(1, 3),
            bbox=[100, 100, 50, 50],
            confidence=round(rng.uniform(0.3, 0.6), 3),  # bassa = sospetto
            scomposizione=[],
            frame_hash=None,
        ))
        n_creati += 1

    await db.commit()
    return n_creati


async def calcola_e_persisti_divergenze(
    db, partita_id: str, stato_motore: list,
) -> int:
    """Calcola le divergenze e le salva come DivergenzaInferita."""
    risultato = await db.execute(
        select(InferenzaCV).where(
            InferenzaCV.partita_id == partita_id,
            InferenzaCV.modello_versione == MODELLO_VERSIONE_DEMO,
        )
    )
    inferenze = list(risultato.scalars().all())

    divergenze = calcola_discrepanze(stato_motore, inferenze)

    for d in divergenze:
        db.add(DivergenzaInferita(
            partita_id=partita_id,
            evento_validato_id=None,
            territorio=d.territorio,
            colore=d.colore,
            valore_motore=d.valore_motore,
            valore_cv=d.valore_cv,
            confidence_cv=d.confidence_cv,
            delta_assoluto=d.delta_assoluto,
            inferenze_correlate=d.inferenze_correlate,
            risoluzione="aperta",
        ))

    await db.commit()
    return len(divergenze)


async def main_async(*, reset: bool) -> None:
    engine = _crea_engine()
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with factory() as db:
        partita = await cerca_partita_demo(db)
        if partita is None:
            print(
                "✗ Nessuna partita 'Demo BLE Seed' trovata. Esegui prima:\n"
                "    python -m scripts.seed_demo_ble"
            )
            return

        print(f"✓ Partita demo trovata: id={partita.id}")

        if reset:
            n = await elimina_inferenze_demo(db, partita.id)
            if n > 0:
                print(f"✓ {n} record di seed CV precedente eliminati")

        try:
            stato_motore = await carica_stato_motore(db, partita.id)
        except RuntimeError as e:
            print(f"✗ {e}")
            return

        print(f"✓ Stato motore caricato: {len(stato_motore)} territori controllati")

        # Verifica idempotenza: se ci sono gia' inferenze demo, skippa
        risultato = await db.execute(
            select(InferenzaCV).where(
                InferenzaCV.partita_id == partita.id,
                InferenzaCV.modello_versione == MODELLO_VERSIONE_DEMO,
            )
        )
        if risultato.first() is not None and not reset:
            print(
                "i Inferenze demo gia' presenti. Usa --reset per ricrearle."
            )
            return

        n_inf = await genera_inferenze_demo(db, partita.id, stato_motore)
        print(f"✓ {n_inf} inferenze CV demo create (modello: {MODELLO_VERSIONE_DEMO})")

        n_div = await calcola_e_persisti_divergenze(db, partita.id, stato_motore)
        print(f"✓ {n_div} divergenze calcolate e persistite")

    print()
    print("=" * 60)
    print("URL FRONTEND:")
    print(f"  http://localhost:5173/partite/{partita.id}")
    print()
    print("API discrepanze:")
    print(f"  http://localhost:8000/api/partite/{partita.id}/discrepanze")
    print("=" * 60)
    print(f"\nGenerati alle {datetime.now(UTC).isoformat()}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed inferenze CV demo per testing UI"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Elimina inferenze e divergenze esistenti prima di ricrearle",
    )
    args = parser.parse_args()

    asyncio.run(main_async(reset=args.reset))


if __name__ == "__main__":
    main()
