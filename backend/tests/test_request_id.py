"""Test middleware RequestIdMiddleware via TestClient."""
from __future__ import annotations

import io
import json
import logging
import re

import pytest
from fastapi.testclient import TestClient

from app.utili.logging_setup import configura_logging


@pytest.fixture(autouse=True)
def reset_root_logger():
    yield
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    root.setLevel(logging.WARNING)


@pytest.fixture
def app_e_stream():
    """Crea l'app con logging configurato su uno stream catturabile."""
    stream = io.StringIO()
    configura_logging(level="DEBUG", stream=stream)
    # importiamo dopo aver configurato il logging
    from app.main import app
    return app, stream


def parse_log_lines(testo: str) -> list[dict]:
    return [json.loads(l) for l in testo.strip().split("\n") if l.strip()]


class TestRequestIdHeaderResponse:
    def test_response_include_X_Request_ID(self, app_e_stream):
        app, _ = app_e_stream
        client = TestClient(app)
        r = client.get("/api/health")
        assert "X-Request-ID" in r.headers
        rid = r.headers["X-Request-ID"]
        # UUID v4 format
        assert re.match(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
            rid,
        )

    def test_request_id_da_header_riusato(self, app_e_stream):
        app, _ = app_e_stream
        client = TestClient(app)
        r = client.get(
            "/api/health",
            headers={"X-Request-ID": "client-fornito-id"},
        )
        assert r.headers["X-Request-ID"] == "client-fornito-id"

    def test_richieste_diverse_id_diversi(self, app_e_stream):
        app, _ = app_e_stream
        client = TestClient(app)
        r1 = client.get("/api/health")
        r2 = client.get("/api/health")
        assert r1.headers["X-Request-ID"] != r2.headers["X-Request-ID"]


class TestLoggingPerRichiesta:
    def test_log_inizio_e_fine_richiesta(self, app_e_stream):
        app, stream = app_e_stream
        client = TestClient(app)
        client.get("/api/health")
        righe = parse_log_lines(stream.getvalue())
        # almeno 2 messaggi: "request inizio" e "request fine"
        msg = [r["msg"] for r in righe]
        assert "request inizio" in msg
        assert "request fine" in msg

    def test_request_id_propagato_nei_log(self, app_e_stream):
        app, stream = app_e_stream
        client = TestClient(app)
        r = client.get(
            "/api/health",
            headers={"X-Request-ID": "test-id-fisso"},
        )
        assert r.status_code == 200
        righe = parse_log_lines(stream.getvalue())
        # tutti i log della richiesta dovrebbero avere lo stesso request_id
        rid_logs = [
            r for r in righe if r.get("request_id") == "test-id-fisso"
        ]
        assert len(rid_logs) >= 2  # inizio + fine

    def test_log_include_path_e_status(self, app_e_stream):
        app, stream = app_e_stream
        client = TestClient(app)
        client.get("/api/health")
        righe = parse_log_lines(stream.getvalue())
        log_fine = next(r for r in righe if r["msg"] == "request fine")
        assert log_fine["path"] == "/api/health"
        assert log_fine["status"] == 200
        assert log_fine["method"] == "GET"
