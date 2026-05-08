"""
Schemi per le proposte di aggregazione di eventi BLE.

Quando l'app mobile registra una partita, ogni dado lanciato genera un
evento `EventoGrezzo` separato (tipo=DADI_LANCIATI, fonte=DADO_BLE,
dati={"ble_id", "ruolo", "slot", "valore"}).

Il servizio di aggregazione raggruppa questi eventi grezzi in proposte
di `attacco_risolto` candidato, basandosi su clustering temporale.

L'utente in fase di review accetta/modifica/rifiuta ogni proposta:
- accettare → crea un `EventoValidato` di tipo `ATTACCO_RISOLTO`
- modificare → cambia i valori prima di accettare
- rifiutare → marca gli eventi grezzi come da ignorare

Il servizio NON crea automaticamente eventi validati: si limita a
proporre. La supervisione umana è mantenuta perché:
- Mancano i dati di contesto (giocatore, territori `da`/`a`)
- Il clustering temporale può sbagliare (es. dadi vicini ma di attacchi
  consecutivi senza gap netto)
"""

from datetime import datetime

from pydantic import BaseModel, Field


class PropostaAggregazioneDadi(BaseModel):
    """
    Una proposta di aggregazione di N eventi `DADI_LANCIATI` BLE in un
    singolo `attacco_risolto` candidato.

    Contiene solo i dadi (estratti dal BLE). I campi mancanti per
    creare un `DatiAttaccoRisolto` finale (`giocatore_id`, `da`, `a`)
    devono essere forniti dall'utente in fase di accettazione.
    """

    ts_inizio: datetime = Field(
        ..., description="Timestamp del primo evento BLE del cluster"
    )
    ts_fine: datetime = Field(
        ..., description="Timestamp dell'ultimo evento BLE del cluster"
    )
    dadi_attaccante: list[int] = Field(
        default_factory=list,
        description="Valori dei dadi attaccante (1..6, max 3)",
    )
    dadi_difensore: list[int] = Field(
        default_factory=list,
        description="Valori dei dadi difensore (1..6, max 3)",
    )
    eventi_grezzi_id: list[str] = Field(
        ..., description="ID degli `EventoGrezzo` raggruppati in questa proposta"
    )
    confidenza: float = Field(
        ..., ge=0.0, le=1.0,
        description=(
            "Confidenza del clustering: 1.0 = configurazione plausibile, "
            "<0.5 = ambigua, l'utente dovrebbe verificare"
        ),
    )
    note: list[str] = Field(
        default_factory=list,
        description="Avvertimenti generati dal clustering (es. 'solo 1 dado difensore')",
    )


class RisultatoAggregazione(BaseModel):
    """Esito complessivo della richiesta di aggregazione su una partita."""

    n_eventi_grezzi_analizzati: int
    n_proposte: int
    proposte: list[PropostaAggregazioneDadi]


# === Accettazione di una proposta ===


class AccettaProposta(BaseModel):
    """
    Body della richiesta di accettazione di una proposta di aggregazione.

    L'utente seleziona una proposta dalla lista (`/proponi-aggregazioni-dadi`),
    aggiunge i campi che il BLE non può fornire (giocatore, territori),
    e invia per creare un `EventoValidato` di tipo `ATTACCO_RISOLTO`.

    I valori dei dadi sono modificabili rispetto alla proposta originale
    (l'utente può aver visto un dado caduto sul tavolo che il sensore non
    ha registrato correttamente, oppure può escludere un dado spurio).
    """

    eventi_grezzi_id: list[str] = Field(
        ...,
        min_length=1,
        description=(
            "ID degli `EventoGrezzo` da consumare. Devono essere "
            "DADI_LANCIATI con fonte=DADO_BLE non ancora validati e "
            "appartenenti alla partita."
        ),
    )
    giocatore_id: str = Field(
        ...,
        min_length=1,
        description="ID del `GiocatorePartita` che ha lanciato l'attacco",
    )
    da: str = Field(
        ...,
        min_length=1,
        description="Codice territorio attaccante (es. 'kamchatka')",
    )
    a: str = Field(
        ...,
        min_length=1,
        description="Codice territorio difensore",
    )
    dadi_attaccante: list[int] = Field(
        ...,
        min_length=1,
        max_length=3,
        description="Valori finali dei dadi attaccante (1..6)",
    )
    dadi_difensore: list[int] = Field(
        ...,
        min_length=1,
        max_length=3,
        description="Valori finali dei dadi difensore (1..6)",
    )
    ts_evento: datetime | None = Field(
        default=None,
        description=(
            "Timestamp dell'attacco. Se omesso, viene usato `ts_inizio` "
            "del cluster (primo dado lanciato)."
        ),
    )
    validato_da: str = Field(
        default="anonimo",
        max_length=100,
        description="Identificativo di chi sta validando (per audit)",
    )
