"""
Mappa del Risiko classico Editrice Giochi: 42 territori, 6 continenti, adiacenze.

I nomi dei territori sono in **snake_case canonico** (es. `africa_settentrionale`,
`territori_nordovest`). Le UI possono mostrarli con label "umane" tramite un
mapping separato.

Questa è la fonte di verità delle adiacenze: tutti i moduli a valle (combattimento,
state_machine) si fidano di ciò che è qui dichiarato.

**Invariante**: le adiacenze sono **simmetriche** — se A confina con B,
allora B confina con A. Il dict `_BORDI` dichiara una sola direzione per
chiarezza, e la simmetria viene costruita programmaticamente.
"""

from enum import StrEnum


class Continente(StrEnum):
    """I 6 continenti del Risiko classico EG."""

    NORD_AMERICA = "nordamerica"
    SUD_AMERICA = "sudamerica"
    EUROPA = "europa"
    AFRICA = "africa"
    ASIA = "asia"
    OCEANIA = "oceania"


# === Territori per continente ===

#: I 42 territori del Risiko, raggruppati per continente.
#: I nomi sono i canonical IDs usati internamente.
_TERRITORI_PER_CONTINENTE: dict[Continente, tuple[str, ...]] = {
    Continente.NORD_AMERICA: (
        "alaska",
        "territori_nordovest",
        "groenlandia",
        "alberta",
        "ontario",
        "quebec",
        "stati_occidentali",
        "stati_orientali",
        "america_centrale",
    ),
    Continente.SUD_AMERICA: (
        "venezuela",
        "peru",
        "brasile",
        "argentina",
    ),
    Continente.EUROPA: (
        "islanda",
        "gran_bretagna",
        "europa_settentrionale",
        "scandinavia",
        "ucraina",
        "europa_occidentale",
        "europa_meridionale",
    ),
    Continente.AFRICA: (
        "africa_settentrionale",
        "egitto",
        "africa_orientale",
        "congo",
        "africa_meridionale",
        "madagascar",
    ),
    Continente.ASIA: (
        "medio_oriente",
        "afghanistan",
        "india",
        "urali",
        "siberia",
        "jacuzia",
        "kamchatka",
        "cita",
        "mongolia",
        "cina",
        "asia_sudorientale",
        "giappone",
    ),
    Continente.OCEANIA: (
        "indonesia",
        "nuova_guinea",
        "australia_occidentale",
        "australia_orientale",
    ),
}

#: Tutti i territori in ordine deterministico (per continente, poi alfabetico
#: all'interno del continente per stabilità).
TERRITORI: tuple[str, ...] = tuple(
    territorio
    for continente in Continente  # ordine: NORD_AMERICA, SUD_AMERICA, ...
    for territorio in _TERRITORI_PER_CONTINENTE[continente]
)

#: Mappa inversa: territorio -> continente.
_CONTINENTE_DI_TERRITORIO: dict[str, Continente] = {
    territorio: continente
    for continente, territori in _TERRITORI_PER_CONTINENTE.items()
    for territorio in territori
}

# === Bonus rinforzo per continente (Risiko classico EG) ===

#: Bonus armate ricevuti dal giocatore che controlla un intero continente
#: a inizio del proprio turno di rinforzo.
BONUS_CONTINENTE: dict[Continente, int] = {
    Continente.NORD_AMERICA: 5,
    Continente.SUD_AMERICA: 2,
    Continente.EUROPA: 5,
    Continente.AFRICA: 3,
    Continente.ASIA: 7,
    Continente.OCEANIA: 2,
}

# === Adiacenze ===

#: Bordi unidirezionali della mappa. La simmetria viene applicata
#: programmaticamente in `_costruisci_adiacenze`. Dichiarare la stessa
#: relazione due volte qui è ridondante e error-prone.
_BORDI: tuple[tuple[str, str], ...] = (
    # === Nord America ===
    ("alaska", "territori_nordovest"),
    ("alaska", "alberta"),
    ("alaska", "kamchatka"),  # bordo intercontinentale Asia
    ("territori_nordovest", "alberta"),
    ("territori_nordovest", "ontario"),
    ("territori_nordovest", "groenlandia"),
    ("groenlandia", "ontario"),
    ("groenlandia", "quebec"),
    ("groenlandia", "islanda"),  # bordo intercontinentale Europa
    ("alberta", "ontario"),
    ("alberta", "stati_occidentali"),
    ("ontario", "stati_occidentali"),
    ("ontario", "stati_orientali"),
    ("ontario", "quebec"),
    ("quebec", "stati_orientali"),
    ("stati_occidentali", "stati_orientali"),
    ("stati_occidentali", "america_centrale"),
    ("stati_orientali", "america_centrale"),
    ("america_centrale", "venezuela"),  # bordo intercontinentale Sud America
    # === Sud America ===
    ("venezuela", "peru"),
    ("venezuela", "brasile"),
    ("peru", "brasile"),
    ("peru", "argentina"),
    ("brasile", "argentina"),
    ("brasile", "africa_settentrionale"),  # bordo intercontinentale Africa
    # === Europa ===
    ("islanda", "gran_bretagna"),
    ("islanda", "scandinavia"),
    ("gran_bretagna", "europa_settentrionale"),
    ("gran_bretagna", "scandinavia"),
    ("gran_bretagna", "europa_occidentale"),
    ("scandinavia", "europa_settentrionale"),
    ("scandinavia", "ucraina"),
    ("europa_settentrionale", "ucraina"),
    ("europa_settentrionale", "europa_occidentale"),
    ("europa_settentrionale", "europa_meridionale"),
    ("europa_occidentale", "europa_meridionale"),
    ("europa_occidentale", "africa_settentrionale"),  # bordo intercontinentale
    ("europa_meridionale", "ucraina"),
    ("europa_meridionale", "egitto"),  # bordo intercontinentale
    ("europa_meridionale", "africa_settentrionale"),  # bordo intercontinentale
    ("europa_meridionale", "medio_oriente"),  # bordo intercontinentale
    ("ucraina", "medio_oriente"),  # bordo intercontinentale
    ("ucraina", "afghanistan"),  # bordo intercontinentale
    ("ucraina", "urali"),  # bordo intercontinentale
    # === Africa ===
    ("africa_settentrionale", "egitto"),
    ("africa_settentrionale", "africa_orientale"),
    ("africa_settentrionale", "congo"),
    ("egitto", "africa_orientale"),
    ("egitto", "medio_oriente"),  # bordo intercontinentale Asia
    ("africa_orientale", "congo"),
    ("africa_orientale", "africa_meridionale"),
    ("africa_orientale", "madagascar"),
    ("congo", "africa_meridionale"),
    ("africa_meridionale", "madagascar"),
    # === Asia ===
    ("medio_oriente", "afghanistan"),
    ("medio_oriente", "india"),
    ("afghanistan", "india"),
    ("afghanistan", "cina"),
    ("afghanistan", "urali"),
    ("india", "cina"),
    ("india", "asia_sudorientale"),
    ("urali", "cina"),
    ("urali", "siberia"),
    ("siberia", "cina"),
    ("siberia", "mongolia"),
    ("siberia", "cita"),
    ("siberia", "jacuzia"),
    ("jacuzia", "cita"),
    ("jacuzia", "kamchatka"),
    ("kamchatka", "cita"),
    ("kamchatka", "mongolia"),
    ("kamchatka", "giappone"),
    ("cita", "mongolia"),
    ("mongolia", "cina"),
    ("mongolia", "giappone"),
    ("cina", "asia_sudorientale"),
    ("asia_sudorientale", "indonesia"),  # bordo intercontinentale Oceania
    # === Oceania ===
    ("indonesia", "nuova_guinea"),
    ("indonesia", "australia_occidentale"),
    ("nuova_guinea", "australia_occidentale"),
    ("nuova_guinea", "australia_orientale"),
    ("australia_occidentale", "australia_orientale"),
)


def _costruisci_adiacenze(
    bordi: tuple[tuple[str, str], ...],
) -> dict[str, frozenset[str]]:
    """
    Costruisce la mappa di adiacenze simmetrica a partire dai bordi
    unidirezionali. Garantisce che ogni territorio compaia come chiave
    e che la simmetria sia rispettata.
    """
    grezzo: dict[str, set[str]] = {t: set() for t in TERRITORI}

    for a, b in bordi:
        if a not in grezzo:
            raise ValueError(f"Territorio sconosciuto in _BORDI: {a!r}")
        if b not in grezzo:
            raise ValueError(f"Territorio sconosciuto in _BORDI: {b!r}")
        grezzo[a].add(b)
        grezzo[b].add(a)

    return {t: frozenset(vicini) for t, vicini in grezzo.items()}


#: Mappa territorio -> set dei territori adiacenti. Simmetrica per costruzione.
ADIACENZE: dict[str, frozenset[str]] = _costruisci_adiacenze(_BORDI)


# === API pubblica ===


def territori_di(continente: Continente) -> tuple[str, ...]:
    """Ritorna i territori che compongono un continente."""
    return _TERRITORI_PER_CONTINENTE[continente]


def continente_di(territorio: str) -> Continente:
    """
    Ritorna il continente di appartenenza di un territorio.

    Raises:
        KeyError: se il territorio non esiste nella mappa.
    """
    if territorio not in _CONTINENTE_DI_TERRITORIO:
        raise KeyError(f"Territorio sconosciuto: {territorio!r}")
    return _CONTINENTE_DI_TERRITORIO[territorio]


def adiacenti_a(territorio: str) -> frozenset[str]:
    """
    Ritorna i territori adiacenti a quello dato.

    Raises:
        KeyError: se il territorio non esiste nella mappa.
    """
    if territorio not in ADIACENZE:
        raise KeyError(f"Territorio sconosciuto: {territorio!r}")
    return ADIACENZE[territorio]


def bonus_continente(continente: Continente) -> int:
    """Bonus armate per il controllo completo del continente."""
    return BONUS_CONTINENTE[continente]
