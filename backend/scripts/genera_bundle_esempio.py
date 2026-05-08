"""
Genera un bundle replay di esempio (JSON) usabile come fixture per
testare il modulo replay di Battle Commander senza dover avere il
backend Risiko Live attivo.

Output: file JSON conforme allo schema `BundleReplay` del pacchetto
`@risiko/eventi-schema`. Dataset realistico:
- 3 giocatori (rosso, blu, verde)
- Setup automatico (42 territori distribuiti + 3 obiettivi + partita_inizio)
- ~5 turni con: rinforzi, qualche attacco vincente, qualche perdente,
  conquiste, fine turno

Usage:
    python scripts/genera_bundle_esempio.py [output_path]

Default output: ./bundle-replay-esempio.json
"""

from __future__ import annotations

import asyncio
import json
import random
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.configurazione.database import Base, engine, sessione_factory
from app.modelli import (
    EventoValidato,
    GiocatorePartita,
    Partita,
    StatoReview,
    TipoEvento,
)
from app.servizi.esportazione_servizio import ServizioEsportazione
from app.servizi.setup_automatico_servizio import (
    ServizioSetupAutomatico,
)
from risiko_engine.mappa import adiacenti_a

DEFAULT_OUTPUT = Path("bundle-replay-esempio.json")


GIOCATORI = [
    ("Edoardo", "rosso", 1),
    ("Marco", "blu", 2),
    ("Alice", "verde", 3),
]


async def genera_bundle_esempio() -> dict:
    """Costruisce DB in-memory, crea partita, applica setup + eventi."""
    # DB SQLite in-memory dedicato
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    rng = random.Random(42)

    async with sessione_factory() as db:
        ts_inizio = datetime(2026, 5, 8, 21, 0, 0, tzinfo=UTC)
        partita = Partita(
            data_inizio=ts_inizio,
            luogo="Il Gufo · Roma",
            note="Partita di esempio per fixture replay BC",
            stato_review=StatoReview.GREZZA,
        )
        db.add(partita)
        await db.flush()

        for nome, colore, ordine in GIOCATORI:
            db.add(
                GiocatorePartita(
                    partita_id=partita.id,
                    nome=nome,
                    colore=colore,
                    ordine_seduta=ordine,
                )
            )
        await db.flush()

        # Setup automatico (42 territori + 3 obiettivi + partita_inizio)
        await ServizioSetupAutomatico.genera(db, partita.id, seed=42)
        await db.flush()
        await db.refresh(partita, attribute_names=["giocatori", "eventi_validati"])

        # Genera eventi di gioco realistici
        ts = ts_inizio + timedelta(minutes=2)
        territori_per_giocatore = _territori_per_giocatore(partita)
        giocatori_ordinati = sorted(
            partita.giocatori, key=lambda g: g.ordine_seduta
        )

        # 5 turni a giro: rinforzi + 1-2 attacchi + spostamento + fine turno
        for turno_n in range(5):
            giocatore = giocatori_ordinati[turno_n % len(giocatori_ordinati)]

            # TURNO_INIZIATO
            db.add(
                EventoValidato(
                    partita_id=partita.id,
                    ts_evento=ts,
                    tipo=TipoEvento.TURNO_INIZIATO,
                    dati={"giocatore_id": giocatore.id},
                    evento_grezzo_id=None,
                    validato_da="esempio",
                )
            )
            ts += timedelta(seconds=5)

            # ARMATE_PIAZZATE: 3 armate su un territorio random
            terr_propri = list(territori_per_giocatore[giocatore.id])
            if terr_propri:
                terr = rng.choice(terr_propri)
                db.add(
                    EventoValidato(
                        partita_id=partita.id,
                        ts_evento=ts,
                        tipo=TipoEvento.ARMATE_PIAZZATE,
                        dati={
                            "giocatore_id": giocatore.id,
                            "territorio": terr,
                            "n": 3,
                        },
                        evento_grezzo_id=None,
                        validato_da="esempio",
                    )
                )
                ts += timedelta(seconds=10)

            # 1-2 attacchi: trova coppia adiacente con bersaglio nemico
            for _ in range(rng.randint(1, 2)):
                attacco = _trova_attacco_possibile(
                    territori_per_giocatore, giocatore.id, rng
                )
                if attacco is None:
                    break
                terr_da, terr_a, difensore_id = attacco

                # Tira dadi (3v2)
                dadi_att = sorted(
                    [rng.randint(1, 6) for _ in range(3)], reverse=True
                )
                dadi_dif = sorted(
                    [rng.randint(1, 6) for _ in range(2)], reverse=True
                )

                db.add(
                    EventoValidato(
                        partita_id=partita.id,
                        ts_evento=ts,
                        tipo=TipoEvento.ATTACCO_RISOLTO,
                        dati={
                            "giocatore_id": giocatore.id,
                            "da": terr_da,
                            "a": terr_a,
                            "dadi_attaccante": dadi_att,
                            "dadi_difensore": dadi_dif,
                        },
                        evento_grezzo_id=None,
                        validato_da="esempio",
                    )
                )
                ts += timedelta(seconds=15)

                # Determina vincitore semplificato: se attaccante vince
                # tutti i confronti, conquista il territorio
                vittorie_att = sum(
                    1
                    for a, d in zip(dadi_att, dadi_dif, strict=False)
                    if a > d
                )
                if vittorie_att == 2:  # vinto entrambi i confronti
                    db.add(
                        EventoValidato(
                            partita_id=partita.id,
                            ts_evento=ts,
                            tipo=TipoEvento.TERRITORIO_CONQUISTATO,
                            dati={
                                "giocatore_id": giocatore.id,
                                "territorio": terr_a,
                            },
                            evento_grezzo_id=None,
                            validato_da="esempio",
                        )
                    )
                    ts += timedelta(seconds=2)
                    # Aggiorna mappa territori
                    territori_per_giocatore[difensore_id].discard(terr_a)
                    territori_per_giocatore[giocatore.id].add(terr_a)

            # TURNO_FINITO
            db.add(
                EventoValidato(
                    partita_id=partita.id,
                    ts_evento=ts,
                    tipo=TipoEvento.TURNO_FINITO,
                    dati={"giocatore_id": giocatore.id},
                    evento_grezzo_id=None,
                    validato_da="esempio",
                )
            )
            ts += timedelta(seconds=10)

        await db.commit()

        # Esporta bundle replay
        dati = await ServizioEsportazione.prepara_dati(db, partita.id)
        return ServizioEsportazione.serializza_bundle_replay(dati)


def _territori_per_giocatore(partita: Partita) -> dict[str, set[str]]:
    """Mappa giocatore_id -> territori che possiede (da TERRITORIO_ASSEGNATO_INIZIO)."""
    risultato: dict[str, set[str]] = {g.id: set() for g in partita.giocatori}
    for ev in partita.eventi_validati:
        if (
            ev.tipo == TipoEvento.TERRITORIO_ASSEGNATO_INIZIO
            and isinstance(ev.dati, dict)
        ):
            gid = ev.dati.get("giocatore_id")
            terr = ev.dati.get("territorio")
            if isinstance(gid, str) and isinstance(terr, str) and gid in risultato:
                risultato[gid].add(terr)
    return risultato


def _trova_attacco_possibile(
    territori: dict[str, set[str]],
    attaccante_id: str,
    rng: random.Random,
) -> tuple[str, str, str] | None:
    """Trova una coppia (terr_da, terr_a, difensore_id) plausibile."""
    miei = list(territori[attaccante_id])
    rng.shuffle(miei)
    for terr_da in miei:
        for terr_adj in adiacenti_a(terr_da):
            for altro_id, suoi in territori.items():
                if altro_id != attaccante_id and terr_adj in suoi:
                    return (terr_da, terr_adj, altro_id)
    return None


async def main_async() -> int:
    output_path = (
        Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    )

    bundle = await genera_bundle_esempio()
    output_path.write_text(json.dumps(bundle, indent=2, default=str), encoding="utf-8")

    print(f"Bundle scritto: {output_path}")
    print(f"  schema_version: {bundle['schema_version']}")
    print(f"  partita.id: {bundle['partita']['id']}")
    print(f"  giocatori: {len(bundle['giocatori'])}")
    print(f"  eventi: {len(bundle['eventi'])}")

    # Riepilogo per tipo
    tipi: dict[str, int] = {}
    for ev in bundle["eventi"]:
        tipi[ev["tipo"]] = tipi.get(ev["tipo"], 0) + 1
    print("  per tipo:")
    for tipo, n in sorted(tipi.items()):
        print(f"    {tipo}: {n}")

    return 0


def main() -> None:
    sys.exit(asyncio.run(main_async()))


if __name__ == "__main__":
    main()
