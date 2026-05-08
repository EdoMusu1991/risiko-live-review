"""
Endpoint per l'esportazione di una partita validata.

Due formati supportati via query param `formato`:
- `json` (default): bundle strutturato con eventi + stato finale
- `html`: report stampabile A4 autocontenuto
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.configurazione import get_sessione_db
from app.servizi.esportazione_servizio import ServizioEsportazione
from app.servizi.partita_servizio import PartitaInesistenteError

router = APIRouter(prefix="/partite", tags=["esportazione"])


@router.get(
    "/{partita_id}/esporta",
    summary="Esporta partita validata (JSON o HTML)",
    response_model=None,
    response_class=JSONResponse,
)
async def esporta_partita(
    partita_id: str,
    formato: Literal["json", "html", "replay"] = Query(
        default="json",
        description=(
            "Formato di esportazione:\n"
            "- 'json': bundle strutturato con eventi + stato finale\n"
            "- 'html': report stampabile A4 autocontenuto\n"
            "- 'replay': bundle conforme a @risiko/eventi-schema "
            "BundleReplay, consumabile da Battle Commander per il replay"
        ),
    ),
    db: AsyncSession = Depends(get_sessione_db),
) -> JSONResponse | HTMLResponse:
    """
    Esporta una partita in formato strutturato (JSON), stampabile (HTML),
    o replay-bundle per Battle Commander.

    Il bundle JSON include partita + giocatori + tutti gli eventi
    validati + snapshot fresco dello stato finale ricostruito.

    Il bundle replay è la versione "pulita" pensata per essere
    consumata da BC: niente metadati di esportazione, niente stato
    finale, ogni evento con `partita_id` esplicito.

    L'HTML è autocontenuto (CSS inline, niente JS) e ottimizzato per
    stampa A4. Adatto per archivio cartaceo del club.
    """
    try:
        dati = await ServizioEsportazione.prepara_dati(db, partita_id)
    except PartitaInesistenteError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e

    if formato == "html":
        html = ServizioEsportazione.serializza_html(dati)
        nome_file = f"risiko-partita-{partita_id[:8]}.html"
        return HTMLResponse(
            content=html,
            headers={
                "Content-Disposition": f'inline; filename="{nome_file}"',
            },
        )

    if formato == "replay":
        bundle = ServizioEsportazione.serializza_bundle_replay(dati)
        nome_file = f"risiko-replay-{partita_id[:8]}.json"
        return JSONResponse(
            content=bundle,
            headers={
                "Content-Disposition": f'attachment; filename="{nome_file}"',
            },
        )

    # JSON (default)
    bundle = ServizioEsportazione.serializza_json(dati)
    nome_file = f"risiko-partita-{partita_id[:8]}.json"
    return JSONResponse(
        content=bundle,
        headers={
            "Content-Disposition": f'attachment; filename="{nome_file}"',
        },
    )
