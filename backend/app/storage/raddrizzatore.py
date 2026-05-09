"""
Raddrizzamento prospettico di frame video.

Workflow:
1. L'iPhone è fissato al soffitto sopra il tavolo del club. Inquadra
   la plancia di Risiko ma con prospettiva (l'iPhone non è perfettamente
   zenitale, le distanze non sono uniformi).
2. Per la CV serve invece una "vista canonica" della plancia: stessa
   forma di un'immagine di riferimento (la plancia stesa idealmente).
   In questa vista canonica i territori sono sempre nei pixel attesi e
   le pedine hanno scala stabile (un carro grande è sempre NxN pixel,
   un carro piccolo è sempre MxM pixel) — feature critica perché i 3
   tipi di pedina si distinguono per dimensione.
3. Soluzione: calcolare un'omografia da `frame_storto -> frame_canonico`
   usando feature matching (SIFT) + opzionale rifinitura (ORB).

Astrazione:
- `Raddrizzatore` (ABC): contratto.
- `RaddrizzatoreOpencv`: usa opencv + numpy. Dipendenza opzionale.
- `RaddrizzatoreMock`: per test, omografia identità + pass-through bytes.

Caching dell'omografia:
- L'iPhone è fisso, la plancia è (quasi) ferma per tutta la partita.
- Calcolare l'omografia è il pezzo costoso (200-500ms con SIFT).
- Applicarla è veloce (~10ms con cv2.warpPerspective).
- Quindi: calcoliamo UNA volta per partita (su un frame buono di
  calibrazione), poi applichiamo a tutti i frame successivi.
- La matrice 3x3 viene serializzata come JSON per cache su disco o DB.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class RaddrizzamentoError(Exception):
    """Errore generico durante il raddrizzamento."""


class OpencvNonDisponibileError(RaddrizzamentoError):
    """Pacchetto opencv-python non installato."""


class RiferimentoNonTrovatoError(RaddrizzamentoError):
    """L'immagine di riferimento non è stata trovata o è illeggibile."""


class CalibrazioneFallitaError(RaddrizzamentoError):
    """Match feature insufficienti per calcolare un'omografia affidabile."""


class Raddrizzatore(ABC):
    """
    Contratto astratto per raddrizzare frame.

    L'API è separata in due step pensata per l'efficienza in batch:

    1. `calibra(percorso_frame)`: calcola la matrice di omografia da un
       frame di calibrazione. Costoso (SIFT). Ritorna la matrice come
       lista di liste 3x3 di float, JSON-serializzabile.

    2. `applica(percorso_frame, matrice, percorso_output)`: applica
       l'omografia precomputata. Veloce (~10ms).

    Per uso ad-hoc, `raddrizza_singolo(percorso_frame, percorso_output)`
    fa entrambi gli step in un colpo (calibrazione + applicazione).
    """

    @abstractmethod
    def calibra(self, percorso_frame: Path) -> list[list[float]]:
        """
        Calcola la matrice di omografia 3x3 per un frame.

        Returns:
            Matrice 3x3 come lista di liste (JSON-serializzabile).

        Raises:
            CalibrazioneFallitaError: feature matching insufficiente.
            OpencvNonDisponibileError: opencv non installato.
        """

    @abstractmethod
    def applica(
        self,
        percorso_frame: Path,
        matrice: list[list[float]],
        percorso_output: Path,
    ) -> None:
        """
        Applica una matrice di omografia precomputata a un frame.
        Veloce (~10ms), idempotente.
        """

    def raddrizza_singolo(
        self,
        percorso_frame: Path,
        percorso_output: Path,
    ) -> list[list[float]]:
        """
        Helper: calibra + applica in un colpo. Ritorna la matrice usata
        (per poterla cacheare e riusare su frame successivi).
        """
        matrice = self.calibra(percorso_frame)
        self.applica(percorso_frame, matrice, percorso_output)
        return matrice


# === Implementazione OpenCV ===


class RaddrizzatoreOpencv(Raddrizzatore):
    """
    Implementazione concreta basata su OpenCV (SIFT + ORB).

    Args:
        percorso_riferimento: immagine "canonica" della plancia. Carica
            UNA SOLA VOLTA all'init (le sue features SIFT+ORB vengono
            calcolate una volta e tenute in memoria).
        usa_orb_refine: se True, dopo il warp SIFT applica una rifinitura
            ORB. Migliora la precisione per piccoli shift residui ma
            rallenta. Default True.
        soglia_match_lowe: soglia del rapporto di Lowe per filtrare i
            match SIFT (più basso = più strict). Default 0.75 (standard).
        min_match_validi: numero minimo di match buoni per calcolare
            l'omografia. Sotto questa soglia, solleva CalibrazioneFallitaError.
    """

    def __init__(
        self,
        percorso_riferimento: Path,
        *,
        usa_orb_refine: bool = True,
        soglia_match_lowe: float = 0.75,
        min_match_validi: int = 10,
    ) -> None:
        try:
            import cv2
            import numpy as np  # noqa: F401
        except ImportError as e:
            raise OpencvNonDisponibileError(
                "opencv-python non installato. Esegui: pip install -e \".[cv]\""
            ) from e

        if not percorso_riferimento.exists():
            raise RiferimentoNonTrovatoError(
                f"Riferimento non trovato: {percorso_riferimento}"
            )

        self._percorso_riferimento = percorso_riferimento
        self._usa_orb_refine = usa_orb_refine
        self._soglia_lowe = soglia_match_lowe
        self._min_match = min_match_validi

        # Carica e pre-processa il riferimento UNA volta sola
        self._riferimento_bgr = cv2.imread(str(percorso_riferimento))
        if self._riferimento_bgr is None:
            raise RiferimentoNonTrovatoError(
                f"cv2.imread ha restituito None per {percorso_riferimento}"
            )
        self._h, self._w = self._riferimento_bgr.shape[:2]
        self._riferimento_gray = cv2.cvtColor(
            self._riferimento_bgr, cv2.COLOR_BGR2GRAY
        )

        # Detector SIFT + features riferimento (una volta)
        self._sift = cv2.SIFT_create()  # type: ignore[attr-defined]
        self._kp_rif_sift, self._des_rif_sift = self._sift.detectAndCompute(
            self._riferimento_bgr, None
        )

        # Detector ORB + features riferimento (una volta)
        self._orb = cv2.ORB_create(5000)  # type: ignore[attr-defined]
        self._kp_rif_orb, self._des_rif_orb = self._orb.detectAndCompute(
            self._riferimento_gray, None
        )

        # Matchers (riusabili stateless)
        self._matcher_sift = cv2.BFMatcher()
        self._matcher_orb = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

    @property
    def dimensioni_canonica(self) -> tuple[int, int]:
        """Dimensioni (larghezza, altezza) dell'immagine di riferimento."""
        return (self._w, self._h)

    def calibra(self, percorso_frame: Path) -> list[list[float]]:
        import cv2
        import numpy as np

        if not percorso_frame.exists():
            raise RaddrizzamentoError(f"Frame non trovato: {percorso_frame}")

        img = cv2.imread(str(percorso_frame))
        if img is None:
            raise RaddrizzamentoError(
                f"cv2.imread ha restituito None per {percorso_frame}"
            )

        # === Passo 1: SIFT (omografia grossolana) ===
        kp_in, des_in = self._sift.detectAndCompute(img, None)
        if des_in is None or len(des_in) < self._min_match:
            raise CalibrazioneFallitaError(
                f"SIFT ha trovato solo {0 if des_in is None else len(des_in)} "
                f"keypoint nel frame (minimo {self._min_match})"
            )

        matches = self._matcher_sift.knnMatch(des_in, self._des_rif_sift, k=2)
        good = [
            m for pair in matches if len(pair) == 2
            for m, n in [pair]
            if m.distance < self._soglia_lowe * n.distance
        ]
        if len(good) < self._min_match:
            raise CalibrazioneFallitaError(
                f"SIFT: solo {len(good)} match buoni (min {self._min_match})"
            )

        src = np.array(
            [kp_in[m.queryIdx].pt for m in good],
            dtype=np.float32,
        ).reshape(-1, 1, 2)
        dst = np.array(
            [self._kp_rif_sift[m.trainIdx].pt for m in good],
            dtype=np.float32,
        ).reshape(-1, 1, 2)
        m_sift, _ = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
        if m_sift is None:
            raise CalibrazioneFallitaError(
                "findHomography (SIFT) ha restituito None"
            )

        if not self._usa_orb_refine:
            return self._matrice_a_lista(m_sift)

        # === Passo 2: ORB rifinitura ===
        try:
            pre = cv2.warpPerspective(img, m_sift, (self._w, self._h))
            pre_gray = cv2.cvtColor(pre, cv2.COLOR_BGR2GRAY)
            kp_pre, des_pre = self._orb.detectAndCompute(pre_gray, None)
            if des_pre is None:
                return self._matrice_a_lista(m_sift)

            matches_orb = self._matcher_orb.match(des_pre, self._des_rif_orb)
            matches_orb = sorted(matches_orb, key=lambda x: x.distance)
            # Tieni top 15% (filtro outlier grossolani prima di RANSAC)
            n_top = max(20, len(matches_orb) // 7)
            matches_orb = matches_orb[:n_top]
            if len(matches_orb) < self._min_match:
                return self._matrice_a_lista(m_sift)

            src = np.array(
                [kp_pre[m.queryIdx].pt for m in matches_orb],
                dtype=np.float32,
            ).reshape(-1, 1, 2)
            dst = np.array(
                [self._kp_rif_orb[m.trainIdx].pt for m in matches_orb],
                dtype=np.float32,
            ).reshape(-1, 1, 2)
            m_refine, _ = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
            if m_refine is None:
                return self._matrice_a_lista(m_sift)

            # Composizione: omografia totale = m_refine o m_sift
            m_finale = m_refine @ m_sift
            return self._matrice_a_lista(m_finale)
        except cv2.error:
            # Se la rifinitura ORB fallisce, fallback a SIFT-only
            return self._matrice_a_lista(m_sift)

    def applica(
        self,
        percorso_frame: Path,
        matrice: list[list[float]],
        percorso_output: Path,
    ) -> None:
        import cv2
        import numpy as np

        if not percorso_frame.exists():
            raise RaddrizzamentoError(f"Frame non trovato: {percorso_frame}")

        img = cv2.imread(str(percorso_frame))
        if img is None:
            raise RaddrizzamentoError(
                f"cv2.imread ha restituito None per {percorso_frame}"
            )

        m = np.array(matrice, dtype=np.float32)
        if m.shape != (3, 3):
            raise RaddrizzamentoError(
                f"Matrice 3x3 attesa, ricevuta shape {m.shape}"
            )

        raddrizzata = cv2.warpPerspective(img, m, (self._w, self._h))

        percorso_output.parent.mkdir(parents=True, exist_ok=True)
        ok = cv2.imwrite(str(percorso_output), raddrizzata)
        if not ok:
            raise RaddrizzamentoError(
                f"cv2.imwrite ha fallito per {percorso_output}"
            )

    @staticmethod
    def _matrice_a_lista(m: Any) -> list[list[float]]:
        """Converte una np.ndarray 3x3 in lista di liste JSON-friendly."""
        return [[float(m[i][j]) for j in range(3)] for i in range(3)]


# === Mock per test ===


class RaddrizzatoreMock(Raddrizzatore):
    """
    Mock: l'omografia è la matrice identità, l'output è una copia bytes
    del frame di input. Non richiede opencv.

    Usato nei test per verificare il flusso applicativo (cache, errori,
    orchestrazione DB) senza dipendere da opencv installato.
    """

    def __init__(
        self,
        *,
        simula_calibrazione_fallita: bool = False,
        simula_opencv_mancante: bool = False,
    ) -> None:
        self._simula_falla_calibrazione = simula_calibrazione_fallita
        self._simula_opencv_mancante = simula_opencv_mancante

    def calibra(self, percorso_frame: Path) -> list[list[float]]:
        if self._simula_opencv_mancante:
            raise OpencvNonDisponibileError("Mock: simulo opencv mancante")
        if self._simula_falla_calibrazione:
            raise CalibrazioneFallitaError(
                "Mock: simulo match insufficienti"
            )
        if not percorso_frame.exists():
            raise RaddrizzamentoError(f"Frame non trovato: {percorso_frame}")
        # Identità
        return [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]

    def applica(
        self,
        percorso_frame: Path,
        matrice: list[list[float]],
        percorso_output: Path,
    ) -> None:
        if self._simula_opencv_mancante:
            raise OpencvNonDisponibileError("Mock: simulo opencv mancante")
        if not percorso_frame.exists():
            raise RaddrizzamentoError(f"Frame non trovato: {percorso_frame}")
        if len(matrice) != 3 or any(len(r) != 3 for r in matrice):
            raise RaddrizzamentoError("Matrice 3x3 attesa")

        percorso_output.parent.mkdir(parents=True, exist_ok=True)
        # Mock: copia bytes (simula warp con identità)
        percorso_output.write_bytes(percorso_frame.read_bytes())
