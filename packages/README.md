# packages/

Pacchetti TypeScript condivisi del progetto Risiko Live Review.

## `eventi-schema/`

Schema Zod degli eventi di partita Risiko (12 tipi discriminated union +
bundle replay). Source of truth lato TypeScript per il contratto
backend↔frontend e per l'integrazione con Battle Commander.

**Consumatori**:

- **Frontend RL** (`../frontend`): importa via `file:` dependency. Tipi
  TS narrowing-friendly disponibili in `src/tipi/dominio.ts` via
  re-export (`EventoValidatoTipato`, `DatiAttaccoRisolto`, ecc.).
- **Battle Commander** (esterno): riceve il pacchetto come zip, lo
  installa nel suo monorepo o copia in `src/replay-lib/packages/`.

**Source of truth semantica**: gli schemi Pydantic in
`backend/app/schemi/dati_eventi.py`. Lo schema zod è una traduzione TS
verificata via:

- Test di round-trip end-to-end Python→JSON→zod nel test di
  esportazione `formato=replay`
- Fixture concreta `eventi-schema/fixtures/bundle-replay-esempio.json`
  generata dal backend e validata dal test zod (regression test contro
  drift di schema)

## Workflow di sviluppo

```bash
# Build dei pacchetti (auto eseguito da npm install in frontend)
cd packages/eventi-schema
npm install
npm run build

# Test
npm test

# Aggiornare il fixture dal backend (dopo modifiche significative)
cd ../../backend
python scripts/genera_bundle_esempio.py \
  ../packages/eventi-schema/fixtures/bundle-replay-esempio.json

# Verificare che il fixture aggiornato resti valido lato zod
cd ../packages/eventi-schema
npm test
```

## Esportare verso Battle Commander

Quando BC ha bisogno del pacchetto:

```bash
cd packages/eventi-schema
npm pack  # produce risiko-eventi-schema-0.1.0.tgz
```

Oppure per uno zip umano-leggibile:

```bash
cd packages
zip -r eventi-schema-v0.1.zip eventi-schema/ \
  -x '*/node_modules/*' '*/dist/*'
```

## Versioning

- `0.1.x` — breaking changes ammessi (pre-stabilizzazione)
- `0.x.0` (prossimo: 0.2) — alla prima integrazione reale BC, congelo l'API
- `1.0.0` — stable, semver pulito

`schema_version` interno al `BundleReplay` (attualmente `1.0`) è separato
dalla versione del pacchetto npm: cambia solo se cambia il formato del
bundle scambiato fra BC e RL.
