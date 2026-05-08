"""Servizi business logic dell'applicazione."""

from app.servizi.partita_servizio import (
    ColoriDuplicatiError,
    EventoInesistenteError,
    OrdineSedutaInvalidoError,
    PartitaInesistenteError,
    ServizioEventiGrezzi,
    ServizioEventiValidati,
    ServizioPartita,
    StatoReviewIncompatibileError,
)
from app.servizi.ricostruzione_servizio import (
    PayloadInvalidoError,
    RicostruzioneError,
    ServizioRicostruzione,
    TipoEventoNonSupportatoError,
)
from app.servizi.setup_automatico_servizio import (
    NumeroGiocatoriNonSupportatoError,
    RisultatoSetup,
    ServizioSetupAutomatico,
    SetupGiaPresenteError,
)
from app.servizi.video_servizio import ServizioVideo, VideoInesistenteError

__all__ = [
    "ColoriDuplicatiError",
    "EventoInesistenteError",
    "NumeroGiocatoriNonSupportatoError",
    "OrdineSedutaInvalidoError",
    "PartitaInesistenteError",
    "PayloadInvalidoError",
    "RicostruzioneError",
    "RisultatoSetup",
    "ServizioEventiGrezzi",
    "ServizioEventiValidati",
    "ServizioPartita",
    "ServizioRicostruzione",
    "ServizioSetupAutomatico",
    "ServizioVideo",
    "SetupGiaPresenteError",
    "StatoReviewIncompatibileError",
    "TipoEventoNonSupportatoError",
    "VideoInesistenteError",
]
