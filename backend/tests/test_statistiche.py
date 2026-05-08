"""
Test del servizio `calcola_statistiche` (puro) e dell'endpoint
`GET /api/partite/{id}/statistiche`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modelli import (
    EventoValidato,
    GiocatorePartita,
    Partita,
    StatoReview,
    TipoEvento,
)
from app.servizi.statistiche_partita_servizio import (
    _confronta_dadi,
    calcola_statistiche,
)

# === Test della logica di confronto dadi (regola Risiko) ===


class TestConfrontaDadi:
    def test_attaccante_domina_3v3(self) -> None:
        """[6,4,2] vs [5,3,1]: tutte le coppie l'attaccante vince."""
        att, dif = _confronta_dadi([6, 4, 2], [5, 3, 1])
        assert att == 0
        assert dif == 3

    def test_difensore_domina_con_parita(self) -> None:
        """[3,2] vs [3,2]: parità → vince difensore in entrambe le coppie."""
        att, dif = _confronta_dadi([3, 2], [3, 2])
        assert att == 2
        assert dif == 0

    def test_dadi_in_eccesso_non_contano(self) -> None:
        """[6,4,2] vs [5,3]: 2 confronti, 1 dado att in più ignorato."""
        att, dif = _confronta_dadi([6, 4, 2], [5, 3])
        assert att == 0
        assert dif == 2  # 6>5, 4>3

    def test_misto(self) -> None:
        """[6,1] vs [5,2]: 6>5 (dif-1), 1<=2 (att-1)."""
        att, dif = _confronta_dadi([6, 1], [5, 2])
        assert att == 1
        assert dif == 1

    def test_difensore_solo(self) -> None:
        """Senza dadi attaccante non c'è confronto."""
        att, dif = _confronta_dadi([], [5, 3])
        assert att == 0
        assert dif == 0

    def test_attaccante_solo(self) -> None:
        att, dif = _confronta_dadi([5, 3], [])
        assert att == 0
        assert dif == 0

    def test_input_non_ordinato_viene_ordinato(self) -> None:
        """Anche input non ordinato funziona (la funzione ordina internamente)."""
        # [2,4,6] vs [1,3,5] dovrebbe dare gli stessi risultati di [6,4,2] vs [5,3,1]
        att, dif = _confronta_dadi([2, 4, 6], [1, 3, 5])
        assert att == 0
        assert dif == 3


# === Test del servizio principale ===


def _crea_partita(con_data_fine: bool = False) -> Partita:
    """Partita detached, con/senza data_fine."""
    return Partita(
        id="test-partita-id",
        data_inizio=datetime(2026, 5, 7, 21, 0, tzinfo=UTC),
        data_fine=(
            datetime(2026, 5, 7, 23, 30, tzinfo=UTC) if con_data_fine else None
        ),
        stato_review=StatoReview.GREZZA,
    )


def _crea_giocatori() -> list[GiocatorePartita]:
    return [
        GiocatorePartita(
            id="g-rosso", partita_id="test-partita-id",
            nome="Edo", colore="rosso", ordine_seduta=1,
        ),
        GiocatorePartita(
            id="g-blu", partita_id="test-partita-id",
            nome="Marco", colore="blu", ordine_seduta=2,
        ),
    ]


def _evento(
    tipo: TipoEvento, dati: dict[str, Any], offset_sec: float = 0.0
) -> EventoValidato:
    return EventoValidato(
        id=f"ev-{tipo.value}-{offset_sec}",
        partita_id="test-partita-id",
        ts_evento=datetime(2026, 5, 7, 21, 0, tzinfo=UTC) + timedelta(seconds=offset_sec),
        tipo=tipo,
        dati=dati,
        evento_grezzo_id=None,
        validato_da="test",
    )


class TestCalcolaStatistiche:
    def test_partita_vuota(self) -> None:
        partita = _crea_partita()
        giocatori = _crea_giocatori()
        stat = calcola_statistiche(partita, giocatori, [])

        assert stat.partita_id == "test-partita-id"
        assert stat.n_eventi_validati == 0
        assert stat.n_turni == 0
        assert stat.n_attacchi_totali == 0
        assert stat.durata_sec is None
        # 2 giocatori, ognuno con metriche a zero
        assert len(stat.statistiche_giocatori) == 2
        for sg in stat.statistiche_giocatori:
            assert sg.n_attacchi == 0
            assert sg.n_dadi_lanciati == 0
            assert sg.media_dadi_lanciati is None

    def test_durata_calcolata_se_data_fine_presente(self) -> None:
        partita = _crea_partita(con_data_fine=True)
        stat = calcola_statistiche(partita, _crea_giocatori(), [])
        # 2h30m = 9000s
        assert stat.durata_sec == 9000.0

    def test_un_attacco_caso_classico_3v2(self) -> None:
        """[6,4,2] vs [5,3]: att perde 0, dif perde 2."""
        eventi = [
            _evento(
                TipoEvento.ATTACCO_RISOLTO,
                {
                    "giocatore_id": "g-rosso",
                    "da": "kamchatka",
                    "a": "alaska",
                    "dadi_attaccante": [6, 4, 2],
                    "dadi_difensore": [5, 3],
                },
            )
        ]
        stat = calcola_statistiche(_crea_partita(), _crea_giocatori(), eventi)
        rosso = next(s for s in stat.statistiche_giocatori if s.nome == "Edo")
        blu = next(s for s in stat.statistiche_giocatori if s.nome == "Marco")

        assert stat.n_attacchi_totali == 1
        assert rosso.n_attacchi == 1
        assert rosso.n_dadi_lanciati == 3
        assert rosso.media_dadi_lanciati == 4.0  # (6+4+2)/3
        assert rosso.armate_perse_attaccando == 0
        assert rosso.armate_inflitte_attaccando == 2
        # Blu non ha attaccato
        assert blu.n_attacchi == 0
        assert blu.armate_inflitte_attaccando == 0

    def test_attacchi_multipli_aggregati_correttamente(self) -> None:
        """Due attacchi → totali sommati."""
        eventi = [
            _evento(
                TipoEvento.ATTACCO_RISOLTO,
                {
                    "giocatore_id": "g-rosso",
                    "da": "k", "a": "a",
                    "dadi_attaccante": [6, 4, 2],
                    "dadi_difensore": [5, 3],
                },
                offset_sec=0,
            ),
            _evento(
                TipoEvento.ATTACCO_RISOLTO,
                {
                    "giocatore_id": "g-rosso",
                    "da": "a", "a": "n",
                    "dadi_attaccante": [3, 2],
                    "dadi_difensore": [3, 2],
                },
                offset_sec=10,
            ),
        ]
        stat = calcola_statistiche(_crea_partita(), _crea_giocatori(), eventi)
        rosso = next(s for s in stat.statistiche_giocatori if s.nome == "Edo")

        assert rosso.n_attacchi == 2
        assert rosso.n_dadi_lanciati == 5  # 3+2
        assert rosso.media_dadi_lanciati == round((6+4+2+3+2) / 5, 2)
        # Primo attacco: att 0 dif 2. Secondo: att 2 dif 0. Totale: att 2 dif 2
        assert rosso.armate_perse_attaccando == 2
        assert rosso.armate_inflitte_attaccando == 2

    def test_turni_e_armate_piazzate(self) -> None:
        eventi = [
            _evento(TipoEvento.TURNO_INIZIATO, {"giocatore_id": "g-rosso"}),
            _evento(
                TipoEvento.ARMATE_PIAZZATE,
                {"giocatore_id": "g-rosso", "territorio": "k", "n": 5},
                offset_sec=1,
            ),
            _evento(
                TipoEvento.ARMATE_PIAZZATE,
                {"giocatore_id": "g-rosso", "territorio": "a", "n": 3},
                offset_sec=2,
            ),
            _evento(TipoEvento.TURNO_INIZIATO, {"giocatore_id": "g-blu"}, offset_sec=10),
        ]
        stat = calcola_statistiche(_crea_partita(), _crea_giocatori(), eventi)
        rosso = next(s for s in stat.statistiche_giocatori if s.nome == "Edo")

        assert stat.n_turni == 2
        assert rosso.n_armate_piazzate_totali == 8  # 5+3

    def test_carte_tris_conquiste(self) -> None:
        eventi = [
            _evento(
                TipoEvento.CARTA_PESCATA,
                {"giocatore_id": "g-rosso", "carta": {"territorio": "k", "simbolo": "cannone"}},
            ),
            _evento(
                TipoEvento.CARTA_PESCATA,
                {"giocatore_id": "g-rosso", "carta": {"territorio": "a", "simbolo": "fante"}},
                offset_sec=1,
            ),
            _evento(
                TipoEvento.TRIS_GIOCATO,
                {
                    "giocatore_id": "g-rosso",
                    "carte": [
                        {"territorio": "k", "simbolo": "cannone"},
                        {"territorio": "a", "simbolo": "cannone"},
                        {"territorio": "n", "simbolo": "cannone"},
                    ],
                },
                offset_sec=2,
            ),
            _evento(
                TipoEvento.TERRITORIO_CONQUISTATO,
                {"giocatore_id": "g-rosso", "territorio": "kamchatka"},
                offset_sec=3,
            ),
            _evento(
                TipoEvento.TERRITORIO_CONQUISTATO,
                {"giocatore_id": "g-rosso", "territorio": "alaska"},
                offset_sec=4,
            ),
        ]
        stat = calcola_statistiche(_crea_partita(), _crea_giocatori(), eventi)
        rosso = next(s for s in stat.statistiche_giocatori if s.nome == "Edo")

        assert rosso.n_carte_pescate == 2
        assert rosso.n_tris_giocati == 1
        assert rosso.n_territori_conquistati == 2

    def test_eventi_di_giocatori_inesistenti_ignorati(self) -> None:
        """Evento con giocatore_id che non è in lista → ignorato silenziosamente."""
        eventi = [
            _evento(
                TipoEvento.ATTACCO_RISOLTO,
                {
                    "giocatore_id": "fantasma",
                    "da": "k", "a": "a",
                    "dadi_attaccante": [6],
                    "dadi_difensore": [3],
                },
            ),
        ]
        stat = calcola_statistiche(_crea_partita(), _crea_giocatori(), eventi)
        # Nessun giocatore reale ha aggregato
        for sg in stat.statistiche_giocatori:
            assert sg.n_attacchi == 0
        # Ma il counter globale conta lo stesso (è un attacco osservato)
        assert stat.n_attacchi_totali == 1

    def test_eventi_dati_malformati_skippati(self) -> None:
        """Eventi con dati non-dict, campi mancanti, valori invalidi: niente crash."""
        eventi = [
            EventoValidato(
                id="ev-malformato-1", partita_id="test-partita-id",
                ts_evento=datetime(2026, 5, 7, 21, 0, tzinfo=UTC),
                tipo=TipoEvento.ATTACCO_RISOLTO,
                dati="non-un-dict",  # type: ignore[arg-type]
                evento_grezzo_id=None, validato_da="test",
            ),
            _evento(
                TipoEvento.ATTACCO_RISOLTO,
                {"dadi_attaccante": [6], "dadi_difensore": [3]},  # manca giocatore_id
                offset_sec=1,
            ),
            _evento(
                TipoEvento.ATTACCO_RISOLTO,
                {  # giocatore valido + dadi valori fuori range (filtrati)
                    "giocatore_id": "g-rosso",
                    "da": "k", "a": "a",
                    "dadi_attaccante": [99, 6, "tre"],  # 99 e "tre" filtrati
                    "dadi_difensore": [3],
                },
                offset_sec=2,
            ),
        ]
        # Non deve crashare
        stat = calcola_statistiche(_crea_partita(), _crea_giocatori(), eventi)
        rosso = next(s for s in stat.statistiche_giocatori if s.nome == "Edo")
        # Solo il terzo evento è aggregato; dadi validi solo [6]
        assert rosso.n_attacchi == 1
        assert rosso.n_dadi_lanciati == 1
        assert rosso.media_dadi_lanciati == 6.0

    def test_ordinamento_giocatori_per_ordine_seduta(self) -> None:
        """L'output rispetta l'ordine di seduta, non l'ordine di input."""
        giocatori_disordinati = list(reversed(_crea_giocatori()))
        stat = calcola_statistiche(_crea_partita(), giocatori_disordinati, [])
        nomi = [s.nome for s in stat.statistiche_giocatori]
        assert nomi == ["Edo", "Marco"]  # ordine_seduta 1, 2


# === Test endpoint ===


@pytest.mark.asyncio
async def test_endpoint_404_partita_inesistente(
    client_test: AsyncClient,
) -> None:
    risposta = await client_test.get("/api/partite/non-esiste/statistiche")
    assert risposta.status_code == 404


@pytest.mark.asyncio
async def test_endpoint_partita_vuota(
    client_test: AsyncClient, sessione_test: AsyncSession
) -> None:
    """Partita appena creata, nessun evento validato → metriche a 0."""
    p = Partita(
        data_inizio=datetime(2026, 5, 7, 21, 0, tzinfo=UTC),
        stato_review=StatoReview.GREZZA,
    )
    sessione_test.add(p)
    await sessione_test.flush()
    sessione_test.add(
        GiocatorePartita(
            partita_id=p.id, nome="Edo", colore="rosso", ordine_seduta=1
        )
    )
    await sessione_test.commit()

    risposta = await client_test.get(f"/api/partite/{p.id}/statistiche")
    assert risposta.status_code == 200
    body = risposta.json()
    assert body["n_eventi_validati"] == 0
    assert body["n_attacchi_totali"] == 0
    assert len(body["statistiche_giocatori"]) == 1
    assert body["statistiche_giocatori"][0]["nome"] == "Edo"
    assert body["statistiche_giocatori"][0]["n_attacchi"] == 0


@pytest.mark.asyncio
async def test_endpoint_con_attacco_validato(
    client_test: AsyncClient, sessione_test: AsyncSession
) -> None:
    """Crea partita + attacco validato, verifica metriche calcolate."""
    p = Partita(
        data_inizio=datetime(2026, 5, 7, 21, 0, tzinfo=UTC),
        stato_review=StatoReview.GREZZA,
    )
    sessione_test.add(p)
    await sessione_test.flush()
    rosso = GiocatorePartita(
        partita_id=p.id, nome="Edo", colore="rosso", ordine_seduta=1
    )
    sessione_test.add(rosso)
    await sessione_test.flush()

    sessione_test.add(
        EventoValidato(
            partita_id=p.id,
            ts_evento=datetime(2026, 5, 7, 21, 5, tzinfo=UTC),
            tipo=TipoEvento.ATTACCO_RISOLTO,
            dati={
                "giocatore_id": rosso.id,
                "da": "kamchatka",
                "a": "alaska",
                "dadi_attaccante": [6, 5, 4],
                "dadi_difensore": [3, 2],
            },
            evento_grezzo_id=None,
            validato_da="test",
        )
    )
    await sessione_test.commit()

    risposta = await client_test.get(f"/api/partite/{p.id}/statistiche")
    assert risposta.status_code == 200
    body = risposta.json()
    assert body["n_attacchi_totali"] == 1
    sg = body["statistiche_giocatori"][0]
    assert sg["n_attacchi"] == 1
    assert sg["n_dadi_lanciati"] == 3
    assert sg["media_dadi_lanciati"] == 5.0
    assert sg["armate_perse_attaccando"] == 0
    assert sg["armate_inflitte_attaccando"] == 2


# === Test integrazione motore: difensori_per_evento ===


@pytest.mark.asyncio
async def test_endpoint_calcola_difese_setup_completo(
    client_test: AsyncClient, sessione_test: AsyncSession
) -> None:
    """
    Setup completo + attacco vero: il motore deve riconoscere chi
    possedeva il territorio attaccato e popolare le statistiche di
    difesa del giocatore corretto.
    """
    from app.servizi.setup_automatico_servizio import (
        ServizioSetupAutomatico,
    )

    # Crea partita 2 giocatori e applica setup automatico
    p = Partita(
        data_inizio=datetime(2026, 5, 7, 21, 0, tzinfo=UTC),
        stato_review=StatoReview.GREZZA,
    )
    sessione_test.add(p)
    await sessione_test.flush()
    rosso = GiocatorePartita(
        partita_id=p.id, nome="Edo", colore="rosso", ordine_seduta=1
    )
    blu = GiocatorePartita(
        partita_id=p.id, nome="Marco", colore="blu", ordine_seduta=2
    )
    sessione_test.add_all([rosso, blu])
    await sessione_test.flush()

    # Setup automatico crea i 46 eventi territori_assegnati + obiettivi + partita_inizio
    await ServizioSetupAutomatico.genera(
        sessione_test, p.id, seed=42
    )
    await sessione_test.commit()

    # Cerco un attacco plausibile: un territorio mio adiacente a uno avversario
    from sqlalchemy import select as _sel

    from app.modelli import EventoValidato as _Ev
    eventi_setup = await sessione_test.execute(
        _sel(_Ev).where(_Ev.partita_id == p.id)
        .order_by(_Ev.ts_evento)
    )
    territori_rosso: set[str] = set()
    territori_blu: set[str] = set()
    for ev in eventi_setup.scalars():
        if ev.tipo == TipoEvento.TERRITORIO_ASSEGNATO_INIZIO and isinstance(ev.dati, dict):
            gid = ev.dati.get("giocatore_id")
            terr = ev.dati.get("territorio")
            if gid == rosso.id and isinstance(terr, str):
                territori_rosso.add(terr)
            elif gid == blu.id and isinstance(terr, str):
                territori_blu.add(terr)

    # Trova prima coppia adiacente rosso → blu
    from risiko_engine.mappa import adiacenti_a
    coppia: tuple[str, str] | None = None
    for terr_da in territori_rosso:
        for adj in adiacenti_a(terr_da):
            if adj in territori_blu:
                coppia = (terr_da, adj)
                break
        if coppia:
            break
    assert coppia is not None, "Setup random non ha generato coppie adiacenti"
    terr_da, terr_a = coppia

    # Ora un attacco: rosso da terr_da → blu su terr_a, dadi 6,4 vs 3 (rosso vince)
    sessione_test.add(
        EventoValidato(
            partita_id=p.id,
            ts_evento=datetime(2026, 5, 7, 22, 0, tzinfo=UTC),
            tipo=TipoEvento.ATTACCO_RISOLTO,
            dati={
                "giocatore_id": rosso.id,
                "da": terr_da,
                "a": terr_a,
                "dadi_attaccante": [6, 4],
                "dadi_difensore": [3],
            },
            evento_grezzo_id=None,
            validato_da="test",
        )
    )
    await sessione_test.commit()

    # Verifica statistiche
    risposta = await client_test.get(f"/api/partite/{p.id}/statistiche")
    assert risposta.status_code == 200
    body = risposta.json()
    sg_rosso = next(
        s for s in body["statistiche_giocatori"] if s["nome"] == "Edo"
    )
    sg_blu = next(
        s for s in body["statistiche_giocatori"] if s["nome"] == "Marco"
    )

    # Rosso ha attaccato 1 volta
    assert sg_rosso["n_attacchi"] == 1
    # Blu è stato attaccato 1 volta (popolato dal motore)
    assert sg_blu["n_difese"] == 1
    # Blu ha perso 1 armata difendendo (6>3 → dif perde)
    assert sg_blu["armate_perse_difendendo"] == 1
    # Blu non ha inflitto perdite (l'attaccante non ha perso)
    assert sg_blu["armate_inflitte_difendendo"] == 0


@pytest.mark.asyncio
async def test_endpoint_difese_zero_se_motore_non_inizializzabile(
    client_test: AsyncClient, sessione_test: AsyncSession
) -> None:
    """
    Partita con 1 solo giocatore: il motore non si inizializza
    (richiede 2-6), ma l'endpoint non deve crashare e le difese
    devono essere semplicemente a 0.
    """
    p = Partita(
        data_inizio=datetime(2026, 5, 7, 21, 0, tzinfo=UTC),
        stato_review=StatoReview.GREZZA,
    )
    sessione_test.add(p)
    await sessione_test.flush()
    sessione_test.add(
        GiocatorePartita(
            partita_id=p.id, nome="Solo", colore="rosso", ordine_seduta=1
        )
    )
    await sessione_test.commit()

    risposta = await client_test.get(f"/api/partite/{p.id}/statistiche")
    assert risposta.status_code == 200
    body = risposta.json()
    # Niente crash, difese a 0
    sg = body["statistiche_giocatori"][0]
    assert sg["n_difese"] == 0
    assert sg["armate_perse_difendendo"] == 0
