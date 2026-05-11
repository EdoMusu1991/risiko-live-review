# Guida primo test sull'iPhone

Sequenza dettagliata dal momento in cui hai l'IPA installato sul tuo
iPhone al momento in cui hai registrato la prima partita test e l'hai
caricata sul backend.

Suppone che `risiko-live-mobile.zip` sia gia' stato scompattato, le
dipendenze installate, `eas build` completato e l'IPA installato via
AltStore. Se NON sei a questo punto: usa prima `scripts/verifica.ps1`
nel progetto.

## Checklist pre-test (5 minuti)

Prima di accendere l'app fai questi check:

- [ ] **Batteria iPhone**: almeno 50%. Una registrazione test consuma
  ~10%/h. Per partite reali (2.5h), cavo Lightning collegato.
- [ ] **Spazio iPhone libero**: almeno 5 GB. Una partita 2.5h FullHD
  occupa 3-4 GB.
- [ ] **6 dadi GoDice carichi**. Tienili in mano e agitali per
  svegliarli dallo sleep prima del test.
- [ ] **Backend Railway raggiungibile**:
  ```
  curl https://risiko-scores.up.railway.app/api/health
  → deve rispondere {"status": "ok", ...}
  ```
- [ ] **WiFi del club / casa funzionante** sull'iPhone (per upload
  bundle a fine partita).

## Primo avvio dell'app

### Step 1: Apri l'app dalla home

L'icona si chiama "Risiko Live". Al primo tap potrebbe apparire un
warning "Untrusted Developer": chiudi l'app, vai in:

```
Settings → General → VPN & Device Management → [tuo Apple ID] → Trust
```

Riapri l'app. Si avvia.

### Step 2: Concedi i permessi

In sequenza l'app chiede:

1. **Camera** → "Allow"
   - serve per registrare la plancia
2. **Microphone** → "Allow"
   - obbligatorio per Vision Camera (anche se l'audio non viene poi
     processato per la review, e' richiesto per il background recording)
3. **Bluetooth** → "Allow"
   - serve per i 6 dadi GoDice

Se neghi anche solo uno, l'app non funziona. Per riconcederlo:
```
Settings → Risiko Live → Camera/Microphone/Bluetooth → ON
```

### Step 3: Verifica la Home

Vedi 4 bottoni:
- **Nuova partita**
- **Esporta bundle**
- **Gestione dadi**
- **Diagnostica**

Tap **Diagnostica** prima di tutto.

### Step 4: Diagnostica baseline

Nella schermata Diagnostica controlla:
- **Device ID**: deve essere generato automaticamente (UUID-like).
- **Spazio libero**: minimo 5 GB. Se vedi < 1 GB, l'app rifiutera' di
  registrare.
- **Modalita' BLE**: dovrebbe essere `mock` di default. Lo cambieremo
  dopo aver associato i dadi.
- **Associazioni dadi**: vuoto (atteso al primo avvio).

Se qualcosa non torna: foto della schermata + dimmelo in chat.

Torna indietro alla Home.

## Test BLE con 1 dado (15 minuti)

L'obiettivo: confermare che 1 dado fisico si connette via BLE e l'app
riceve gli eventi `dadi_lanciati`.

### Step 5: Vai in Gestione Dadi

Home → "Gestione Dadi".

Vedi due sezioni:
- **Modalita' BLE**: switch `mock` / `reale`
- **Associazioni dadi**: lista vuota dei 6 ruoli

Switcha a **reale**. La modalita' viene salvata in MMKV (persistente).

### Step 6: Scan

Tap **"Avvia scan"**.

In 5-15 secondi dovresti vedere apparire dispositivi BLE. Se hai 1 solo
dado acceso vicino, ne vedi 1 (oppure piu' device BLE casuali della
casa: cuffie, smartwatch, ecc.).

**Importante**: il firmware Particula non pubblicizza il nome BLE, quindi
il dado appare con nome vuoto o "unknown". Cerca tra i dispositivi quello
che corrisponde al tuo dado (potresti dover provarli uno alla volta).

Per identificarlo:
1. Tap su un device "unknown"
2. Lo schermo mostra "Sto interrogando..." per 1-2 secondi
3. Se e' un GoDice, l'app lo riconosce e ti mostra "Servizio Particula
   trovato"
4. Se NON e' un GoDice, vedi "Non e' un dado GoDice" → torna indietro e
   prova un altro device

Quando trovi il dado:
- Tap **"Associa a Att-1"**
- L'associazione viene salvata in MMKV
- Tap **"Ferma scan"**

### Step 7: Test connessione

Torna alla Home, tap "Diagnostica":
- **Associazioni dadi**: vedi `att-1: <deviceId>`

Adesso il dado e' associato. Il prossimo step (registrazione) lo
connettera' davvero.

## Prima registrazione test (15 minuti)

L'obiettivo: registrare 5 minuti di video + verificare che gli eventi
del dado arrivino, salvare il bundle.

### Step 8: Avvia registrazione

Home → "Nuova Partita".

Vedi:
- Preview camera (inquadra la plancia o anche solo il tavolo)
- 6 pallini per i dadi: 5 grigi + 1 verde (att-1 = il dado associato)
- Pulsante "Avvia registrazione"

Tap **"Avvia registrazione"**.

Dopo 2-3 secondi vedi:
- Stato: `REGISTRAZIONE IN CORSO`
- Timer che parte da 00:00:00
- Counter "Eventi BLE: 0" e "Segmenti: 0"

### Step 9: Tira il dado

Tira il dado vicino all'iPhone. **Atteso**: il counter "Eventi BLE" sale
di 1-2 per ogni tiro. (1 evento `dadi_lanciati` + eventualmente uno
`stable_after_tilt` se hai mosso il dado prima di stabilizzarlo.)

Tira 5-6 volte.

### Step 10: Test sleep + reconnect

Lascia il dado fermo per **1 minuto** senza toccarlo. **Atteso**:

- Dopo ~30-60s il pallino del dado att-1 diventa **giallo**
  (`in_riconnessione` - il dado si e' addormentato, godice-lib v0.4 sta
  riconnettendo)
- Dopo qualche secondo torna **verde** (riconnesso)

Se invece il pallino diventa **rosso** (`MORTO`), godice-lib non e'
riuscito a riconnettere in 10 tentativi (~3 min) — significa che il dado
e' troppo lontano, batteria scarica, o il firmware si comporta in modo
inatteso. Documenta cosa hai osservato e dimmelo.

Tira di nuovo il dado: il counter eventi sale.

### Step 11: Ferma registrazione

Tap **"Ferma registrazione"**.

Alert: "Registrazione completata. N segmenti, M eventi BLE, X.XX GB".

Tap OK. Torni alla Home.

### Step 12: Esporta bundle

Home → "Esporta bundle".

Vedi la partita appena registrata nella lista. Stato: "non esportato".

Tap su di lei → bottone **"Esporta"**.

L'app:
1. Crea `manifest.json` con metadata
2. Zippa tutti i segmenti `seg_*.mp4` + `manifest.json` + `eventi.jsonl`
3. Salva il file in `<documents>/bundles/<id_partita>.zip`

Tempo: pochi secondi per una partita di 5 minuti.

Alert: "Bundle creato: <path>".

### Step 13: Carica al backend

Sullo stesso item, ora vedi il bottone **"Carica"**.

Verifica nella sezione "Impostazioni upload" (collassabile in alto) che
l'URL backend sia `https://risiko-scores.up.railway.app` (default
corretto).

Tap **"Carica"**.

Lo stato diventa "in_caricamento" con una barra di progresso. Per una
partita 5 min: upload ~50-100 MB → 30 secondi su wifi buono.

Se va a buon fine: stato "caricato". Alert "Upload completato".

Se fallisce: stato "errore" con messaggio. Tipicamente:
- "Timeout": rete troppo lenta → riprova
- "HTTP 413": file troppo grande → fix backend (max 10 GB attualmente)
- "HTTP 5xx": backend down → controlla Railway

## Verifica sul backend (5 minuti)

Apri sul PC: https://risiko-scores.up.railway.app/bundle

Dovresti vedere la tua partita test in "Bundle in attesa". Periodo, n
segmenti, n eventi.

Tap **"Promuovi"** → dialog → "Promuovi" di nuovo.

Dialog di successo: "X video importati, Y eventi importati".

Tap **"Apri dettaglio partita"** → vai sulla pagina partita.

Vedi:
- Player video (un singolo segmento per 5 min test)
- Lista eventi grezzi: `dadi_lanciati` con dado_id=att-1, valore, xyz

**Se sei qui, tutto il flusso end-to-end funziona.** Puoi passare a:

- Test con 6 dadi → ripeti dallo Step 5 ma associa tutti i 6 dadi
- Test partita finta 1h con altri membri del club → flusso uguale, solo
  piu' lungo
- Test partita reale 2.5h → il torneo vero

## Cosa fare se qualcosa non va

### Camera nera al primo avvio

Probabilmente UIBackgroundModes manca `audio`. Verifica:
```powershell
type app.config.ts | findstr UIBackgroundModes
# atteso: UIBackgroundModes: ['bluetooth-central', 'audio'],
```

Se manca, applica audit fix CRITICAL #3 (gia' dovrebbe essere nel
bundle che ti ho dato, ma controllo non costa).

### Scan BLE vuoto

Possibili cause:
1. Bluetooth iPhone disattivato → Settings → Bluetooth → ON
2. Dado scarico → ricaricalo (LED rosso lampeggiante = batteria
   scarica)
3. Dado troppo lontano → meno di 1 metro per il primo test
4. Altro device BLE che blocca → riavvia Bluetooth iPhone

### Eventi BLE non arrivano dopo tap sul dado

1. Verifica che il pallino sia **verde**, non grigio
2. Tira il dado piu' forte (deve "atterrare" con un piccolo impatto;
   appoggiarlo dolcemente non genera un evento `stable`)
3. Controlla console dev (se hai eas client connesso) per warning

### Upload fallisce con timeout

1. Test connessione: apri Safari → `https://risiko-scores.up.railway.app/api/health`
   deve rispondere 200
2. Rete cellulare lenta → passa a wifi
3. Backend in maintenance → controlla Railway dashboard
4. Bundle troppo grande → backend M14 ha limite 10 GB (vedi
   `UPLOAD_MAX_SIZE_MB` env var)

### App crasha all'avvio

Guarda log via Xcode (se hai Mac) o:
```powershell
# Su Windows con eas-cli
eas device:list  # trova il device id del tuo iPhone
eas diagnostics  # log generale
```

Probabilmente un modulo native non e' correttamente linkato. Mandami
output.

## Cosa devi mandarmi se trovi un problema

Quando ti blocchi:
1. Screenshot dell'errore (se UI)
2. Step esatto in cui sei (es. "Step 6: scan vuoto dopo 30s")
3. Diagnostica → screenshot
4. Cosa hai fatto subito prima

Cosi' posso isolare il problema senza dover indovinare.

## Quando hai completato il primo test

Quando arrivi alla fine (vedi la partita sul backend), siamo a livello
**MVP funzionante**. Da qui in poi:

1. **Iterare l'app**: piccoli fix UX, miglioramenti
2. **Raccogliere dati per Roboflow**: 5-10 partite test → 1500+ frame
   per addestrare il modello CV
3. **Onboardare i cameramen del club**: spiega loro il flusso, fai
   girare l'app da un volontario al primo torneo ufficiale

Buona fortuna con il test.
