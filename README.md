# Risiko Live Review — App Mobile

App **React Native bare** (iOS + Android) che registra una partita di
Risiko al club e produce un bundle ZIP da caricare al server di review.

Stato: **scaffold completo, runnable in simulatore appena generate le
cartelle native (`ios/` e `android/`)**.

## Cosa fa l'app

Solo due cose:

1. **Registra video** della partita tramite la fotocamera del telefono
   appeso sopra la plancia
2. **Ascolta i 6 GoDice** via Bluetooth Low Energy e logga ogni lancio
   con timestamp

Tutto il resto (CV, regole, ricostruzione, replay) avviene sul server
dopo che l'utente carica il bundle.

## Architettura

```
┌─────────────────────────────────────────────────┐
│  Schermata 1: Setup partita                     │
│  giocatori + luogo + note                       │
└──────────────────┬──────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────┐
│  Schermata 2: Configura dadi (modale)           │
│  scan BLE + associazione ai 6 slot canonici     │
└──────────────────┬──────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────┐
│  Schermata 3: Registrazione attiva              │
│  timer + counter eventi + STOP                  │
└──────────────────┬──────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────┐
│  Schermata 4: Riepilogo + invio                 │
│  invia ora / salva / annulla                    │
└──────────────────┬──────────────────────────────┘
                   ↓
        bundle ZIP → POST /api/import/bundle-mobile
                       (backend Risiko Live Review)

┌─────────────────────────────────────────────────┐
│  Schermata 5: Cronologia (raggiungibile sempre) │
│  riprova upload falliti, elimina vecchi         │
└─────────────────────────────────────────────────┘
```

## Stack tecnico

- **React Native 0.75 bare** (no Expo: ci servono moduli nativi)
- **TypeScript strict**
- **react-native-vision-camera** — `AVCaptureSession` (iOS) + `CameraX` (Android)
- **react-native-ble-plx** — scan/connect/notify BLE GoDice
- **react-native-fs** — I/O file (jsonl writer + upload background)
- **react-native-zip-archive** — bundle ZIP
- **react-native-mmkv** — persistenza locale (cronologia upload)
- **@react-navigation/native** + native-stack — routing tra schermate

## Struttura

```
mobile/
├── App.tsx                           # root + navigation stack
├── index.js                          # entry point RN
├── package.json
├── tsconfig.json                     # strict + paths "@/*"
├── babel.config.js                   # alias module-resolver
├── metro.config.js
├── app.json
├── .env.example
├── docs/
│   └── schema-bundle.md              # CONTRATTO con il backend
└── src/
    ├── tema.ts                       # palette e tipografia
    ├── configurazione.ts             # backend_url, app_version
    ├── navigazione.ts                # ParametriRotteApp type
    ├── tipi/
    │   ├── partita.ts                # ColoreGiocatore, Giocatore
    │   ├── godice.ts                 # RuoloDado, ConfigurazioneGoDado
    │   ├── bundle.ts                 # Manifest, RigaEventoJsonl
    │   ├── upload.ts                 # RecordUpload, StatoUpload
    │   └── index.ts
    ├── contesto/
    │   └── partita.tsx               # ProvenanzaPartita context
    ├── servizi/
    │   ├── godice.ts                 # ServizioGoDice (interfaccia + StubGoDice)
    │   ├── registratore.ts           # ServizioRegistratore (interfaccia + Stub)
    │   ├── bundleBuilder.ts          # costruisciBundle / eliminaBundle
    │   ├── uploader.ts               # caricaBundle
    │   └── storageLocale.ts          # MMKV wrapper cronologia
    └── schermate/
        ├── SchermataSetup.tsx
        ├── SchermataDadi.tsx
        ├── SchermataRegistrazione.tsx
        ├── SchermataRiepilogo.tsx
        └── SchermataCronologia.tsx
```

## Filosofia "stub per dev, reale per prod"

I servizi `godice.ts` e `registratore.ts` espongono un'**interfaccia**
e una **implementazione stub** che simula dadi e camera senza hardware
reale. Questo permette di:

- Iterare sull'UX senza dover compilare per dispositivo fisico
- Testare il flow end-to-end con dadi virtuali che lanciano da soli
- Non bloccare lo sviluppo finché non arrivano i GoDice fisici

Quando si avranno i dadi reali, basta sostituire `StubGoDice` con
`GoDiceBlePlx` (che farà sniffing GATT + parser orientazione → valore).
La firma resta la stessa.

## Setup di sviluppo

### Prerequisiti

- Node 20+
- (per build iOS) Mac + Xcode + CocoaPods
- (per build Android) Android Studio + JDK 17 + Android SDK

### Generazione cartelle native (prima volta)

Le cartelle `ios/` e `android/` non sono in repo (sono boilerplate di
RN, ricreabili sempre). Per generarle:

```bash
cd mobile
npx react-native init RisikoLiveReview --version 0.75.4 --skip-install
# Poi: copia solo `ios/` e `android/` da quello scaffold dentro la
# cartella mobile/ esistente, mantenendo i nostri src/, App.tsx, ecc.
```

### Permessi nativi

Una volta generate le cartelle native, configurare:

**iOS** (`ios/RisikoLiveReview/Info.plist`):
- `NSCameraUsageDescription` — "Per registrare la partita"
- `NSMicrophoneUsageDescription` — "Per audio di ambiente"
- `NSBluetoothAlwaysUsageDescription` — "Per leggere i dadi GoDice"
- `NSBluetoothPeripheralUsageDescription` — idem

**Android** (`android/app/src/main/AndroidManifest.xml`):
- `android.permission.CAMERA`
- `android.permission.RECORD_AUDIO`
- `android.permission.BLUETOOTH_SCAN`
- `android.permission.BLUETOOTH_CONNECT`
- `android.permission.WRITE_EXTERNAL_STORAGE` (per video lunghi)
- `android.permission.FOREGROUND_SERVICE` (per registrazione in background)

### Comandi

```bash
cd mobile
npm install
npm start              # Metro bundler
npm run android        # build + run su emulator/device Android
npm run ios            # build + run su simulator/device iOS (solo Mac)
npm run typecheck      # tsc --noEmit
npm run lint           # eslint
```

### Testare lo scaffold senza device

Anche senza Mac/Android, puoi:

1. `npm run typecheck` — verifica che TypeScript non abbia errori
2. Aprire i file `.tsx` nell'editor per vederne la struttura

Per un test interattivo dell'UI, basta uno qualsiasi tra:
- Mac → simulatore iOS
- Windows + Android Studio → emulatore Android

Ricorda: i servizi sono **stub** quindi NON serve hardware fisico per
testare il flow. I dadi virtuali si "scansionano" istantaneamente e
si "lanciano" su comando.

## Convenzioni

- Italiano per nomi di variabili, file, funzioni, errori
- TypeScript **strict**, no `any`
- Schemi I/O speculari ai Pydantic backend (vedi `docs/schema-bundle.md`)
- Niente Redux / Zustand: state corrente in Context API, persistente in MMKV

## Schema bundle

Vedi [docs/schema-bundle.md](docs/schema-bundle.md). È il contratto
**stabile** col backend: cambiare con cura.

## Piano next steps

1. **Generare cartelle native** (`ios/` + `android/`)
2. **Setup permessi** + linking moduli nativi
3. **Sostituire `StubGoDice`** con `GoDiceBlePlx` reale (richiede
   sniffing del GATT profile sui dadi quando arrivano)
4. **Sostituire `StubRegistratore`** con `RegistratoreVisionCamera`
5. **Test sul campo**: 30 minuti di registrazione al club, poi
   verifica che il backend importi correttamente il bundle
6. **Build TestFlight** (iOS) per uso al club senza dover aprire Xcode
   ogni volta
