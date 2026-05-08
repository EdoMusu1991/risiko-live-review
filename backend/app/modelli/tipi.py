"""
Enumerazioni del dominio Risiko, condivise tra modelli, schemi e logica.
"""

from enum import StrEnum


class StatoReview(StrEnum):
    """Stato di una partita nel ciclo di review."""

    GREZZA = "grezza"
    """La partita è stata creata e ha eventi grezzi, ma non è ancora stata revisionata."""

    IN_REVIEW = "in_review"
    """L'utente sta validando gli eventi."""

    VALIDATA = "validata"
    """Tutti gli eventi sono stati validati e la partita è stata ricostruita."""

    ARCHIVIATA = "archiviata"
    """Partita validata e archiviata, in sola lettura."""


class TipoEvento(StrEnum):
    """Tipi di evento osservabili durante una partita."""

    # Eventi di gioco regolari
    PARTITA_INIZIO = "partita_inizio"
    PARTITA_FINE = "partita_fine"

    # Setup
    TERRITORIO_ASSEGNATO_INIZIO = "territorio_assegnato_inizio"
    OBIETTIVO_ASSEGNATO = "obiettivo_assegnato"

    # Turni
    TURNO_INIZIATO = "turno_iniziato"
    TURNO_FINITO = "turno_finito"

    # Rinforzo
    ARMATE_PIAZZATE = "armate_piazzate"
    TRIS_GIOCATO = "tris_giocato"

    # Attacco
    DADI_LANCIATI = "dadi_lanciati"
    ATTACCO_RISOLTO = "attacco_risolto"
    TERRITORIO_CONQUISTATO = "territorio_conquistato"

    # Spostamento
    ARMATE_SPOSTATE = "armate_spostate"

    # Carte
    CARTA_PESCATA = "carta_pescata"
    MAZZO_RIGIRATO = "mazzo_rigirato"

    # Eventi grezzi catturati dal CV (da raffinare in fase review)
    CV_PESCA_RILEVATA = "cv_pesca_rilevata"
    CV_TRIS_RILEVATO = "cv_tris_rilevato"
    CV_MOVIMENTO_CARRI = "cv_movimento_carri"

    # Note
    NOTA = "nota"


class FonteEvento(StrEnum):
    """Da dove proviene un evento."""

    DADO_BLE = "dado_ble"
    """GoDice via Bluetooth Low Energy. Alta confidenza."""

    QR_RETRO_CARTA = "qr_retro_carta"
    """QR letto dal retro di una carta in pesca. Alta confidenza."""

    QR_FRONTE_CARTA = "qr_fronte_carta"
    """QR letto dal fronte di una carta scoperta. Alta confidenza."""

    CV_AUTOMATICO = "cv_automatico"
    """Modello CV ha rilevato l'evento. Confidenza variabile."""

    INPUT_MANUALE = "input_manuale"
    """L'utente ha inserito o validato l'evento manualmente."""


class ColoreGiocatore(StrEnum):
    """I 6 colori canonici del Risiko classico EG. Speculare a risiko_engine."""

    ROSSO = "rosso"
    BLU = "blu"
    VERDE = "verde"
    GIALLO = "giallo"
    NERO = "nero"
    VIOLA = "viola"
