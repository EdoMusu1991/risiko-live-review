"""
Test ErrorHandlerMiddleware + CORS.

Per testare ErrorHandlerMiddleware servono route che lanciano eccezioni
non-HTTP. Aggiungiamo un router di test temporaneo.
"""
from __future__ import annotations

import io
import json
import logging

import pytest
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.middleware.error_handler import registra_exception_handlers
from app.middleware.request_id import RequestIdMiddleware
from app.utili.logging_setup import configura_logging


@pytest.fixture(autouse=True)
def reset_root_logger():
    yield
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    root.setLevel(logging.WARNING)


@pytest.fixture
def app_test():
    """App FastAPI minimale con solo i middleware da testare + route di test."""
    stream = io.StringIO()
    configura_logging(level="DEBUG", stream=stream)

    a = FastAPI()
    a.add_middleware(RequestIdMiddleware)
    registra_exception_handlers(a)

    test_router = APIRouter()

    @test_router.get("/boom")
    def boom():
        raise RuntimeError("kaboom")

    @test_router.get("/zero-div")
    def zero_div():
        return 1 / 0  # ZeroDivisionError

    @test_router.get("/http-exc")
    def http_exc():
        raise HTTPException(status_code=404, detail="not found")

    @test_router.get("/ok")
    def ok():
        return {"ok": True}

    a.include_router(test_router)
    return a, stream


def parse_log_lines(testo: str) -> list[dict]:
    return [json.loads(l) for l in testo.strip().split("\n") if l.strip()]


class TestErrorHandlerMiddleware:
    def test_runtime_error_diventa_500_json(self, app_test):
        app, _ = app_test
        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/boom")
        assert r.status_code == 500
        body = r.json()
        assert body["errore"] == "errore interno del server"
        assert body["tipo"] == "RuntimeError"
        assert body["request_id"] is not None

    def test_zero_div_500_json(self, app_test):
        app, _ = app_test
        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/zero-div")
        assert r.status_code == 500
        assert r.json()["tipo"] == "ZeroDivisionError"

    def test_http_exception_NON_catturata(self, app_test):
        """HTTPException ha il suo gestore standard FastAPI: 404 con detail."""
        app, _ = app_test
        client = TestClient(app)
        r = client.get("/http-exc")
        assert r.status_code == 404
        assert r.json() == {"detail": "not found"}

    def test_route_ok_passa(self, app_test):
        app, _ = app_test
        client = TestClient(app)
        r = client.get("/ok")
        assert r.status_code == 200
        assert r.json() == {"ok": True}

    def test_log_traceback_emesso_per_500(self, app_test):
        app, stream = app_test
        client = TestClient(app, raise_server_exceptions=False)
        client.get("/boom")
        righe = parse_log_lines(stream.getvalue())
        log_errore = [r for r in righe if r["msg"] == "errore non gestito"]
        assert len(log_errore) == 1
        assert "exc" in log_errore[0]
        assert "RuntimeError" in log_errore[0]["exc"]
        assert "kaboom" in log_errore[0]["exc"]

    def test_request_id_in_response_500(self, app_test):
        app, _ = app_test
        client = TestClient(app, raise_server_exceptions=False)
        r = client.get(
            "/boom",
            headers={"X-Request-ID": "rid-fisso-test"},
        )
        assert r.json()["request_id"] == "rid-fisso-test"
        # anche header
        assert r.headers["X-Request-ID"] == "rid-fisso-test"


class TestCORS:
    """Test che CORSMiddleware è configurato sulla app reale."""

    def test_options_preflight_ritorna_headers_cors(self):
        from app.main import app
        client = TestClient(app)
        r = client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        # CORSMiddleware risponde 200 al preflight
        assert r.status_code == 200
        assert "access-control-allow-origin" in (k.lower() for k in r.headers.keys())

    def test_response_normale_ha_access_control_allow_origin(self):
        from app.main import app
        client = TestClient(app)
        r = client.get(
            "/api/health",
            headers={"Origin": "http://localhost:5173"},
        )
        assert r.status_code == 200
        # con allow_origins specifici, header presente solo per origin in lista
        assert "access-control-allow-origin" in (k.lower() for k in r.headers.keys())

    def test_x_request_id_esposto_via_cors(self):
        """expose_headers=['X-Request-ID'] per consentire al client JS di leggerlo."""
        from app.main import app
        client = TestClient(app)
        r = client.get(
            "/api/health",
            headers={"Origin": "http://localhost:5173"},
        )
        expose = r.headers.get("access-control-expose-headers", "")
        assert "X-Request-ID" in expose
