"""
Gestione del mazzo di carte durante la partita.

Responsabilità:
- Mantenere lo stato del mazzo di pesca e degli scarti
- Gestire la pesca delle carte
- Gestire i tris giocati (vanno negli scarti)
- Rimescolare gli scarti quando il mazzo di pesca si esaurisce

Le mani dei giocatori NON sono gestite qui: sono di competenza del modulo
`stato_partita` (ancora da implementare), che applicherà il pattern di
knowledge segregation. Questo modulo gestisce solo le pile pubbliche
(mazzo + scarti).

Invariante: in ogni momento, len(mazzo_pesca) + len(scarti) +
sum(len(mano_giocatore)) == 44 (totale carte iniziali).
"""

import random
from collections.abc import Iterable

from risiko_engine.carte import MAZZO_INIZIALE, Carta, nuovo_mazzo_mescolato


class MazzoEsauritoError(Exception):
    """
    Sollevata se si tenta di pescare ma sia il mazzo di pesca sia gli scarti
    sono vuoti. Caso teoricamente impossibile in una partita ben gestita
    (le 44 carte non possono essere tutte simultaneamente in mano), ma
    gestita defensivamente.
    """


class GestoreMazzo:
    """
    Gestisce il ciclo di vita del mazzo Risiko durante una partita.

    Esempio d'uso:
        gestore = GestoreMazzo.nuovo(seed=42)
        carta = gestore.pesca()
        # ... il giocatore usa la carta ...
        gestore.gioca_tris([c1, c2, c3])
        # ... più tardi ...
        carta_2 = gestore.pesca()  # se mazzo finito, rimescola scarti
    """

    def __init__(
        self,
        carte_iniziali: list[Carta] | None = None,
        rng: random.Random | None = None,
    ) -> None:
        """
        Args:
            carte_iniziali: mazzo di partenza già mescolato. Se None,
                            usa MAZZO_INIZIALE in ordine deterministico.
            rng: generatore casuale per i rimescolamenti successivi degli scarti.
                 Se None, ne crea uno nuovo non riproducibile.
        """
        if carte_iniziali is None:
            self._mazzo_pesca: list[Carta] = list(MAZZO_INIZIALE)
        else:
            self._mazzo_pesca = list(carte_iniziali)

        self._scarti: list[Carta] = []
        self._rng: random.Random = rng if rng is not None else random.Random()
        self._rimescolamenti: int = 0

    @classmethod
    def nuovo(cls, seed: int | None = None) -> "GestoreMazzo":
        """
        Crea un GestoreMazzo con mazzo iniziale già mescolato.

        Args:
            seed: opzionale, per partite riproducibili in test/replay.
        """
        rng = random.Random(seed)
        mazzo = nuovo_mazzo_mescolato(seed=seed)
        # Usa lo stesso RNG anche per i rimescolamenti successivi.
        return cls(carte_iniziali=mazzo, rng=rng)

    # === Pesca ===

    def pesca(self) -> Carta:
        """
        Pesca la prima carta dalla cima del mazzo.

        Se il mazzo è vuoto, rimescola gli scarti per formare un nuovo mazzo
        di pesca, poi pesca.

        Returns:
            La carta pescata.

        Raises:
            MazzoEsauritoError: se sia il mazzo che gli scarti sono vuoti
                                (caso patologico in pratica impossibile).
        """
        if not self._mazzo_pesca:
            self._rimescola_scarti_in_mazzo()

        if not self._mazzo_pesca:
            raise MazzoEsauritoError(
                "Tutte le 44 carte sono in mano ai giocatori, impossibile pescare"
            )

        return self._mazzo_pesca.pop(0)

    def pesca_n(self, n: int) -> list[Carta]:
        """
        Pesca N carte di seguito.

        Utile per la fase iniziale della partita quando ogni giocatore pesca
        più carte territorio per la distribuzione iniziale.
        """
        if n < 0:
            raise ValueError(f"Numero carte da pescare negativo: {n}")
        return [self.pesca() for _ in range(n)]

    # === Tris giocati ===

    def gioca_tris(self, carte: Iterable[Carta]) -> None:
        """
        Aggiunge le carte di un tris giocato al mazzo degli scarti.

        Le carte rimangono negli scarti finché il mazzo di pesca non si
        esaurisce, momento in cui gli scarti vengono mescolati e diventano
        il nuovo mazzo di pesca.

        Args:
            carte: le 3 carte del tris (più solitamente 3, ma accetta
                   qualsiasi iterabile di carte per flessibilità).
        """
        carte_lista = list(carte)
        self._scarti.extend(carte_lista)

    # === Rimescolamento ===

    def _rimescola_scarti_in_mazzo(self) -> None:
        """
        Mescola gli scarti e li mette al posto del mazzo di pesca esaurito.

        Operazione interna, chiamata automaticamente da `pesca()` quando serve.
        Incrementa il contatore di rimescolamenti.
        """
        if not self._scarti:
            return

        self._rng.shuffle(self._scarti)
        self._mazzo_pesca = self._scarti
        self._scarti = []
        self._rimescolamenti += 1

    # === Stato ===

    @property
    def carte_nel_mazzo(self) -> int:
        """Numero di carte ancora pescabili dal mazzo."""
        return len(self._mazzo_pesca)

    @property
    def carte_negli_scarti(self) -> int:
        """Numero di carte attualmente negli scarti (tris giocati non ancora rimescolati)."""
        return len(self._scarti)

    @property
    def carte_pubbliche_totali(self) -> int:
        """Carte note al sistema (mazzo + scarti). Le mani dei giocatori sono
        gestite altrove."""
        return self.carte_nel_mazzo + self.carte_negli_scarti

    @property
    def numero_rimescolamenti(self) -> int:
        """
        Quante volte gli scarti sono stati rimescolati nel mazzo.

        Utile per varianti con bonus tris progressivo: il bonus può aumentare
        a ogni nuovo ciclo del mazzo.
        """
        return self._rimescolamenti

    def snapshot_stato(self) -> dict[str, int]:
        """
        Snapshot dello stato corrente, utile per logging e debug.

        NON include la composizione esatta del mazzo (sarebbe leak di
        informazione segreta), solo i conteggi.
        """
        return {
            "carte_nel_mazzo": self.carte_nel_mazzo,
            "carte_negli_scarti": self.carte_negli_scarti,
            "rimescolamenti": self.numero_rimescolamenti,
        }
