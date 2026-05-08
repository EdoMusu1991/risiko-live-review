"""
I 16 obiettivi del Risiko classico Editrice Giochi.

Ogni obiettivo richiede al giocatore di **conquistare e mantenere
contemporaneamente un insieme specifico di territori**. I nomi degli
obiettivi (Letto, Elefante, Ciclista, ecc.) richiamano la forma che i
territori richiesti disegnano sulla mappa.

Verifica vittoria: il giocatore vince se l'insieme dei suoi territori
contiene (è superinsieme di) l'insieme dei territori richiesti
dall'obiettivo.

A differenza di altre versioni di Risiko, **non ci sono obiettivi di
distruzione né obiettivi numerici** ("conquista 24 territori"). Tutti i 16
obiettivi sono di tipo "conquista questa lista".

I dati grezzi degli obiettivi possono usare alcuni alias storici nei nomi
dei territori (es. `africa_del_nord` invece di `africa_settentrionale`,
`siam` invece di `asia_sudorientale`, ...). Il dizionario `_ALIAS_TERRITORI`
normalizza tutti gli ID al canonico usato in `mappa.py`.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from risiko_engine.mappa import TERRITORI

# === Normalizzazione alias ===

#: Mapping da nomi storici/alternativi al nome canonico in `mappa.TERRITORI`.
#: Necessario perché i dati Java/legacy degli obiettivi usano nomi diversi
#: rispetto alle adiacenze e ai continenti.
_ALIAS_TERRITORI: dict[str, str] = {
    "africa_del_nord": "africa_settentrionale",
    "africa_del_sud": "africa_meridionale",
    "territori_del_nord_ovest": "territori_nordovest",
    "stati_uniti_occidentali": "stati_occidentali",
    "stati_uniti_orientali": "stati_orientali",
    "siam": "asia_sudorientale",
    "jakutsk": "jacuzia",
    "irkutsk": "cita",
    # nessun alias per: alaska, alberta, ontario, quebec, groenlandia,
    # america_centrale, venezuela, peru, brasile, argentina, islanda,
    # gran_bretagna, scandinavia, ucraina, europa_*, egitto, congo, madagascar,
    # africa_orientale, urali, siberia, kamchatka, cina, mongolia, india,
    # afghanistan, medio_oriente, indonesia, nuova_guinea, australia_*,
    # giappone -- usano già il nome canonico
}


def _normalizza(territorio: str) -> str:
    """Risolve gli alias nel nome canonico. Se non è alias, ritorna inalterato."""
    return _ALIAS_TERRITORI.get(territorio, territorio)


def _normalizza_lista(territori: Iterable[str]) -> frozenset[str]:
    """
    Applica `_normalizza` a tutti i territori. Solleva ValueError se uno dei
    risultati non è in `TERRITORI` (cattura typo / nomi sconosciuti).
    """
    risultato: set[str] = set()
    for t in territori:
        canonico = _normalizza(t)
        if canonico not in TERRITORI:
            raise ValueError(
                f"Territorio sconosciuto in obiettivo: {t!r} "
                f"(normalizzato a {canonico!r})"
            )
        risultato.add(canonico)
    return frozenset(risultato)


# === Modello dati ===


@dataclass(frozen=True, slots=True)
class Obiettivo:
    """
    Un obiettivo del Risiko classico EG.

    Attributi:
        id: identificatore numerico stabile (1-16).
        nome: nome descrittivo dell'obiettivo (es. "Letto", "Elefante").
        immagine: nome del file immagine della carta obiettivo
                  (es. "obiettivo_01.jpg"). Usato dalla UI per mostrare la carta.
        territori_richiesti: insieme dei territori da possedere
                             contemporaneamente per vincere.
    """

    id: int
    nome: str
    immagine: str
    territori_richiesti: frozenset[str]

    def __post_init__(self) -> None:
        if self.id < 1:
            raise ValueError(f"id obiettivo deve essere >= 1, ricevuto {self.id}")
        if not self.nome:
            raise ValueError("nome obiettivo non può essere vuoto")
        if not self.immagine:
            raise ValueError("immagine obiettivo non può essere vuota")
        if not self.territori_richiesti:
            raise ValueError(
                f"Obiettivo {self.id} '{self.nome}' senza territori richiesti"
            )

    @property
    def n_territori_richiesti(self) -> int:
        return len(self.territori_richiesti)

    def __repr__(self) -> str:
        return (
            f"Obiettivo({self.id}, {self.nome!r}, "
            f"{self.n_territori_richiesti} territori)"
        )


# === Catalogo dei 16 obiettivi (set ufficiale Editrice Giochi) ===

OBIETTIVI: tuple[Obiettivo, ...] = (
    Obiettivo(
        id=1,
        nome="Letto",
        immagine="obiettivo_01.jpg",
        territori_richiesti=_normalizza_lista([
            "alaska", "alberta", "america_centrale", "groenlandia", "ontario",
            "quebec", "stati_uniti_occidentali", "stati_uniti_orientali",
            "territori_del_nord_ovest",
            "argentina", "brasile", "peru", "venezuela",
            "australia_occidentale", "nuova_guinea", "indonesia", "siam",
            "india", "medio_oriente",
            "africa_del_nord", "congo", "egitto", "africa_orientale",
        ]),
    ),
    Obiettivo(
        id=2,
        nome="Elefante",
        immagine="obiettivo_02.jpg",
        territori_richiesti=_normalizza_lista([
            "quebec", "groenlandia", "ontario", "islanda", "stati_uniti_orientali",
            "europa_occidentale", "europa_meridionale", "europa_settentrionale",
            "gran_bretagna", "scandinavia", "ucraina",
            "afghanistan", "urali", "medio_oriente",
            "africa_del_nord", "egitto", "congo", "africa_orientale",
            "africa_del_sud", "madagascar",
        ]),
    ),
    Obiettivo(
        id=3,
        nome="Ciclista",
        immagine="obiettivo_03.jpg",
        territori_richiesti=_normalizza_lista([
            "europa_occidentale", "europa_meridionale", "europa_settentrionale",
            "gran_bretagna", "islanda", "scandinavia", "ucraina",
            "afghanistan", "urali", "medio_oriente", "india", "siam",
            "australia_occidentale", "australia_orientale", "nuova_guinea",
            "indonesia",
            "africa_del_nord", "egitto", "congo", "africa_orientale",
            "africa_del_sud", "madagascar",
        ]),
    ),
    Obiettivo(
        id=4,
        nome="Giraffa",
        immagine="obiettivo_04.jpg",
        territori_richiesti=_normalizza_lista([
            "alaska", "alberta", "america_centrale", "groenlandia", "ontario",
            "quebec", "stati_uniti_occidentali", "stati_uniti_orientali",
            "territori_del_nord_ovest",
            "europa_meridionale", "europa_settentrionale", "gran_bretagna",
            "islanda", "scandinavia", "ucraina",
            "africa_del_nord", "egitto", "congo", "africa_orientale",
            "africa_del_sud", "madagascar",
        ]),
    ),
    Obiettivo(
        id=5,
        nome="Granchio",
        immagine="obiettivo_05.jpg",
        territori_richiesti=_normalizza_lista([
            "alaska", "alberta", "america_centrale", "groenlandia", "ontario",
            "quebec", "stati_uniti_occidentali", "stati_uniti_orientali",
            "territori_del_nord_ovest",
            "islanda", "scandinavia", "ucraina",
            "afghanistan", "urali", "medio_oriente", "cina", "india", "siam",
            "australia_occidentale", "australia_orientale", "nuova_guinea",
            "indonesia",
        ]),
    ),
    Obiettivo(
        id=6,
        nome="Formula1",
        immagine="obiettivo_06.jpg",
        territori_richiesti=_normalizza_lista([
            "europa_occidentale", "europa_meridionale", "europa_settentrionale",
            "gran_bretagna", "islanda", "scandinavia", "ucraina",
            "afghanistan", "medio_oriente", "india", "siam",
            "argentina", "brasile", "peru", "venezuela",
            "australia_occidentale", "australia_orientale", "nuova_guinea",
            "indonesia",
            "africa_del_nord", "egitto", "africa_orientale",
        ]),
    ),
    Obiettivo(
        id=7,
        nome="Befana",
        immagine="obiettivo_07.jpg",
        territori_richiesti=_normalizza_lista([
            "argentina", "brasile", "peru", "venezuela",
            "africa_del_nord", "egitto", "congo", "africa_orientale",
            "africa_del_sud", "madagascar",
            "afghanistan", "urali", "medio_oriente", "india", "siam", "cina",
            "mongolia", "jacuzia", "cita", "siberia", "kamchatka", "giappone",
        ]),
    ),
    Obiettivo(
        id=8,
        nome="Elvis",
        immagine="obiettivo_08.jpg",
        territori_richiesti=_normalizza_lista([
            "alaska", "alberta", "america_centrale", "groenlandia", "ontario",
            "quebec", "stati_uniti_occidentali", "stati_uniti_orientali",
            "territori_del_nord_ovest",
            "argentina", "brasile", "peru", "venezuela",
            "europa_occidentale", "europa_meridionale", "europa_settentrionale",
            "gran_bretagna", "islanda", "scandinavia", "ucraina",
            "kamchatka", "giappone",
        ]),
    ),
    Obiettivo(
        id=9,
        nome="Dromedario con mosca",
        immagine="obiettivo_09.jpg",
        territori_richiesti=_normalizza_lista([
            "europa_occidentale", "europa_meridionale", "europa_settentrionale",
            "gran_bretagna", "islanda", "scandinavia", "ucraina",
            "afghanistan", "urali", "medio_oriente", "india", "siam", "cina",
            "mongolia", "jacuzia", "cita", "siberia", "kamchatka", "giappone",
            "indonesia",
        ]),
    ),
    Obiettivo(
        id=10,
        nome="Piovra",
        immagine="obiettivo_10.jpg",
        territori_richiesti=_normalizza_lista([
            "alaska", "alberta", "america_centrale", "groenlandia", "ontario",
            "quebec", "stati_uniti_occidentali", "stati_uniti_orientali",
            "territori_del_nord_ovest",
            "europa_occidentale", "europa_meridionale", "europa_settentrionale",
            "gran_bretagna", "islanda", "scandinavia", "ucraina",
            "urali", "siberia", "kamchatka", "giappone", "jacuzia",
        ]),
    ),
    Obiettivo(
        id=11,
        nome="Lupo (Siberiana)",
        immagine="obiettivo_11.jpg",
        territori_richiesti=_normalizza_lista([
            "europa_occidentale", "europa_meridionale", "europa_settentrionale",
            "gran_bretagna", "islanda", "scandinavia", "ucraina",
            "siberia", "urali", "afghanistan", "medio_oriente",
            "africa_del_nord", "egitto", "congo", "africa_orientale",
            "africa_del_sud", "madagascar",
            "argentina", "brasile", "peru", "venezuela",
        ]),
    ),
    Obiettivo(
        id=12,
        nome="Tappeto",
        immagine="obiettivo_12.jpg",
        territori_richiesti=_normalizza_lista([
            "africa_del_nord", "egitto", "congo", "africa_orientale",
            "africa_del_sud", "madagascar",
            "afghanistan", "urali", "medio_oriente", "india", "siam", "cina",
            "mongolia", "jacuzia", "cita", "siberia", "kamchatka", "giappone",
            "indonesia",
            "europa_meridionale", "ucraina",
        ]),
    ),
    Obiettivo(
        id=13,
        nome="Guerra fredda",
        immagine="obiettivo_13.jpg",
        territori_richiesti=_normalizza_lista([
            "alaska", "alberta", "america_centrale", "groenlandia", "ontario",
            "quebec", "stati_uniti_occidentali", "stati_uniti_orientali",
            "territori_del_nord_ovest",
            "afghanistan", "urali", "medio_oriente", "india", "siam", "cina",
            "mongolia", "jacuzia", "siberia", "cita", "kamchatka", "giappone",
        ]),
    ),
    Obiettivo(
        id=14,
        nome="Motorino",
        immagine="obiettivo_14.jpg",
        territori_richiesti=_normalizza_lista([
            "argentina", "brasile", "peru", "venezuela",
            "africa_del_nord", "egitto", "congo", "africa_orientale",
            "africa_del_sud", "madagascar",
            "australia_occidentale", "australia_orientale", "nuova_guinea",
            "indonesia",
            "europa_occidentale", "europa_meridionale", "medio_oriente",
            "india", "siam", "cina",
            "mongolia", "cita", "giappone",
        ]),
    ),
    Obiettivo(
        id=15,
        nome="Aragosta e pesciolino",
        immagine="obiettivo_15.jpg",
        territori_richiesti=_normalizza_lista([
            "alaska", "alberta",
            "egitto", "congo", "africa_orientale", "africa_del_sud", "madagascar",
            "afghanistan", "urali", "medio_oriente", "india", "siam", "cina",
            "mongolia", "jacuzia", "siberia", "kamchatka", "giappone", "cita",
            "indonesia",
            "australia_occidentale", "australia_orientale", "nuova_guinea",
        ]),
    ),
    Obiettivo(
        id=16,
        nome="Locomotiva",
        immagine="obiettivo_16.jpg",
        territori_richiesti=_normalizza_lista([
            "alaska", "alberta", "america_centrale", "groenlandia", "ontario",
            "quebec", "stati_uniti_occidentali", "stati_uniti_orientali",
            "territori_del_nord_ovest",
            "argentina", "brasile", "peru", "venezuela",
            "africa_del_nord", "egitto", "congo", "africa_orientale",
            "africa_del_sud", "madagascar",
            "europa_occidentale", "ucraina", "europa_meridionale",
        ]),
    ),
)


# === API pubblica ===


def conta_obiettivi() -> int:
    """Numero di obiettivi nel catalogo (deve essere 16)."""
    return len(OBIETTIVI)


def obiettivo_per_id(id_obiettivo: int) -> Obiettivo:
    """
    Ritorna l'obiettivo con l'id dato.

    Raises:
        KeyError: se l'id non corrisponde a nessun obiettivo del catalogo.
    """
    for o in OBIETTIVI:
        if o.id == id_obiettivo:
            return o
    raise KeyError(
        f"Obiettivo con id {id_obiettivo} non trovato (validi: 1-{len(OBIETTIVI)})"
    )


def obiettivo_per_nome(nome: str) -> Obiettivo:
    """
    Ritorna l'obiettivo dal suo nome (case-insensitive).

    Raises:
        KeyError: se nessun obiettivo ha quel nome.
    """
    nome_norm = nome.strip().lower()
    for o in OBIETTIVI:
        if o.nome.lower() == nome_norm:
            return o
    raise KeyError(f"Obiettivo con nome {nome!r} non trovato")


def verifica_vittoria(
    obiettivo: Obiettivo, territori_posseduti: Iterable[str]
) -> bool:
    """
    Verifica se l'insieme di territori posseduti soddisfa l'obiettivo.

    Args:
        obiettivo: l'obiettivo da verificare.
        territori_posseduti: i territori controllati dal giocatore.

    Returns:
        True se territori_posseduti contiene tutti i territori richiesti.

    Note:
        Possedere territori extra non invalida l'obiettivo: serve solo
        possedere ALMENO i territori richiesti, simultaneamente.
    """
    posseduti_set = (
        territori_posseduti
        if isinstance(territori_posseduti, frozenset | set)
        else frozenset(territori_posseduti)
    )
    return obiettivo.territori_richiesti.issubset(posseduti_set)
