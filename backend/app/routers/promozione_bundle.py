"""
Endpoint di promozione bundle mobile → Partita SQL.

Workflow:
1. App mobile: POST /api/import/bundle-mobile (router import_bundle_mobile)
   → bundle deposita in `storage_partite/<id_partita>/`
2. Arbitro/operatore: GET /api/partite/bundle-disponibili
   → vede i bundle in attesa di promozione
3. Arbitro: POST /api/partite/da-bundle/{id_partita}
   → crea record Partita SQL + Video + EventoGrezzo, attiva il flusso review

Solo il punto 3 attiva il pipeline downstream (aggregazione, ricostruzione,
discrepanze CV, ecc.). Il bundle puo' restare in storage_partite per giorni
prima di essere promosso (utile se l'arbitro non e' lo stesso del cameraman).
"""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.configurazione import get_sessione_db
from app.schemi.promozione_bundle import (
    BundleDisponibile,
    RichiestaPromozioneBundle,
    RispostaListaBundle,
    RispostaPromozioneBundle,
)
from app.servizi.promozione_bundle_servizio import (
    BundleCorruttoError,
    BundleNonTrovatoError,
    PartitaGiaPromossaError,
    cancella_bundle,
    cancella_bundle_vecchi,
    lista_bundle_disponibili,
    promuovi_bundle_a_partita,
)

router = APIRouter(prefix="/partite", tags=["partite"])


@router.get(
    "/bundle-disponibili",
    response_model=RispostaListaBundle,
    summary="Lista bundle mobile in attesa di promozione a Partita SQL",
)
async def get_bundle_disponibili() -> RispostaListaBundle:
    bundles = lista_bundle_disponibili()
    return RispostaListaBundle(
        bundle=[
            BundleDisponibile(
                id_partita=b["id_partita"],
                ts_inizio=b["ts_inizio"],
                ts_fine=b["ts_fine"],
                n_segmenti=int(b["n_segmenti"]),
                n_eventi_dichiarati=int(b["n_eventi_dichiarati"]),
            )
            for b in bundles
        ]
    )


@router.post(
    "/da-bundle/{id_partita}",
    response_model=RispostaPromozioneBundle,
    status_code=status.HTTP_201_CREATED,
    summary="Promuove un bundle gia' uploadato a Partita SQL completa",
)
async def post_promuovi_bundle(
    id_partita: str,
    body: RichiestaPromozioneBundle | None = Body(default=None),
    db: AsyncSession = Depends(get_sessione_db),
) -> RispostaPromozioneBundle:
    luogo = body.luogo if body else None
    note_extra = body.note_extra if body else None

    try:
        risultato = await promuovi_bundle_a_partita(
            db,
            id_partita,
            luogo=luogo,
            note_extra=note_extra,
        )
    except BundleNonTrovatoError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except BundleCorruttoError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except PartitaGiaPromossaError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e

    return RispostaPromozioneBundle(
        id_partita=str(risultato["id_partita"]),
        n_video=int(risultato["n_video"]),  # type: ignore[arg-type]
        n_eventi_importati=int(risultato["n_eventi_importati"]),  # type: ignore[arg-type]
        n_eventi_scartati=int(risultato["n_eventi_scartati"]),  # type: ignore[arg-type]
        avvisi=list(risultato["avvisi"]),  # type: ignore[arg-type]
    )


@router.delete(
    "/bundle/{id_partita}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Scarta un bundle non promosso (cancella la cartella in storage_partite/)",
)
async def delete_bundle(id_partita: str) -> None:
    """
    Cancella la cartella `storage_partite/<id_partita>/` con tutto il
    suo contenuto (manifest, segmenti video, eventi).

    Idempotente: se la cartella non esiste, ritorna comunque 204.
    """
    cancella_bundle(id_partita)


@router.delete(
    "/bundle",
    summary="Cleanup: cancella bundle piu' vecchi di N giorni (default 30)",
)
async def delete_bundle_vecchi(
    older_than_days: int = 30,
) -> dict[str, int | list[str]]:
    """
    Cancella tutti i bundle in `storage_partite/` la cui registrazione e'
    finita oltre N giorni fa. Bundle con manifest illeggibile vengono
    saltati per sicurezza.

    Utile come endpoint di cron job manuale o batch. Per cron schedulato,
    chiamare via curl quotidiano.
    """
    if older_than_days < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="older_than_days deve essere >= 1",
        )
    return cancella_bundle_vecchi(older_than_days)
