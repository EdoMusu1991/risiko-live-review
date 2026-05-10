"""
Scheduler in-process per task ricorrenti.

Usato per:
- Cleanup automatico dei bundle non promossi piu' vecchi di N giorni
  (`storage_partite/<id>/`). Senza questo, la cartella accumula bundle
  rimasti dimenticati nel filesystem Railway, mangiando il volume
  persistente.

Implementato con APScheduler `AsyncIOScheduler` perche' integra
nativamente con il loop asyncio di FastAPI e non richiede thread
separati. Lo scheduler viene avviato in `lifespan` di `app/main.py`
solo se `impostazioni.scheduler_abilitato` e' True (default False per
non avere side-effects nei test pytest).

Su Railway, settare `SCHEDULER_ABILITATO=true` come env var.
"""

from __future__ import annotations

import logging
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.configurazione import impostazioni
from app.servizi.promozione_bundle_servizio import cancella_bundle_vecchi

log = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def avvia_scheduler() -> None:
    """
    Avvia lo scheduler globale se `impostazioni.scheduler_abilitato == True`.

    Idempotente: una seconda chiamata e' no-op se lo scheduler e' gia' avviato.
    Sicura da chiamare anche se APScheduler non e' installato (lazy import
    sopra ha gia' fatto fail-fast in tal caso).
    """
    global _scheduler

    if not impostazioni.scheduler_abilitato:
        log.info("scheduler disabilitato (scheduler_abilitato=False)")
        return

    if _scheduler is not None and _scheduler.running:
        log.debug("scheduler gia' avviato, skip")
        return

    _scheduler = AsyncIOScheduler()

    # Parse "HH:MM"
    try:
        ora_str = impostazioni.bundle_cleanup_ora
        ora_h, ora_m = map(int, ora_str.split(":"))
    except (ValueError, AttributeError):
        log.warning(
            "bundle_cleanup_ora invalido (%r), uso default 03:00",
            impostazioni.bundle_cleanup_ora,
        )
        ora_h, ora_m = 3, 0

    _scheduler.add_job(
        _job_cleanup_bundle,
        trigger=CronTrigger(hour=ora_h, minute=ora_m),
        id="cleanup_bundle_vecchi",
        replace_existing=True,
        misfire_grace_time=3600,  # se il server era down, esegue entro 1h dal trigger
    )

    _scheduler.start()
    log.info(
        "scheduler avviato: cleanup bundle alle %02d:%02d (giorni=%d)",
        ora_h,
        ora_m,
        impostazioni.bundle_cleanup_giorni,
    )


def ferma_scheduler() -> None:
    """Ferma lo scheduler globale (chiamato da lifespan shutdown)."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        log.info("scheduler fermato")


def _job_cleanup_bundle() -> None:
    """Job ricorrente: cancella bundle non promossi piu' vecchi di N giorni."""
    giorni = impostazioni.bundle_cleanup_giorni
    log.info("cleanup_bundle: avvio (giorni=%d)", giorni)
    try:
        risultato = cancella_bundle_vecchi(giorni)
        log.info(
            "cleanup_bundle: cancellati %d bundle: %s",
            risultato["n_cancellati"],
            risultato["ids_cancellati"],
        )
    except Exception:
        log.exception("cleanup_bundle: errore durante l'esecuzione del job")


def stato_scheduler() -> dict[str, Any]:
    """
    Stato corrente dello scheduler (per endpoint di diagnostica).

    Ritorna `{abilitato, in_esecuzione, prossima_esecuzione, giorni_cleanup}`.
    """
    if not impostazioni.scheduler_abilitato:
        return {
            "abilitato": False,
            "in_esecuzione": False,
            "prossima_esecuzione": None,
            "giorni_cleanup": impostazioni.bundle_cleanup_giorni,
        }

    in_esecuzione = _scheduler is not None and _scheduler.running
    prossima: str | None = None
    if in_esecuzione and _scheduler is not None:
        try:
            job = _scheduler.get_job("cleanup_bundle_vecchi")
            if job is not None and job.next_run_time is not None:
                prossima = job.next_run_time.isoformat()
        except Exception:
            prossima = None

    return {
        "abilitato": True,
        "in_esecuzione": in_esecuzione,
        "prossima_esecuzione": prossima,
        "giorni_cleanup": impostazioni.bundle_cleanup_giorni,
    }
