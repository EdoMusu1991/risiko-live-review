#requires -version 5.0

<#
.SYNOPSIS
    Verifica completa del progetto risiko-live-mobile prima del build EAS.

.DESCRIPTION
    Esegue checks per essere sicuro che il progetto sia pronto per build:
    - Node 20+ installato
    - Dipendenze npm presenti
    - godice-lib v0.4 buildata
    - tsc --noEmit pulito
    - vitest verdi
    - app.config.ts presente con i campi corretti
    - eas.json presente

    Usage:
        cd risiko-live-mobile
        powershell -ExecutionPolicy Bypass -File scripts\verifica.ps1
#>

$ErrorActionPreference = 'Stop'

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "=== $Message ===" -ForegroundColor Cyan
}

function Write-Ok {
    param([string]$Message)
    Write-Host "OK  $Message" -ForegroundColor Green
}

function Write-Fail {
    param([string]$Message)
    Write-Host "ERR $Message" -ForegroundColor Red
    exit 1
}

function Write-Warn {
    param([string]$Message)
    Write-Host "?   $Message" -ForegroundColor Yellow
}

# ============================================================================
# Inizio verifica
# ============================================================================

Write-Host ""
Write-Host "Risiko Live Mobile - Script Verifica Pre-Build" -ForegroundColor Magenta
Write-Host ""

# 1. Posizione corretta
Write-Step "Posizione e file di progetto"
if (-not (Test-Path ".\package.json")) {
    Write-Fail "Esegui questo script DALLA RADICE del progetto risiko-live-mobile (non da scripts\)"
}
$pkg = Get-Content package.json | ConvertFrom-Json
if ($pkg.name -ne "risiko-live-mobile") {
    Write-Fail "package.json non sembra essere quello di risiko-live-mobile (name = $($pkg.name))"
}
Write-Ok "package.json risiko-live-mobile trovato"

if (-not (Test-Path ".\App.tsx")) { Write-Fail "App.tsx mancante" }
if (-not (Test-Path ".\app.config.ts")) { Write-Fail "app.config.ts mancante" }
if (-not (Test-Path ".\eas.json")) { Write-Fail "eas.json mancante" }
Write-Ok "App.tsx, app.config.ts, eas.json presenti"

# 2. Node version
Write-Step "Node.js"
try {
    $nodeVer = (& node --version) 2>&1
    if ($nodeVer -match "^v(\d+)") {
        $major = [int]$Matches[1]
        if ($major -lt 20) {
            Write-Fail "Node v$($Matches[1]) - serve Node v20 o superiore. Aggiorna da nodejs.org"
        }
        Write-Ok "Node $nodeVer"
    } else {
        Write-Fail "Output node --version non parsabile: $nodeVer"
    }
} catch {
    Write-Fail "node non installato. Installa Node 20 LTS da nodejs.org"
}

# 3. node_modules
Write-Step "node_modules"
if (-not (Test-Path ".\node_modules")) {
    Write-Warn "node_modules mancante - eseguo 'npm install' (puo richiedere 2-5 minuti)..."
    & npm install 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Fail "npm install fallito" }
}
Write-Ok "node_modules presente"

# 4. godice-lib
Write-Step "Dipendenza locale godice-lib"
if (-not (Test-Path ".\libs\risiko-godice-lib")) {
    Write-Fail "Cartella libs\risiko-godice-lib mancante - lo zip e' incompleto?"
}
if (-not (Test-Path ".\libs\risiko-godice-lib\dist")) {
    Write-Warn "godice-lib non buildata - eseguo build..."
    Push-Location .\libs\risiko-godice-lib
    if (-not (Test-Path ".\node_modules")) {
        & npm install 2>&1 | Out-Null
    }
    & npm run build 2>&1 | Out-Null
    Pop-Location
    if ($LASTEXITCODE -ne 0) { Write-Fail "Build godice-lib fallito" }
}
Write-Ok "godice-lib presente e buildata"

# Verifica che node_modules\risiko-godice-lib sia presente (linked)
if (-not (Test-Path ".\node_modules\risiko-godice-lib")) {
    Write-Warn "risiko-godice-lib non linkata - re-install..."
    & npm install ./libs/risiko-godice-lib 2>&1 | Out-Null
}
Write-Ok "risiko-godice-lib linkata in node_modules"

# 5. typecheck
Write-Step "TypeScript typecheck"
$tscOutput = & npx tsc --noEmit 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host $tscOutput
    Write-Fail "tsc --noEmit ha errori (vedi sopra)"
}
Write-Ok "tsc --noEmit pulito"

# 6. vitest
Write-Step "Test vitest"
$testOutput = & npm test 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host $testOutput
    Write-Fail "Test falliti (vedi sopra)"
}
if ($testOutput -match "Tests\s+(\d+)\s+passed") {
    $nTests = $Matches[1]
    Write-Ok "$nTests test verdi"
} else {
    Write-Warn "Output test non parsabile, ma exit code 0 - assumo OK"
}

# 7. app.config.ts: campi critici
Write-Step "Configurazione app.config.ts (audit checks)"
$appConfig = Get-Content .\app.config.ts -Raw

if ($appConfig -notmatch "'audio'") {
    Write-Fail "app.config.ts NON ha 'audio' in UIBackgroundModes - critical fix #3 dell'audit non applicato!"
}
Write-Ok "UIBackgroundModes include 'audio' (audit CRITICAL #3)"

if ($appConfig -match "bundleIdentifier:\s*'(.+?)'") {
    $bundleId = $Matches[1]
    if ($bundleId -eq "club.ilgufo.risikolive") {
        Write-Warn "bundleIdentifier = '$bundleId' - probabilmente gia' usato dal tuo Apple ID."
        Write-Warn "  Quando lanci 'eas build', cambialo a qualcosa di unico tipo 'it.tuonome.risikolive'"
    } else {
        Write-Ok "bundleIdentifier = '$bundleId'"
    }
} else {
    Write-Warn "bundleIdentifier non trovato in app.config.ts"
}

# 8. eas-cli
Write-Step "eas-cli"
try {
    $easVer = (& eas --version) 2>&1
    if ($easVer -match "(\d+\.\d+\.\d+)") {
        Write-Ok "eas-cli $($Matches[1])"
    } else {
        Write-Warn "eas-cli installato ma versione non parsabile: $easVer"
    }
} catch {
    Write-Warn "eas-cli NON installato. Per buildare l'IPA esegui: npm install -g eas-cli"
}

# 9. Sommario
Write-Host ""
Write-Host "=== TUTTO OK ===" -ForegroundColor Green
Write-Host ""
Write-Host "Prossimi step:" -ForegroundColor Cyan
Write-Host "  1. eas login          (se non l'hai mai fatto)"
Write-Host "  2. eas init           (collega questo progetto al tuo workspace Expo)"
Write-Host "  3. eas build --profile preview --platform ios"
Write-Host "  4. Scarica IPA, installa via AltStore (vedi GUIDA_PRIMO_TEST.md)"
Write-Host ""
