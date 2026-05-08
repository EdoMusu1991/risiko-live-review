# Schema bundle ZIP

Questo documento descrive il **contratto stabile** tra l'app mobile
(produttore) e il backend Risiko Live Review (consumatore).

Schema version corrente: **`1.0`**

Il `schema_version` è incluso in ogni manifest. Cambiamenti
backward-incompatibili richiederanno il bump della versione (`2.0`,
`3.0`, …) e il backend supporterà più versioni in parallelo per
permettere migrazioni graduali.

## Layout dello ZIP

```
risiko-partita-{partita_id_locale}.zip
├── manifest.json          # metadati strutturati
├── video.mp4              # registrazione completa
└── eventi.jsonl           # un evento per riga
```

I nomi dei file dentro lo ZIP sono fissi (`manifest.json`,
`video.mp4`, `eventi.jsonl`). I path sono relativi alla radice dello
ZIP (no sottocartelle).

Il backend rifiuta lo ZIP se:
- Manca uno qualsiasi dei 3 file
- I nomi non corrispondono (case-sensitive)
- Lo ZIP contiene path che escono dalla cartella di destrazione (zip-slip)
- Lo ZIP è corrotto / non leggibile

## `manifest.json`

Esempio completo:

```json
{
  "schema_version": "1.0",
  "partita_id_locale": "1947ab2c-0001-4f4f-aaaa-bbbbccccdddd",
  "luogo": "Il Gufo · Roma",
  "note": "Quartine girone B",
  "device": {
    "modello": "iPhone 11",
    "os": "iOS 17.4",
    "app_version": "0.1.0"
  },
  "registrazione": {
    "ts_inizio": "2026-05-08T20:00:00.000+00:00",
    "ts_fine": "2026-05-08T22:30:42.453+00:00",
    "durata_sec": 9042.453,
    "video_file": "video.mp4",
    "video_sha256": null,
    "video_dimensione_byte": 4521098112
  },
  "godice": {
    "n_dadi_attaccante": 3,
    "n_dadi_difensore": 3,
    "ble_id_attaccante": ["AA:BB:01:CC:DD:EE", "AA:BB:02:CC:DD:EE", "AA:BB:03:CC:DD:EE"],
    "ble_id_difensore": ["AA:BB:04:CC:DD:EE", "AA:BB:05:CC:DD:EE", "AA:BB:06:CC:DD:EE"]
  },
  "eventi": {
    "n_eventi_totali": 1247,
    "eventi_file": "eventi.jsonl"
  },
  "giocatori": [
    {"nome": "Edoardo", "colore": "rosso", "ordine_seduta": 1},
    {"nome": "Alice", "colore": "blu", "ordine_seduta": 2},
    {"nome": "Marco", "colore": "verde", "ordine_seduta": 3},
    {"nome": "Sara", "colore": "giallo", "ordine_seduta": 4}
  ]
}
```

### Campi

| Campo | Tipo | Note |
|---|---|---|
| `schema_version` | string | `"1.0"` per questa versione |
| `partita_id_locale` | string (UUID) | Generato sull'app, deve essere univoco per quella registrazione |
| `luogo` | string\|null | Testo libero |
| `note` | string\|null | Testo libero |
| `device.modello` | string | Es. `"iPhone 11"` |
| `device.os` | string | Es. `"iOS 17.4"` |
| `device.app_version` | string | Versione `package.json` dell'app |
| `registrazione.ts_inizio` | ISO 8601 datetime | Con timezone (es. `+02:00` o `Z`) |
| `registrazione.ts_fine` | ISO 8601 datetime | Con timezone |
| `registrazione.durata_sec` | float (>0) | Calcolata sull'app, il backend la riverifica con ffprobe |
| `registrazione.video_file` | string | Sempre `"video.mp4"` per ora |
| `registrazione.video_sha256` | string\|null | SHA256 hex lowercase, opzionale |
| `registrazione.video_dimensione_byte` | int (>0) | |
| `godice.n_dadi_attaccante` | int (0-3) | |
| `godice.n_dadi_difensore` | int (0-3) | |
| `godice.ble_id_attaccante` | string[] | MAC address ordinati per slot 1,2,3 |
| `godice.ble_id_difensore` | string[] | |
| `eventi.n_eventi_totali` | int (≥0) | Numero righe nel file `eventi.jsonl` (informativo, il backend conta comunque) |
| `eventi.eventi_file` | string | Sempre `"eventi.jsonl"` |
| `giocatori[]` | array (min 2) | Vedi sotto |

### `giocatori[]`

Ogni elemento:

| Campo | Tipo | Note |
|---|---|---|
| `nome` | string | Nome breve UI (max ~20 char raccomandati) |
| `colore` | string | Uno di: `"rosso"`, `"blu"`, `"verde"`, `"giallo"`, `"nero"`, `"viola"` |
| `ordine_seduta` | int (1-6) | Posizione al tavolo |

I colori devono essere unici tra i giocatori. Il backend solleva
errore se ci sono duplicati.

## `video.mp4`

Container MP4, codec H.264 (consigliato) o HEVC. Risoluzione e
bitrate liberi.

Vincoli pratici (non enforced ma fortemente raccomandati):
- Risoluzione **almeno** 1920×1080 per leggibilità del CV
- Frame rate 30 fps
- Orientamento verticale (telefono attaccato a soffitto, asse lungo
  vs. asse corto della plancia)

Il backend estrae i metadati reali (codec, risoluzione, durata) con
`ffprobe`, **ignorando** i campi `codec`/`risoluzione` se presenti
nel manifest. Solo `dimensione_byte` è preso dal manifest (per
display rapido) ma anche questa viene riverificata.

## `eventi.jsonl`

Un evento per riga. Encoding UTF-8. Newline `\n`. Righe vuote
ignorate. Righe malformate scartate con nota nella risposta di
import (NON bloccano l'import).

### Tipi di evento (versione 1.0)

#### `dado_lanciato` (richiesto)

L'evento principale: un GoDice ha emesso un valore.

```json
{
  "ts": "2026-05-08T20:14:32.451+00:00",
  "tipo": "dado_lanciato",
  "ble_id": "AA:BB:01:CC:DD:EE",
  "ruolo": "attaccante",
  "slot": 1,
  "valore": 5
}
```

| Campo | Tipo | Note |
|---|---|---|
| `ts` | ISO 8601 datetime | Con timezone, generato sul telefono al momento del lancio |
| `tipo` | `"dado_lanciato"` | |
| `ble_id` | string | MAC address del dado |
| `ruolo` | `"attaccante"` \| `"difensore"` | Speculare al manifest |
| `slot` | int (1-3) | Speculare al manifest |
| `valore` | int (1-6) \| null | Null se la lettura del dado è ambigua (orientation indeterminata) |

Il backend mappa questi eventi a `EventoGrezzo` con
`tipo=DADI_LANCIATI`, `fonte=DADO_BLE`.

#### Tipi riservati per estensione futura (1.0)

Questi tipi possono comparire nello jsonl, ma in 1.0 il backend li
**ignora** silenziosamente:

- `dado_collegato`: `{ts, tipo, ble_id, ruolo, slot}` — un dado si è
  riconnesso dopo una disconnessione
- `dado_disconnesso`: stesso schema — un dado si è disconnesso volontariamente
- `connessione_persa`: stesso schema — connessione persa per assenza segnale
- `stop_registrazione`: `{ts, tipo, motivo}` — l'utente ha fermato
  la registrazione (`motivo` ∈ `manuale`, `errore_camera`,
  `batteria_bassa`, `altro`)

L'app DEVE comunque scriverli: serviranno per analytics future
(stabilità BLE) e per debug. Quando il backend supporterà 1.1, li
trasformerà in eventi grezzi anche.

## Errori di import

Il backend ritorna `400 Bad Request` con `detail` testuale per:

- ZIP corrotto / non leggibile
- File mandatory mancanti dentro lo ZIP
- `manifest.json` non parsabile come JSON
- `manifest.json` non rispetta lo schema (campo richiesto mancante,
  tipo errato, valore fuori range)
- `schema_version` non supportata dal backend
- Hash SHA256 dichiarato non corrisponde al video reale

E `500 Internal Server Error` per errori inattesi del backend
(filesystem pieno, DB down, ecc.).

## Risposta di successo

```json
{
  "partita_id": "uuid-server",
  "n_giocatori": 4,
  "n_eventi_grezzi_creati": 1245,
  "n_eventi_scartati": 2,
  "durata_video_sec": 9042.5,
  "dimensione_video_byte": 4521098112,
  "note": ["Riga 547 eventi.jsonl scartata: ..."]
}
```

L'app mostra `partita_id` (UUID server) all'utente come ricevuta.
Il `partita_id` è anche il segmento URL per la review web:
`https://risiko-review.example.com/partite/{partita_id}`.

## Versioning

Versioni planned per evoluzione futura:

- **`1.0`** (attuale): MVP single-camera + 6 dadi BLE
- **`1.1`** (futuro): aggiunge supporto eventi `dado_collegato` etc
  come eventi grezzi importati
- **`2.0`** (futuro): potrebbe supportare multi-camera (es. una zoom
  sul mazzo carte) o QR carte. Breaking changes.

L'app DEVE inviare `schema_version` esattamente uguale alla versione
che intende mandare. Mai inviare versioni più alte di quella che
sa scrivere.
