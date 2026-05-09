"""
Servizio di calcolo delle discrepanze fra stato del motore (derivato
dalla cronologia eventi) e stato dedotto dalle inferenze CV.

Algoritmo (puro, niente dipendenze CV):

Input:
- `stato_motore`: dict territorio_slug -> {"colore": str, "n_armate": int}
- `inferenze_cv`: list di InferenzaCV per la partita allo stesso istante

Output:
- list di `DivergenzaInferita` (non persistite, candidate al salvataggio)

Logica:
1. Aggrega le inferenze per (territorio, colore): ne viene fuori una
   mappa `cv_per_territorio_colore -> {n_armate, confidence_aggregata, ids}`.
2. Per ogni territorio nello stato_motore:
   a. Se c'è una corrispondenza CV con stesso colore e stesso n_armate
      → no divergenza.
   b. Se c'è una corrispondenza CV ma con n_armate diverso → divergenza
      con valore_motore != valore_cv.
   c. Se la CV non vede nulla per quel territorio (ma il motore sì)
      → divergenza con valore_cv=0.
3. Per ogni territorio visto dalla CV ma non presente nel motore (o con
   colore diverso) → divergenza con valore_motore=0.

Threshold di rilevanza:
- Le divergenze con `delta_assoluto == 0` non vengono prodotte (sono
  match perfetti, niente da rivedere).
- Le divergenze con confidence_cv < soglia_minima vengono comunque
  prodotte, ma con flag `risoluzione="aperta"` e l'utente può scartarle.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from dataclasses import field as dataclass_field

from app.modelli import InferenzaCV


@dataclass(frozen=True)
class StatoTerritorioMotore:
    """Stato che il motore di gioco ritiene di un territorio."""

    territorio: str
    colore: str
    n_armate: int


@dataclass(frozen=True)
class DivergenzaCalcolata:
    """
    Divergenza calcolata dal servizio (non ancora persistita).

    Il chiamante decide se persisterla creando un record
    `DivergenzaInferita` nel DB.
    """

    territorio: str
    colore: str
    valore_motore: int
    valore_cv: int
    confidence_cv: float
    delta_assoluto: int
    inferenze_correlate: list[str]


def calcola_discrepanze(
    stato_motore: list[StatoTerritorioMotore],
    inferenze_cv: list[InferenzaCV],
) -> list[DivergenzaCalcolata]:
    """
    Calcola le divergenze fra stato motore e stato CV.

    Args:
        stato_motore: lista di stati per (territorio, colore). Ogni
            tupla (territorio, colore) deve apparire al massimo una
            volta. Il chiamante derivata questa struttura dal motore
            (es. via `vista_arbitro()` su uno snapshot ricostruito).
        inferenze_cv: lista di InferenzaCV. Tipicamente filtrate per
            un dato `evento_validato_id` o `frame_hash`.

    Returns:
        Lista di divergenze ordinata per delta_assoluto decrescente.
        Le coppie (territorio, colore) con match perfetto sono escluse.
    """
    # 1. Aggrega inferenze per (territorio, colore)
    @dataclass
    class _Aggregato:
        n_armate: int = 0
        confidence_somma: float = 0.0
        n_inferenze: int = 0
        ids: list[str] = dataclass_field(default_factory=list)

    cv_aggregato: dict[tuple[str, str], _Aggregato] = defaultdict(_Aggregato)

    for inf in inferenze_cv:
        if inf.territorio is None or inf.colore is None:
            continue
        chiave = (inf.territorio, inf.colore)
        agg = cv_aggregato[chiave]
        agg.n_armate += inf.n_armate_stimate
        agg.confidence_somma += inf.confidence
        agg.n_inferenze += 1
        agg.ids.append(inf.id)

    # 2. Aggrega stato motore per (territorio, colore) per lookup veloce
    motore_per_chiave: dict[tuple[str, str], int] = {}
    for stato in stato_motore:
        chiave = (stato.territorio, stato.colore)
        if chiave in motore_per_chiave:
            raise ValueError(
                f"Stato motore duplicato per {chiave}: il chiamante deve "
                f"passare al massimo una entry per (territorio, colore)."
            )
        motore_per_chiave[chiave] = stato.n_armate

    divergenze: list[DivergenzaCalcolata] = []
    chiavi_viste = set()

    # 3. Itera lo stato motore: per ogni territorio cerca corrispondenza CV
    for chiave, n_motore in motore_per_chiave.items():
        chiavi_viste.add(chiave)
        territorio, colore = chiave
        agg_cv: _Aggregato | None = cv_aggregato.get(chiave)

        if agg_cv is None:
            # Il motore vede armate ma la CV no
            if n_motore == 0:
                continue  # entrambi 0, nessuna divergenza
            divergenze.append(DivergenzaCalcolata(
                territorio=territorio,
                colore=colore,
                valore_motore=n_motore,
                valore_cv=0,
                confidence_cv=0.0,
                delta_assoluto=n_motore,
                inferenze_correlate=[],
            ))
            continue

        if agg_cv.n_armate == n_motore:
            continue  # match perfetto

        confidence_media = agg_cv.confidence_somma / max(1, agg_cv.n_inferenze)

        divergenze.append(DivergenzaCalcolata(
            territorio=territorio,
            colore=colore,
            valore_motore=n_motore,
            valore_cv=agg_cv.n_armate,
            confidence_cv=confidence_media,
            delta_assoluto=abs(n_motore - agg_cv.n_armate),
            inferenze_correlate=list(agg_cv.ids),
        ))

    # 4. Itera la CV: per ogni (territorio, colore) NON visto dal motore
    for chiave, agg in cv_aggregato.items():
        if chiave in chiavi_viste:
            continue
        if agg.n_armate == 0:
            continue
        territorio, colore = chiave
        confidence_media = agg.confidence_somma / max(1, agg.n_inferenze)
        divergenze.append(DivergenzaCalcolata(
            territorio=territorio,
            colore=colore,
            valore_motore=0,
            valore_cv=agg.n_armate,
            confidence_cv=confidence_media,
            delta_assoluto=agg.n_armate,
            inferenze_correlate=list(agg.ids),
        ))

    # 5. Ordina per delta_assoluto decrescente
    divergenze.sort(key=lambda d: d.delta_assoluto, reverse=True)
    return divergenze


def stato_motore_da_snapshot(
    snapshot: dict[str, object],
) -> list[StatoTerritorioMotore]:
    """
    Helper: converte uno `StatoPartitaSnapshot` (dict serializzato) in
    una lista di `StatoTerritorioMotore`.

    Lo snapshot viene da `StatoPartitaRicostruito.stato_serializzato`
    nel DB. Schema atteso:
        {
            "territori": {
                "kamchatka": {"controllore_id": "rosso-uuid", "armate": 5},
                ...
            },
            "giocatori": [
                {"player_id": "rosso-uuid", "colore": "rosso", ...},
                ...
            ],
        }
    """
    territori = snapshot.get("territori") or {}
    giocatori = snapshot.get("giocatori") or []
    if not isinstance(territori, dict) or not isinstance(giocatori, list):
        return []

    # Mappa player_id -> colore
    id_a_colore: dict[str, str] = {}
    for g in giocatori:
        if not isinstance(g, dict):
            continue
        pid = g.get("player_id")
        col = g.get("colore")
        if isinstance(pid, str) and isinstance(col, str):
            id_a_colore[pid] = col

    risultato: list[StatoTerritorioMotore] = []
    for nome_terr, info in territori.items():
        if not isinstance(info, dict):
            continue
        controllore_id = info.get("controllore_id")
        armate = info.get("armate")
        if controllore_id is None or armate is None:
            continue
        if not isinstance(controllore_id, str) or not isinstance(armate, int):
            continue
        colore = id_a_colore.get(controllore_id)
        if colore is None:
            continue
        risultato.append(StatoTerritorioMotore(
            territorio=nome_terr,
            colore=colore,
            n_armate=armate,
        ))
    return risultato
