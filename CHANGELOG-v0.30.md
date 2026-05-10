# CHANGELOG v0.30 — frontend pagina "Bundle in attesa"

Continuazione di v0.29. Aggiunge la UI nel frontend Vite per gestire i bundle
caricati dall'app mobile e promuoverli a `Partita` SQL.

## Cosa e' cambiato

### Frontend

#### Nuova pagina: `PaginaBundleInAttesa.tsx` (route `/bundle`)

Lista i bundle gia' caricati dall'app mobile e ancora da promuovere a Partita
SQL. Coerente con l'estetica editoriale del resto del frontend (titolo grande
in Fraunces, lista a colonna, etichetta rossa).

Per ogni bundle mostra:
- ID partita (mono)
- Periodo (gg mese yyyy dalle hh:mm alle hh:mm, in italiano)
- Numero segmenti video
- Numero eventi BLE dichiarati
- Durata totale (ore + minuti)
- Bottone "Promuovi"

Click su "Promuovi" apre una **dialog modale** con due step:

1. **Input form**: campi `luogo` (default "Il Gufo - Roma") e `note_extra`
   (textarea opzionale). Bottone "Promuovi" chiama `POST /api/partite/da-bundle/<id>`.
2. **Risultato**: mostra n_video, n_eventi_importati, n_eventi_scartati,
   eventuali avvisi in `<details>`. Bottoni "Chiudi" e "Apri dettaglio
   partita →" (che fa navigate(`/partite/<id>`)).

Errori del backend (404, 400, 409) sono mostrati nel form prima di chiudere.

#### Nuovo client API: `apiPromozioneBundle`

`src/api/promozioneBundle.ts`:
- `apiPromozioneBundle.lista(): Promise<RispostaListaBundle>`
- `apiPromozioneBundle.promuovi(id, body): Promise<RispostaPromozioneBundle>`
- Tipi esportati: `BundleDisponibile`, `RispostaListaBundle`,
  `RichiestaPromozioneBundle`, `RispostaPromozioneBundle`

#### Voce menu

`Layout.tsx`: aggiunta `<VoceMenu to="/bundle">Bundle</VoceMenu>` nella nav
principale tra "Nuova partita" e "Classifica club".

### Stato build

```
typecheck:  pulito
vite build: 486.94 kB → 138.57 kB gzip (+1.5 KB rispetto a v0.29 baseline)
            2691 moduli, 6.54s
```

Backend: 372/372 test verdi, nessun cambiamento dalla v0.29.

## Flusso UX completo per l'arbitro

```
1. App mobile carica bundle → finisce in storage_partite/<id>/

2. Arbitro apre il backend Railway nel browser
3. Tab "Bundle" nella nav principale
4. Vede la lista dei bundle in attesa con periodo, n_segmenti, n_eventi
5. Click "Promuovi" sul bundle desiderato
6. Compila luogo + note (opzionali)
7. Click "Promuovi" → dialog mostra "Promozione in corso..."
8. Risposta: dialog mostra "Bundle promosso" con riepilogo
9. Click "Apri dettaglio partita →" → navigazione a /partite/<id>
10. Da qui il flusso review esistente: aggregazione, ricostruzione, CV,
   discrepanze, validazione finale
```

## Cosa resta

- **Cleanup automatico bundle non promossi**: scaduti dopo 30 giorni vengono
  cancellati. Cron job + endpoint `DELETE /api/partite/bundle/{id}`.
- **Multi-segmento player video** nella PaginaDettaglioPartita: il
  `PlayerVideo` esistente assume un singolo file. Va esteso per gestire
  `Video[]` come playlist con timeline globale.
- **Polling automatico** della lista bundle (oggi ricarica solo all'apertura
  pagina o dopo promozione). Refresh ogni 30s utile se il backend riceve
  bundle continuamente da piu' device.
