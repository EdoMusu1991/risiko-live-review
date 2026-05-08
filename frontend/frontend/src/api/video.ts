/**
 * Funzioni per upload e gestione video.
 */

import { chiamaApi, cliente } from "./cliente";
import type { Video } from "@/tipi/dominio";

export const apiVideo = {
  async lista(partitaId: string): Promise<Video[]> {
    return chiamaApi(
      cliente.get<Video[]>(`/partite/${partitaId}/video`),
    );
  },

  async dettaglio(partitaId: string, videoId: string): Promise<Video> {
    return chiamaApi(
      cliente.get<Video>(`/partite/${partitaId}/video/${videoId}`),
    );
  },

  /**
   * Upload di un file video.
   *
   * Riceve callback opzionale per il progresso (0..1).
   * Il backend estrae i metadata (durata, codec, ts_inizio) automaticamente
   * via ffprobe; non serve passarli da qui.
   */
  async carica(
    partitaId: string,
    file: File,
    onProgresso?: (frazione: number) => void,
  ): Promise<Video> {
    const formData = new FormData();
    formData.append("file", file);

    return chiamaApi(
      cliente.post<Video>(`/partite/${partitaId}/video`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 0, // upload può richiedere ore per file grandi
        onUploadProgress: (e) => {
          if (onProgresso && e.total) {
            onProgresso(e.loaded / e.total);
          }
        },
      }),
    );
  },

  async elimina(partitaId: string, videoId: string): Promise<void> {
    await chiamaApi(
      cliente.delete<void>(`/partite/${partitaId}/video/${videoId}`),
    );
  },

  /** URL pubblico per lo streaming video (HTML5 `<video>` o player JS). */
  urlStream(partitaId: string, videoId: string): string {
    return `/api/partite/${partitaId}/video/${videoId}/stream`;
  },
};
