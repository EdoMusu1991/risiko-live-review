"""
Smoke test end-to-end: costruisce un bundle ZIP "realistico" e lo
manda all'endpoint POST /api/import/bundle-mobile per verifica
manuale. Lanciare con `python verifica_e2e.py`.

Non parte di pytest. Utile per verificare il backend dal vivo prima
di un deploy o dopo cambi grossi.
"""

from __future__ import annotations

import io
import json
import zipfile
from datetime import UTC, datetime, timedelta

import httpx


def costruisci_bundle_realistico() -> bytes:
    inizio = datetime.now(UTC)
    fine = inizio + timedelta(minutes=15)

    manifest = {
        "schema_version": "1.0",
        "partita_id_locale": "smoke-test-local-001",
        "luogo": "Il Gufo · Roma",
        "note": "Smoke test e2e",
        "device": {
            "modello": "iPhone 11",
            "os": "iOS 17.4",
            "app_version": "0.1.0-smoke",
        },
        "registrazione": {
            "ts_inizio": inizio.isoformat(),
            "ts_fine": fine.isoformat(),
            "durata_sec": 900.0,
            "video_file": "video.mp4",
            "video_sha256": None,
            "video_dimensione_byte": 1024,
        },
        "godice": {
            "n_dadi_attaccante": 3,
            "n_dadi_difensore": 3,
            "ble_id_attaccante": ["AA:01", "AA:02", "AA:03"],
            "ble_id_difensore": ["BB:01", "BB:02", "BB:03"],
        },
        "eventi": {
            "n_eventi_totali": 6,
            "eventi_file": "eventi.jsonl",
        },
        "giocatori": [
            {"nome": "Edoardo", "colore": "rosso", "ordine_seduta": 1},
            {"nome": "Alice", "colore": "blu", "ordine_seduta": 2},
            {"nome": "Marco", "colore": "verde", "ordine_seduta": 3},
        ],
    }

    # Simula 6 lanci (una battaglia 3v3)
    eventi = []
    for i, (ble, ruolo, slot) in enumerate(
        [
            ("AA:01", "attaccante", 1),
            ("AA:02", "attaccante", 2),
            ("AA:03", "attaccante", 3),
            ("BB:01", "difensore", 1),
            ("BB:02", "difensore", 2),
            ("BB:03", "difensore", 3),
        ]
    ):
        ts = inizio + timedelta(minutes=5, seconds=i * 0.3)
        eventi.append(
            {
                "ts": ts.isoformat(),
                "tipo": "dado_lanciato",
                "ble_id": ble,
                "ruolo": ruolo,
                "slot": slot,
                "valore": ((i * 7) % 6) + 1,
            }
        )
    jsonl = "\n".join(json.dumps(e) for e in eventi) + "\n"

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
        zf.writestr("video.mp4", b"FAKE_MP4_CONTENT_FOR_SMOKE_TEST")
        zf.writestr("eventi.jsonl", jsonl)
    buffer.seek(0)
    return buffer.read()


def main() -> None:
    bundle = costruisci_bundle_realistico()
    print(f"Bundle costruito: {len(bundle)} byte")

    url = "http://localhost:8000/api/import/bundle-mobile"
    print(f"POST {url}")

    with httpx.Client(timeout=30.0) as client:
        risposta = client.post(
            url,
            files={"file": ("smoke.zip", bundle, "application/zip")},
        )

    print(f"Status: {risposta.status_code}")
    print(f"Body: {risposta.json()}")
    assert risposta.status_code == 201, "Smoke test fallito"
    print("✓ Smoke test OK")


if __name__ == "__main__":
    main()
