"""Test per gli endpoint diagnostici."""
from __future__ import annotations

import os
import time

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class TestHealth:
    def test_health_ritorna_200_e_status_ok(self, client: TestClient):
        r = client.get("/api/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert "timestamp" in body
        assert isinstance(body["uptime_sec"], (int, float))
        assert body["uptime_sec"] >= 0

    def test_health_uptime_aumenta(self, client: TestClient):
        r1 = client.get("/api/health").json()
        time.sleep(0.05)
        r2 = client.get("/api/health").json()
        assert r2["uptime_sec"] > r1["uptime_sec"]

    def test_health_timestamp_iso8601(self, client: TestClient):
        body = client.get("/api/health").json()
        # ISO 8601 con timezone
        from datetime import datetime
        parsed = datetime.fromisoformat(body["timestamp"])
        assert parsed.tzinfo is not None


class TestVersion:
    def test_version_default(self, client: TestClient, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("APP_VERSION", raising=False)
        monkeypatch.delenv("APP_COMMIT", raising=False)
        r = client.get("/api/version")
        assert r.status_code == 200
        body = r.json()
        assert body["version"] == "dev"
        assert body["commit"] is None
        assert body["python"].count(".") == 2
        assert isinstance(body["fastapi"], str)

    def test_version_da_env(self, client: TestClient, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("APP_VERSION", "1.2.3")
        monkeypatch.setenv("APP_COMMIT", "abc1234")
        body = client.get("/api/version").json()
        assert body["version"] == "1.2.3"
        assert body["commit"] == "abc1234"

    def test_version_commit_vuoto_diventa_none(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("APP_COMMIT", "")
        body = client.get("/api/version").json()
        assert body["commit"] is None
