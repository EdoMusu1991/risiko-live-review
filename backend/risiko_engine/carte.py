"""
Mazzo di carte del Risiko classico Editrice Giochi.

44 carte:
- 42 carte territorio (una per ogni territorio della mappa), ognuna con
  un simbolo: cannone, fante o cavaliere
- 2 carte jolly

I simboli sono distribuiti uniformemente: 14 cannoni, 14 fanti, 14 cavalieri.

NOTA: la distribuzione specifica simbolo->territorio in questa implementazione
è una proposta ragionevole. Se il set fisico ha assegnazioni diverse,
modifica `_SIMBOLI_TERRITORI` di conseguenza. La logica di gioco non cambia.
"""

import random
from dataclasses import dataclass
from enum import StrEnum

from risiko_engine.mappa import TERRITORI


class Simbolo(StrEnum):
    """I 4 simboli delle carte Risiko."""

    CANNONE = "cannone"
    FANTE = "fante"
    CAVALIERE = "cavaliere"
    JOLLY = "jolly"


@dataclass(frozen=True, slots=True)
class Carta:
    """
    Una carta del mazzo Risiko.

    Le carte territorio hanno `territorio` valorizzato e `simbolo` uno tra
    CANNONE/FANTE/CAVALIERE. Le carte jolly hanno `territorio = None` e
    `simbolo = JOLLY`.
    """

    territorio: str | None
    simbolo: Simbolo

    @property
    def is_jolly(self) -> bool:
        return self.simbolo == Simbolo.JOLLY

    def __repr__(self) -> str:
        if self.is_jolly:
            return "Carta(JOLLY)"
        return f"Carta({self.territorio}, {self.simbolo.value})"


# Distribuzione simbolo per territorio.
# 14 cannoni + 14 fanti + 14 cavalieri = 42 territori.
_SIMBOLI_TERRITORI: dict[str, Simbolo] = {
    # Nord America: 3 cannoni, 3 fanti, 3 cavalieri
    "alaska": Simbolo.FANTE,
    "territori_nordovest": Simbolo.CANNONE,
    "groenlandia": Simbolo.CAVALIERE,
    "alberta": Simbolo.FANTE,
    "ontario": Simbolo.CANNONE,
    "quebec": Simbolo.CAVALIERE,
    "stati_occidentali": Simbolo.CANNONE,
    "stati_orientali": Simbolo.FANTE,
    "america_centrale": Simbolo.CAVALIERE,
    # Sud America: 1 cannone, 1 fante, 2 cavalieri
    "venezuela": Simbolo.CAVALIERE,
    "brasile": Simbolo.FANTE,
    "peru": Simbolo.CANNONE,
    "argentina": Simbolo.CAVALIERE,
    # Europa: 2 cannoni, 3 fanti, 2 cavalieri
    "islanda": Simbolo.FANTE,
    "scandinavia": Simbolo.FANTE,
    "gran_bretagna": Simbolo.CAVALIERE,
    "europa_settentrionale": Simbolo.CANNONE,
    "europa_meridionale": Simbolo.CAVALIERE,
    "europa_occidentale": Simbolo.CANNONE,
    "ucraina": Simbolo.FANTE,
    # Africa: 2 cannoni, 2 fanti, 2 cavalieri
    "africa_settentrionale": Simbolo.CANNONE,
    "egitto": Simbolo.CAVALIERE,
    "africa_orientale": Simbolo.FANTE,
    "congo": Simbolo.CANNONE,
    "africa_meridionale": Simbolo.CAVALIERE,
    "madagascar": Simbolo.FANTE,
    # Asia: 4 cannoni, 4 fanti, 4 cavalieri
    "urali": Simbolo.CAVALIERE,
    "siberia": Simbolo.CANNONE,
    "jacuzia": Simbolo.FANTE,
    "cita": Simbolo.CANNONE,
    "kamchatka": Simbolo.CAVALIERE,
    "mongolia": Simbolo.FANTE,
    "giappone": Simbolo.CANNONE,
    "cina": Simbolo.FANTE,
    "medio_oriente": Simbolo.CAVALIERE,
    "india": Simbolo.CAVALIERE,
    "asia_sudorientale": Simbolo.FANTE,
    "afghanistan": Simbolo.CANNONE,
    # Oceania: 2 cannoni, 1 fante, 1 cavaliere
    "indonesia": Simbolo.CANNONE,
    "nuova_guinea": Simbolo.FANTE,
    "australia_occidentale": Simbolo.CANNONE,
    "australia_orientale": Simbolo.CAVALIERE,
}


def _crea_mazzo_iniziale() -> tuple[Carta, ...]:
    """
    Crea il mazzo completo: 42 carte territorio + 2 jolly.

    Ritorna una tupla immutabile per garantire che `MAZZO_INIZIALE` non possa
    essere modificato accidentalmente da codice client.
    """
    territori_attesi = set(TERRITORI)
    territori_dichiarati = set(_SIMBOLI_TERRITORI.keys())
    if territori_dichiarati != territori_attesi:
        mancanti = territori_attesi - territori_dichiarati
        in_eccesso = territori_dichiarati - territori_attesi
        raise ValueError(
            f"Mismatch simboli/territori. Mancanti: {sorted(mancanti)}, "
            f"in eccesso: {sorted(in_eccesso)}"
        )

    carte: list[Carta] = [
        Carta(territorio=t, simbolo=s) for t, s in _SIMBOLI_TERRITORI.items()
    ]
    carte.append(Carta(territorio=None, simbolo=Simbolo.JOLLY))
    carte.append(Carta(territorio=None, simbolo=Simbolo.JOLLY))
    return tuple(carte)


# Mazzo iniziale immutabile, in ordine deterministico.
# Per giocare, usa `nuovo_mazzo_mescolato()` che ritorna una lista mutabile.
MAZZO_INIZIALE: tuple[Carta, ...] = _crea_mazzo_iniziale()


def nuovo_mazzo_mescolato(seed: int | None = None) -> list[Carta]:
    """
    Ritorna una nuova lista mutabile contenente le 44 carte del mazzo,
    mescolate casualmente.

    Args:
        seed: Se fornito, il mescolamento è riproducibile. Utile per i test.
    """
    rng = random.Random(seed)
    mazzo = list(MAZZO_INIZIALE)
    rng.shuffle(mazzo)
    return mazzo


def carta_per_territorio(territorio: str) -> Carta:
    """
    Ritorna la carta corrispondente al territorio dato.

    Solleva KeyError se il territorio non esiste.
    """
    simbolo = _SIMBOLI_TERRITORI[territorio]
    return Carta(territorio=territorio, simbolo=simbolo)
