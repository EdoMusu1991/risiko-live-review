/**
 * Funzioni per l'esportazione di una partita.
 *
 * L'endpoint backend genera direttamente file scaricabili (JSON con
 * Content-Disposition attachment, HTML inline). Le URL sono lette
 * dal browser nativo, niente axios qui.
 */

export const apiEsportazione = {
  /** URL del bundle JSON. Forza il download via Content-Disposition. */
  urlJson(partitaId: string): string {
    return `/api/partite/${partitaId}/esporta?formato=json`;
  },

  /** URL del report HTML. Si apre inline nel browser (printable). */
  urlHtml(partitaId: string): string {
    return `/api/partite/${partitaId}/esporta?formato=html`;
  },
};
