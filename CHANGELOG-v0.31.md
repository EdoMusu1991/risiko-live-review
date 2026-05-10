# CHANGELOG v0.31 — multi-segment player + cleanup bundle

Continuazione di v0.30. Due cambiamenti principali:

## 1. Multi-segment video player

### Nuovo: `PlayerVideoMultiSegmento.tsx`

Sostituisce `PlayerVideo` per la `PaginaDettaglioPartita`. Il vecchio
player gestiva un singolo file mp4. Quello nuovo gestisce N segmenti in
sequenza, presentandoli al consumer come un unico video con timeline
globale cumulativa.

Funzionalita':
- Auto-play del segmento successivo quando il corrente finisce
- `saltaA(secondoGlobale)` calcola quale segmento + offset locale
- Timeline cliccabile con marker visuali tra segmenti
- Bottoni "segmento prec" / "segmento succ" quando N > 1
- Counter "seg X/N" visibile in header
- Backwards-compatible: con N=1 si comporta esattamente come PlayerVideo

### Aggiornata: `PaginaDettaglioPartita.tsx`

- Sostituisce `PlayerVideo` con `PlayerVideoMultiSegmento`
- `videoCorrente` rinominato `primoVideo` (usato solo per `ts_inizio`
  della partita)
- Nuovo `segmenti` array calcolato da `partita.video[]`
- Display info adattato: se 1 segmento mostra nome originale, se >1 mostra
  "N segmenti · totale Mmin"
- Dimensione totale calcolata sommando tutti i `dimensione_byte`

### Build

Frontend: 490.66 kB → 139.66 kB gzip (+1 KB rispetto a v0.30, costo del
nuovo componente)

## 2. Cleanup bundle non promossi

### Nuovi endpoint backend

`DELETE /api/partite/bundle/{id_partita}` — cancella un bundle dal
filesystem senza creare record SQL. Idempotente: 204 anche se la cartella
non esiste. Utile per scartare bundle di test o difettosi prima della
promozione.

`DELETE /api/partite/bundle?older_than_days=30` — batch cleanup: cancella
tutti i bundle la cui registrazione e' finita oltre N giorni fa. Bundle
con manifest illeggibile vengono saltati per sicurezza. Adatto per cron
job (es. `curl -X DELETE https://railway/api/partite/bundle` ogni notte).

### Nuove funzioni servizio

- `cancella_bundle(id_partita) -> bool` — elimina cartella idempotente
- `cancella_bundle_vecchi(giorni) -> {n_cancellati, ids_cancellati[]}`
  — batch cleanup con manifest-based filtering per `ts_fine_registrazione`

### Stato test

- 372/372 verdi (incluso 6 nuovi test sui DELETE bundle)
- Frontend typecheck pulito
- Ruff pulito su tutti i file nuovi

## Compatibilita'

Niente breaking changes. Le 21 patch dell'altra chat continuano a
funzionare. Devi solo:

1. **Sostituire `bleReale.ts`** con quello in `migrazione-godice-v0.4.zip`
   per attivare l'auto-reconnect (godice-lib v0.4.0)
2. Aggiornare `package.json` dell'app: `risiko-godice-lib@v0.4.0`

## Cosa resta aperto

- **Cron schedulato Railway** per il cleanup automatico bundle vecchi:
  Railway non ha cron nativo nel free tier. Soluzioni:
  a. Usare un service esterno (es. cron-job.org gratuito) che chiama
     `DELETE /api/partite/bundle` ogni notte
  b. Aggiungere APScheduler nel backend e lo schedula in-process
  c. Se passi a Railway Pro, usare i Cron Jobs nativi
- **UX miglioramenti pagina Bundle**: bottone "Scarta" accanto a
  "Promuovi" su ogni bundle nella lista, che chiama `DELETE` con
  conferma. Aggiungere quando l'MVP gira.
- **Pre-loading segmento successivo** nel video player: oggi tra un
  segmento e l'altro c'e' una micro-pausa di 100-300ms per loading. Per
  smoothness top-tier, serve un secondo `<video>` invisibile con
  preload. Non urgente.
