# CHANGELOG v0.35 — run-now scheduler + pre-loading player

Continuazione di v0.34. Due piccoli miglioramenti che chiudono punti
lasciati aperti nei round precedenti.

## Backend

### Nuovo endpoint: `POST /api/scheduler/run-now`

Esegue immediatamente il job di cleanup bundle vecchi, senza aspettare
il trigger schedulato (default 03:00). Funziona anche se
`SCHEDULER_ABILITATO=false`: il job e' una funzione pura, lo scheduler
ne gestisce solo lo schedule.

Risposta:
```json
{
  "n_cancellati": 3,
  "ids_cancellati": ["bundle-1", "bundle-2", "bundle-3"],
  "giorni_soglia": 30
}
```

Casi d'uso:
- Testare manualmente la configurazione prima di abilitare lo scheduler
- Liberare spazio on-demand dopo molte partite test
- Forzare il cleanup prima di un torneo importante

### Test

- 384 verdi (383 + 1 nuovo per run-now)
- Ruff pulito

## Frontend

### `PlayerVideoMultiSegmento`: pre-loading del segmento successivo

Aggiunto un secondo `<video>` invisibile con `preload="auto"` puntato al
segmento N+1 mentre il segmento N e' in riproduzione. Risultato: lo
switch tra segmenti e' praticamente istantaneo invece della pausa di
200-300ms tipica.

Tradeoff: leggera occupazione banda extra durante la riproduzione (il
browser scarica il prossimo segmento in parallelo). Per una review post-
partita su rete wifi del club e' irrilevante; su mobile potrebbe essere
disabilitato in futuro con una prop opzionale.

Cost build: +0.1 KB gzip.

## Stato sistema

Backend: 384/384 test verdi, ruff pulito, frontend typecheck pulito.

App mobile: bundle `risiko-live-mobile.zip` consegnato in precedenza
(progetto Expo completo con tutte le patch + audit + godice-lib v0.4
applicati, 193/193 test vitest verdi, typecheck pulito).
