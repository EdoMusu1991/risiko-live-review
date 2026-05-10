# CHANGELOG v0.30 — cleanup bundle non promossi + UI bottone scarta

Continuazione di v0.29. Aggiunge meccanismi per evitare l'accumulo di
bundle abbandonati in `storage_partite/`.

## Cosa e' cambiato

### Backend: 2 nuovi endpoint

- `DELETE /api/partite/bundle/{id_partita}` — scarta un bundle non
  ancora promosso. Cancella la cartella `storage_partite/<id>/` con
  manifest, segmenti video, eventi. Idempotente (204 anche se la
  cartella non esiste).

- `DELETE /api/partite/bundle?older_than_days=30` — cleanup batch.
  Cancella tutti i bundle il cui `manifest.ts_fine_registrazione` e'
  precedente a `now - N giorni`. Per safety, **non cancella bundle con
  manifest illeggibile** (preferiamo sprecare disco che cancellare per
  errore). Risponde con `{n_cancellati, ids_cancellati[]}`.

  Validazione: `older_than_days >= 1` (rifiutato 0 o negativo).

### Frontend: bottone "Scarta" sulla PaginaBundleInAttesa

Accanto al bottone "Promuovi" su ogni card bundle. Mostra dialog di
conferma con riepilogo (n. segmenti video + n. eventi dichiarati).
Spinner durante la richiesta. Banner errore non-bloccante in cima alla
lista in caso di fallimento.

API frontend aggiornata (`apiPromozioneBundle.ts`):
- `apiPromozioneBundle.scarta(idPartita)` → DELETE singolo
- `apiPromozioneBundle.cleanupVecchi(olderThanDays)` → DELETE batch
  (non ancora esposto in UI; disponibile per futuro pulsante "Pulisci
  vecchi" o cron job).

### Stato test

```
366 baseline (v0.29)
+6 test_promozione_bundle.py
───
372 passed in 9.50s
```

Test nuovi:
- `test_delete_bundle_esistente_204`
- `test_delete_bundle_inesistente_idempotente_204`
- `test_delete_bundle_cancella_anche_video_segmenti`
- `test_delete_bundle_vecchi_cancella_solo_oltre_soglia`
- `test_delete_bundle_vecchi_validazione_giorni`
- `test_delete_bundle_vecchi_salta_manifest_corrotto`

Frontend: typecheck pulito, build 488 KB (139 KB gzip).

## Cron job suggerito (opzionale, post-deploy)

Per evitare di accumulare bundle vecchi su Railway, schedula un cron job
giornaliero che chiama:

```bash
curl -X DELETE "https://<railway>/api/partite/bundle?older_than_days=60"
```

60 giorni e' un default sicuro: i bundle abbandonati piu' di 2 mesi senza
essere promossi probabilmente sono test o errori, non partite vere.

## Cosa NON fa

- Non rimuove i video di partite **gia' promosse** (quelli stanno in
  `storage_video/` e sono linkati a record SQL Partita; cancellarli
  romperebbe il review)
- Non elimina record SQL: per quello esiste gia' `DELETE /api/partite/{id}`
- Non e' transazionale: se il filesystem fallisce a meta', alcuni file
  potrebbero restare orfani. Per il caso d'uso (bundle abbandonati,
  cleanup periodico) e' accettabile.
