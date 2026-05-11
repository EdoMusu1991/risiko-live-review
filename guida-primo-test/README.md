# Guida Primo Test iPhone

Contiene tutto quello che serve a Edoardo per portare l'app mobile dal
bundle ZIP allo schermo dell'iPhone e fare la prima registrazione test.

## File

- **`verifica.ps1`** - script PowerShell di autodiagnostica progetto.
  Esegui da dentro `risiko-live-mobile/` per controllare che tutto sia
  pronto prima di `eas build`. Verifica: Node 20+, node_modules,
  godice-lib buildata, typecheck pulito, vitest verdi, audit fix
  applicati, bundleIdentifier configurato.

- **`GUIDA_PRIMO_TEST.md`** - guida passo-passo, dal momento in cui hai
  l'IPA installato sull'iPhone fino al primo bundle caricato sul backend
  Railway. 13 step organizzati in 5 fasi: pre-test, primo avvio,
  test BLE 1 dado, prima registrazione 5min, verifica backend.

## Uso

### Per verificare il progetto prima del build:

```powershell
cd risiko-live-mobile

# Copia lo script
Copy-Item ..\guida-primo-test\verifica.ps1 .\scripts\
mkdir scripts -ErrorAction SilentlyContinue

# Esegui
powershell -ExecutionPolicy Bypass -File scripts\verifica.ps1
```

L'output ti dice esattamente cosa va e cosa no. Se trovi un problema
da "ERR", risolvilo prima di buildare.

### Per il primo test sull'iPhone:

Apri `GUIDA_PRIMO_TEST.md` su PC + iPhone in mano. Segui gli step uno
alla volta. Non saltare avanti finche' uno non e' "verde".

## Tempistiche realistiche

- Setup ambiente + EAS Build IPA: **2-3 ore** la prima volta
- AltStore setup: **45 minuti** una volta sola
- Primo test 5 minuti sull'iPhone: **30 minuti** (inclusi
  troubleshooting tipici)
- Test con 6 dadi: **1 ora** dopo il primo test 1-dado
- Test partita reale 2.5h al club: **3 ore** del torneo + 30min upload
- Promozione partita su backend + review: **15-30 minuti**

## Cosa NON e' coperto in questa guida

- **EAS Build setup** (`eas login`, `eas init`, `eas build`) - coperto
  nella guida AltStore inviata in chat
- **AltStore install** (AltServer + AltStore su iPhone via Wi-Fi sync)
  - coperto nella guida AltStore
- **Promozione bundle a Partita SQL** - workflow sul backend Railway,
  scopri facendo dalla UI /bundle del frontend
- **Annotazione Roboflow** - coperto in `roboflow-scaffold.zip`
- **Refresh AltStore ogni 7 giorni** - coperto nella guida AltStore
