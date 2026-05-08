"""
Servizio di esportazione di una partita validata.

Produce due formati:
- **JSON**: dump strutturato completo (partita + giocatori + eventi validati
  + stato finale ricostruito). Adatto per archivio digitale, re-import,
  analisi automatiche.
- **HTML**: report stampabile A4 autocontenuto (CSS inline, niente JS).
  Adatto per archivio cartaceo del club o invio per email.

Entrambi i formati includono uno snapshot fresco dello stato finale,
calcolato al momento dell'esportazione tramite il motore regole.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import UTC, datetime
from html import escape
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modelli import Partita
from app.servizi.partita_servizio import ServizioPartita
from app.servizi.ricostruzione_servizio import ServizioRicostruzione
from risiko_engine.mappa import TERRITORI, continente_di
from risiko_engine.obiettivi import OBIETTIVI

# Mappa nome continente canonico → label umano
_ETICHETTE_CONTINENTE: dict[str, str] = {
    "nordamerica": "Nord America",
    "sudamerica": "Sud America",
    "europa": "Europa",
    "africa": "Africa",
    "asia": "Asia",
    "oceania": "Oceania",
}

_BONUS_CONTINENTE: dict[str, int] = {
    "nordamerica": 5,
    "sudamerica": 2,
    "europa": 5,
    "africa": 3,
    "asia": 7,
    "oceania": 2,
}


@dataclass(frozen=True)
class DatiEsportazione:
    """Bundle dei dati necessari per generare un report."""

    partita: Partita
    eventi: list[dict[str, Any]]
    stato_finale: dict[str, Any] | None
    data_export: datetime


class ServizioEsportazione:
    """Genera bundle di esportazione (JSON e HTML) da una partita."""

    @staticmethod
    async def prepara_dati(
        db: AsyncSession,
        partita_id: str,
    ) -> DatiEsportazione:
        """
        Carica partita, eventi validati, e ricalcola lo stato finale.

        Solleva PartitaInesistenteError se la partita non esiste.
        """
        partita = await ServizioPartita.trova_per_id(db, partita_id)

        # Eager load eventi validati (la sessione async non supporta lazy loading)
        from sqlalchemy import select

        from app.modelli import EventoValidato

        stmt = (
            select(EventoValidato)
            .where(EventoValidato.partita_id == partita_id)
            .order_by(EventoValidato.ts_evento, EventoValidato.data_creazione)
        )
        risultato_ricostruzione = await db.execute(stmt)
        eventi_validati = list(risultato_ricostruzione.scalars().all())

        eventi_serializzati = [
            {
                "id": str(e.id),
                "ts_evento": e.ts_evento.isoformat(),
                "tipo": e.tipo.value if hasattr(e.tipo, "value") else str(e.tipo),
                "dati": e.dati,
                "validato_da": e.validato_da,
            }
            for e in eventi_validati
        ]

        # Ricostruzione "soft" per snapshot fresco
        try:
            risultato = await ServizioRicostruzione.ricostruisci(
                db, partita_id
            )
            stato = (
                dict(risultato.stato_serializzato)
                if risultato.stato_serializzato is not None
                else None
            )
            if stato is not None:
                stato["_n_errori_ricostruzione"] = (
                    risultato.n_eventi_totali - risultato.n_eventi_applicati
                )
                stato["_errori_ricostruzione"] = list(risultato.errori)
        except Exception:
            stato = None

        return DatiEsportazione(
            partita=partita,
            eventi=eventi_serializzati,
            stato_finale=stato,
            data_export=datetime.now(tz=eventi_validati[0].ts_evento.tzinfo)
            if eventi_validati
            else datetime.now(tz=UTC),
        )

    @staticmethod
    def serializza_json(dati: DatiEsportazione) -> dict[str, Any]:
        """Produce il dict JSON-serializzabile completo."""
        p = dati.partita
        return {
            "schema_version": "1.0",
            "data_esportazione": dati.data_export.isoformat(),
            "partita": {
                "id": str(p.id),
                "data_inizio": p.data_inizio.isoformat(),
                "data_fine": p.data_fine.isoformat() if p.data_fine else None,
                "luogo": p.luogo,
                "note": p.note,
                "stato_review": p.stato_review,
            },
            "giocatori": [
                {
                    "id": str(g.id),
                    "nome": g.nome,
                    "colore": g.colore,
                    "ordine_seduta": g.ordine_seduta,
                }
                for g in sorted(p.giocatori, key=lambda g: g.ordine_seduta)
            ],
            "eventi_validati": dati.eventi,
            "stato_finale": dati.stato_finale,
        }

    @staticmethod
    def serializza_csv(dati: DatiEsportazione) -> str:
        """
        Produce un dump CSV degli eventi validati per analytics esterne
        (Excel, Google Sheets, pandas, ecc.).

        Schema colonne (fissa, una riga per evento):
        - posizione: 1-based index cronologico
        - ts_evento: ISO 8601 con offset UTC se naive
        - tipo: tipo evento
        - giocatore_id: UUID del giocatore (se presente nei dati)
        - giocatore_nome: nome risolto via lookup (se trovato)
        - territorio_da: territorio sorgente (attacco/spostamento)
        - territorio_a: territorio bersaglio (attacco/spostamento)
        - n_armate: per ARMATE_PIAZZATE/ARMATE_SPOSTATE
        - dadi_attaccante: pipe-separated (es "6|4|2"), per ATTACCO_RISOLTO
        - dadi_difensore: pipe-separated, per ATTACCO_RISOLTO
        - dati_extra: JSON dei campi `dati` non già esposti come colonna

        Formato: RFC 4180-compliant, encoding UTF-8 con BOM (per Excel
        che altrimenti interpreta i caratteri italiani in Latin-1).
        """
        nomi_per_id = {str(g.id): g.nome for g in dati.partita.giocatori}

        buffer = io.StringIO()
        # Excel ha bisogno del BOM UTF-8 per riconoscere accenti italiani
        buffer.write("\ufeff")
        writer = csv.writer(buffer, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)

        writer.writerow([
            "posizione",
            "ts_evento",
            "tipo",
            "giocatore_id",
            "giocatore_nome",
            "territorio_da",
            "territorio_a",
            "n_armate",
            "dadi_attaccante",
            "dadi_difensore",
            "dati_extra",
        ])

        # Campi che diventano colonne dedicate (escludiamoli da dati_extra)
        campi_in_colonne = {
            "giocatore_id", "da", "a", "territorio", "n",
            "dadi_attaccante", "dadi_difensore",
        }

        for i, ev in enumerate(dati.eventi, start=1):
            d = ev.get("dati") or {}
            if not isinstance(d, dict):
                d = {}

            gid = d.get("giocatore_id") or ""
            nome = nomi_per_id.get(str(gid), "") if gid else ""

            # Territorio: ARMATE_PIAZZATE usa "territorio", ATTACCO/SPOSTAMENTO usa "da"/"a"
            terr_da = d.get("da") or d.get("territorio") or ""
            terr_a = d.get("a") or ""

            n_armate = d.get("n", "")

            dadi_att = _formatta_dadi_csv(d.get("dadi_attaccante"))
            dadi_dif = _formatta_dadi_csv(d.get("dadi_difensore"))

            # Dati extra: tutto ciò che non è già in colonne
            extra = {k: v for k, v in d.items() if k not in campi_in_colonne}
            extra_json = ""
            if extra:
                import json as _json
                extra_json = _json.dumps(extra, ensure_ascii=False, default=str)

            writer.writerow([
                i,
                ev.get("ts_evento", ""),
                ev.get("tipo", ""),
                gid,
                nome,
                terr_da,
                terr_a,
                n_armate,
                dadi_att,
                dadi_dif,
                extra_json,
            ])

        return buffer.getvalue()

    @staticmethod
    def serializza_bundle_replay(dati: DatiEsportazione) -> dict[str, Any]:
        """
        Produce un bundle conforme allo schema `@risiko/eventi-schema`
        BundleReplay (zod). Usato da Battle Commander per il replay
        di partite registrate al club.

        Differenze dal `serializza_json`:
        - Campo eventi si chiama `eventi` (non `eventi_validati`)
        - Niente campi extra (`data_esportazione`, `stato_review`,
          `stato_finale`) — il bundle replay è puro stream eventi
        - Ogni evento include `partita_id` per consistenza con il
          contratto stabile dello schema
        - I `ts_evento` sono normalizzati con timezone UTC (su SQLite
          arrivano naive; lo schema zod richiede ISO 8601 con offset)
        """
        p = dati.partita
        eventi_normalizzati = [
            {**e, "partita_id": str(p.id), "ts_evento": _ts_aware_iso(e["ts_evento"])}
            for e in dati.eventi
        ]
        return {
            "schema_version": "1.0",
            "partita": {
                "id": str(p.id),
                "data_inizio": _ts_aware_iso(p.data_inizio.isoformat()),
                "data_fine": (
                    _ts_aware_iso(p.data_fine.isoformat()) if p.data_fine else None
                ),
                "luogo": p.luogo,
                "note": p.note,
            },
            "giocatori": [
                {
                    "id": str(g.id),
                    "nome": g.nome,
                    "colore": (
                        g.colore.value if hasattr(g.colore, "value") else g.colore
                    ),
                    "ordine_seduta": g.ordine_seduta,
                }
                for g in sorted(p.giocatori, key=lambda g: g.ordine_seduta)
            ],
            "eventi": eventi_normalizzati,
        }

    @staticmethod
    def serializza_html(dati: DatiEsportazione) -> str:
        """
        Produce un report HTML stampabile, autocontenuto (CSS inline).

        L'HTML è pensato per A4 stampato: una pagina con riepilogo,
        cronologia eventi compatta, e riepilogo stato finale per
        giocatore.
        """
        p = dati.partita
        giocatori = sorted(p.giocatori, key=lambda g: g.ordine_seduta)
        nomi_per_id = {str(g.id): g.nome for g in giocatori}
        colori_per_id: dict[str, str] = {str(g.id): g.colore for g in giocatori}

        # Header
        titolo = "Risiko Live · Resoconto partita"
        sottotitolo = _formato_data_estesa(p.data_inizio)

        meta_righe: list[str] = []
        if p.luogo:
            meta_righe.append(f"<strong>Luogo:</strong> {escape(p.luogo)}")
        if p.note:
            meta_righe.append(f"<strong>Note:</strong> {escape(p.note)}")
        meta_righe.append(
            f"<strong>Stato review:</strong> {escape(p.stato_review)}"
        )
        meta_righe.append(
            f"<strong>Eventi validati:</strong> {len(dati.eventi)}"
        )
        meta_html = " · ".join(meta_righe)

        # Roster giocatori
        roster_html = "\n".join(
            f"""
            <div class="giocatore">
                <span class="pallino" style="background: {_HEX_COLORI[g.colore]}"></span>
                <span class="nome">{escape(g.nome)}</span>
                <span class="meta">seduta {g.ordine_seduta} · {g.colore}</span>
            </div>
            """
            for g in giocatori
        )

        # Cronologia
        cronologia_html = _genera_cronologia_html(
            dati.eventi, nomi_per_id
        )

        # Stato finale
        stato_html = _genera_stato_finale_html(
            dati.stato_finale, nomi_per_id, colori_per_id
        )

        # Footer
        footer = (
            f"Esportato il {_formato_data_estesa(dati.data_export)} · "
            f"Partita ID {str(p.id)[:8]}…"
        )

        return _TEMPLATE_HTML.format(
            titolo=escape(titolo),
            sottotitolo=escape(sottotitolo),
            meta=meta_html,
            roster=roster_html,
            cronologia=cronologia_html,
            stato_finale=stato_html,
            footer=escape(footer),
        )


# === HTML helpers ===

_HEX_COLORI: dict[str, str] = {
    "rosso": "#b8332a",
    "blu": "#1f3552",
    "verde": "#2c4a36",
    "giallo": "#c8902b",
    "nero": "#1a1614",
    "viola": "#5e2d56",
}


def _formatta_dadi_csv(v: object) -> str:
    """Formatta una lista di dadi come stringa pipe-separated (es '6|4|2')."""
    if not isinstance(v, list):
        return ""
    return "|".join(str(d) for d in v if isinstance(d, int))


def _ts_aware_iso(ts_iso: str) -> str:
    """
    Converte un timestamp ISO in formato aware (con offset UTC se naive).

    SQLite memorizza datetime senza timezone; quando SQLAlchemy li legge
    arrivano naive. Il bundle replay deve avere ISO 8601 con offset
    perché il consumer (Battle Commander, schema zod) lo richiede.

    Se la stringa contiene già `+`, `-` (dopo la T) o `Z` la lascia
    intatta. Altrimenti aggiunge `+00:00` assumendo UTC.
    """
    # Cerca offset dopo la 'T'
    indice_t = ts_iso.find("T")
    if indice_t == -1:
        return ts_iso  # non sembra ISO, lascio passare
    parte_orario = ts_iso[indice_t:]
    if "+" in parte_orario or parte_orario.endswith("Z"):
        return ts_iso
    # Cerca segno '-' nell'orario (dopo eventuali ':' e '.')
    # Se c'è qualsiasi '-' dopo la T è un offset negativo
    if "-" in parte_orario:
        return ts_iso
    return ts_iso + "+00:00"


def _formato_data_estesa(d: datetime) -> str:
    """'martedì 7 maggio 2026, 21:00' (italiano)."""
    giorni = [
        "lunedì",
        "martedì",
        "mercoledì",
        "giovedì",
        "venerdì",
        "sabato",
        "domenica",
    ]
    mesi = [
        "gennaio",
        "febbraio",
        "marzo",
        "aprile",
        "maggio",
        "giugno",
        "luglio",
        "agosto",
        "settembre",
        "ottobre",
        "novembre",
        "dicembre",
    ]
    return (
        f"{giorni[d.weekday()]} {d.day} {mesi[d.month - 1]} {d.year}, "
        f"{d.hour:02d}:{d.minute:02d}"
    )


def _formato_territorio(slug: str) -> str:
    return " ".join(p.capitalize() for p in slug.split("_"))


def _genera_cronologia_html(
    eventi: list[dict[str, Any]],
    nomi_per_id: dict[str, str],
) -> str:
    if not eventi:
        return '<p class="vuoto">Nessun evento validato.</p>'

    righe: list[str] = []
    for i, e in enumerate(eventi, start=1):
        ts = datetime.fromisoformat(e["ts_evento"])
        ora = f"{ts.hour:02d}:{ts.minute:02d}:{ts.second:02d}"
        tipo = e["tipo"].replace("_", " ")
        descrizione = _descrivi_evento(e, nomi_per_id)
        righe.append(
            f"""
            <tr>
                <td class="num">{i}</td>
                <td class="ora">{ora}</td>
                <td class="tipo">{escape(tipo)}</td>
                <td class="dett">{descrizione}</td>
            </tr>
            """
        )

    return f"""
    <table class="cronologia">
        <thead>
            <tr>
                <th>#</th>
                <th>Ora</th>
                <th>Tipo</th>
                <th>Dettagli</th>
            </tr>
        </thead>
        <tbody>
            {"".join(righe)}
        </tbody>
    </table>
    """


def _descrivi_evento(
    evento: dict[str, Any],
    nomi_per_id: dict[str, str],
) -> str:
    """Descrizione testuale leggibile dell'evento."""
    d = evento["dati"]
    tipo = evento["tipo"]

    def gioc(key: str) -> str:
        gid = d.get(key)
        if isinstance(gid, str) and gid in nomi_per_id:
            return escape(nomi_per_id[gid])
        return "?"

    def terr(key: str) -> str:
        v = d.get(key)
        if isinstance(v, str):
            return escape(_formato_territorio(v))
        return "?"

    if tipo == "partita_inizio":
        return f"Inizia <strong>{gioc('primo_giocatore_id')}</strong>"
    if tipo == "territorio_assegnato_inizio":
        return (
            f"<strong>{gioc('giocatore_id')}</strong> riceve "
            f"<em>{terr('territorio')}</em> "
            f"({d.get('n_armate', '?')} armate)"
        )
    if tipo == "obiettivo_assegnato":
        return (
            f"<strong>{gioc('giocatore_id')}</strong> riceve obiettivo "
            f"#{d.get('obiettivo_id', '?')}"
        )
    if tipo == "armate_piazzate":
        return (
            f"<strong>{gioc('giocatore_id')}</strong> piazza "
            f"<strong>{d.get('n', '?')}</strong> armate su "
            f"<em>{terr('territorio')}</em>"
        )
    if tipo == "tris_giocato":
        return f"<strong>{gioc('giocatore_id')}</strong> gioca un tris"
    if tipo == "attacco_risolto":
        att = d.get("dadi_attaccante", []) or []
        dif = d.get("dadi_difensore", []) or []
        return (
            f"<strong>{gioc('giocatore_id')}</strong> attacca "
            f"<em>{terr('a')}</em> da <em>{terr('da')}</em> · "
            f"dadi {att} vs {dif}"
        )
    if tipo == "armate_spostate":
        return (
            f"<strong>{gioc('giocatore_id')}</strong> sposta "
            f"<strong>{d.get('n', '?')}</strong> da <em>{terr('da')}</em> "
            f"a <em>{terr('a')}</em>"
        )
    if tipo == "turno_finito":
        return f"Fine turno di <strong>{gioc('giocatore_id')}</strong>"
    if tipo == "partita_fine":
        return f"Vince <strong>{gioc('vincitore_id')}</strong>"
    if tipo == "nota":
        return f"<em>{escape(str(d.get('testo', '')))}</em>"

    # Fallback
    return f"<code>{escape(str(d))}</code>"


def _genera_stato_finale_html(
    stato: dict[str, Any] | None,
    nomi_per_id: dict[str, str],
    colori_per_id: dict[str, str],
) -> str:
    if stato is None:
        return '<p class="vuoto">Stato finale non disponibile (ricostruzione fallita).</p>'

    fase = stato.get("fase_corrente", "?").replace("_", " ")
    turno = stato.get("turno", "?")
    vincitore_id = stato.get("vincitore_id")
    vincitore_html = ""
    if isinstance(vincitore_id, str):
        nome = nomi_per_id.get(vincitore_id, "?")
        vincitore_html = (
            f'<div class="vincitore">🏆 Vincitore: '
            f"<strong>{escape(nome)}</strong></div>"
        )

    n_errori = stato.get("_n_errori_ricostruzione", 0)
    avviso_errori = (
        f'<div class="avviso">⚠ {n_errori} errori durante la ricostruzione.</div>'
        if n_errori
        else ""
    )

    territori = stato.get("territori", {})
    giocatori_list = stato.get("giocatori", [])

    # Per giocatore: territori controllati + armate totali
    blocchi_giocatore: list[str] = []
    for g in giocatori_list:
        pid = g.get("player_id", "")
        nome = nomi_per_id.get(pid, g.get("nome", "?"))
        colore = colori_per_id.get(pid, g.get("colore", "rosso"))
        controllati = [
            (slug, info)
            for slug, info in territori.items()
            if info.get("controllore_id") == pid
        ]
        controllati.sort(key=lambda t: t[0])
        n_terr = len(controllati)
        n_armate = sum(int(info.get("armate", 0)) for _, info in controllati)
        n_carte = stato.get("conteggio_mani", {}).get(pid, 0)
        eliminato = " (eliminato)" if g.get("eliminato") else ""

        lista_territori = ", ".join(
            f"<span class='terr'>{escape(_formato_territorio(slug))}"
            f"<sup>{info.get('armate', 0)}</sup></span>"
            for slug, info in controllati
        )

        blocchi_giocatore.append(
            f"""
            <article class="riassunto-giocatore">
                <header>
                    <span class="pallino" style="background:{_HEX_COLORI[colore]}"></span>
                    <strong>{escape(nome)}</strong>{eliminato}
                    <span class="conteggi">
                        {n_terr} territori · {n_armate} armate · {n_carte} carte
                    </span>
                </header>
                <p class="lista-terr">{lista_territori or "<em>nessun territorio</em>"}</p>
            </article>
            """
        )

    # Continenti dominati
    domini: list[str] = []
    raggruppati: dict[str, list[str]] = {}
    for nome_t in TERRITORI:
        c = continente_di(nome_t)
        nome_c = c if isinstance(c, str) else c.value
        raggruppati.setdefault(nome_c, []).append(nome_t)

    for cont, lista in sorted(raggruppati.items()):
        controllori_unici = {
            territori.get(t, {}).get("controllore_id") for t in lista
        }
        if len(controllori_unici) == 1:
            unico = next(iter(controllori_unici))
            if isinstance(unico, str):
                nome = nomi_per_id.get(unico, "?")
                etichetta = _ETICHETTE_CONTINENTE.get(cont, cont)
                bonus = _BONUS_CONTINENTE.get(cont, 0)
                domini.append(
                    f"<li><strong>{escape(etichetta)}</strong> dominato da "
                    f"<strong>{escape(nome)}</strong> (+{bonus})</li>"
                )

    domini_html = (
        f'<section><h3>Continenti dominati</h3><ul>{"".join(domini)}</ul></section>'
        if domini
        else ""
    )

    return f"""
    <div class="stato-meta">
        Fase: <strong>{escape(fase)}</strong> · Turno {turno}
    </div>
    {vincitore_html}
    {avviso_errori}
    <div class="riassunti">
        {"".join(blocchi_giocatore)}
    </div>
    {domini_html}
    """


_TEMPLATE_HTML = """<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<title>{titolo} — {sottotitolo}</title>
<style>
@page {{ size: A4; margin: 1.5cm; }}

body {{
    font-family: "Inter Tight", "Helvetica Neue", Arial, sans-serif;
    color: #1a1614;
    background: #f4ede0;
    line-height: 1.5;
    max-width: 800px;
    margin: 0 auto;
    padding: 24px;
}}
h1, h2, h3 {{
    font-family: "Fraunces", "Times New Roman", serif;
    letter-spacing: -0.02em;
    margin: 0 0 8px 0;
}}
h1 {{
    font-size: 28pt;
    font-weight: 900;
    color: #1a1614;
    border-bottom: 2px solid #1a1614;
    padding-bottom: 8px;
}}
h2 {{
    font-size: 16pt;
    font-weight: 700;
    margin-top: 32px;
    color: #b8332a;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    border-bottom: 1px solid #1a161430;
    padding-bottom: 4px;
}}
h3 {{
    font-size: 12pt;
    font-weight: 600;
    margin-top: 16px;
    color: #5c5147;
}}
.sottotitolo {{
    font-style: italic;
    color: #5c5147;
    font-size: 11pt;
    margin-bottom: 4px;
}}
.meta {{
    font-size: 9pt;
    color: #5c5147;
    margin-bottom: 24px;
}}
.giocatori {{
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    margin-bottom: 16px;
}}
.giocatore {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    border: 1px solid #1a161420;
    background: #faf6ec;
    font-size: 10pt;
}}
.pallino {{
    display: inline-block;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    border: 1px solid #1a161430;
}}
.giocatore .nome {{ font-weight: 600; }}
.giocatore .meta {{
    color: #5c5147;
    font-size: 8pt;
    margin: 0;
}}
table.cronologia {{
    width: 100%;
    border-collapse: collapse;
    font-size: 9pt;
}}
table.cronologia th {{
    background: #ebe1cd;
    padding: 6px 8px;
    text-align: left;
    text-transform: uppercase;
    font-size: 8pt;
    letter-spacing: 0.08em;
    border-bottom: 1px solid #1a161430;
}}
table.cronologia td {{
    padding: 4px 8px;
    border-bottom: 1px solid #1a161410;
    vertical-align: top;
}}
table.cronologia td.num {{
    color: #8a7d70;
    font-family: monospace;
    text-align: right;
    width: 32px;
}}
table.cronologia td.ora {{
    font-family: monospace;
    color: #5c5147;
    width: 70px;
    white-space: nowrap;
}}
table.cronologia td.tipo {{
    color: #1a1614;
    font-weight: 600;
    width: 140px;
    white-space: nowrap;
}}
table.cronologia td.dett {{
    color: #1a1614;
}}
.stato-meta {{
    font-family: monospace;
    margin: 8px 0;
    color: #5c5147;
}}
.vincitore {{
    background: #b8332a10;
    border-left: 3px solid #b8332a;
    padding: 8px 12px;
    margin: 8px 0;
    font-size: 12pt;
}}
.avviso {{
    background: #c8902b10;
    border-left: 3px solid #c8902b;
    padding: 6px 10px;
    margin: 8px 0;
    font-size: 10pt;
}}
.riassunti {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    margin-top: 12px;
    page-break-inside: auto;
}}
.riassunto-giocatore {{
    border: 1px solid #1a161420;
    padding: 10px 12px;
    background: #faf6ec;
    page-break-inside: avoid;
}}
.riassunto-giocatore header {{
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
    margin-bottom: 6px;
}}
.riassunto-giocatore .conteggi {{
    margin-left: auto;
    font-size: 9pt;
    color: #5c5147;
    font-family: monospace;
}}
.riassunto-giocatore .lista-terr {{
    margin: 6px 0 0 0;
    font-size: 9pt;
    line-height: 1.6;
}}
.terr {{
    display: inline-block;
    margin-right: 6px;
}}
.terr sup {{
    font-family: monospace;
    color: #b8332a;
    font-weight: 600;
}}
.vuoto {{
    color: #8a7d70;
    font-style: italic;
}}
ul {{ margin: 6px 0; padding-left: 20px; }}
li {{ margin: 2px 0; }}
footer {{
    margin-top: 32px;
    padding-top: 12px;
    border-top: 1px solid #1a161420;
    font-size: 8pt;
    color: #8a7d70;
    text-align: center;
}}
@media print {{
    body {{ background: white; }}
    h2 {{ page-break-after: avoid; }}
    .riassunto-giocatore {{ page-break-inside: avoid; }}
}}
</style>
</head>
<body>
<header>
    <div class="sottotitolo">Il Gufo · Roma — Risiko Live Review</div>
    <h1>{titolo}</h1>
    <div class="sottotitolo">{sottotitolo}</div>
    <div class="meta">{meta}</div>
</header>

<section>
    <h2>Giocatori al tavolo</h2>
    <div class="giocatori">{roster}</div>
</section>

<section>
    <h2>Stato finale</h2>
    {stato_finale}
</section>

<section>
    <h2>Cronologia eventi</h2>
    {cronologia}
</section>

<footer>{footer}</footer>
</body>
</html>
"""

# Re-export per ridurre coupling con OBIETTIVI (non usato qui ma utile in futuro)
_ = OBIETTIVI
