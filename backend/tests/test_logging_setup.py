"""Test per logging_setup: JsonFormatter + context var request_id."""
from __future__ import annotations

import io
import json
import logging

import pytest

from app.utili.logging_setup import (
    JsonFormatter,
    configura_logging,
    imposta_request_id,
    ottieni_logger,
    ottieni_request_id,
    reset_request_id,
)


@pytest.fixture
def stream() -> io.StringIO:
    return io.StringIO()


@pytest.fixture(autouse=True)
def reset_root_logger():
    """Pulisce il root logger dopo ogni test."""
    yield
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    root.setLevel(logging.WARNING)


def parse_log_lines(testo: str) -> list[dict]:
    return [json.loads(l) for l in testo.strip().split("\n") if l.strip()]


class TestJsonFormatter:
    def test_struttura_base_di_un_log(self, stream: io.StringIO):
        configura_logging(level="DEBUG", stream=stream)
        log = ottieni_logger("test")
        log.info("hello world")
        righe = parse_log_lines(stream.getvalue())
        assert len(righe) == 1
        r = righe[0]
        assert r["level"] == "info"
        assert r["logger"] == "test"
        assert r["msg"] == "hello world"
        assert "ts" in r
        assert r["ts"].endswith("+00:00")  # UTC

    def test_extra_inclusi(self, stream: io.StringIO):
        configura_logging(level="DEBUG", stream=stream)
        log = ottieni_logger("test")
        log.warning("evento", extra={"chiave": "valore", "n": 42})
        r = parse_log_lines(stream.getvalue())[0]
        assert r["chiave"] == "valore"
        assert r["n"] == 42

    def test_request_id_assente_se_non_settato(self, stream: io.StringIO):
        configura_logging(stream=stream)
        ottieni_logger("test").info("msg")
        r = parse_log_lines(stream.getvalue())[0]
        assert "request_id" not in r

    def test_request_id_presente_se_settato(self, stream: io.StringIO):
        configura_logging(stream=stream)
        token = imposta_request_id("abc-123")
        try:
            ottieni_logger("test").info("msg")
        finally:
            reset_request_id(token)
        r = parse_log_lines(stream.getvalue())[0]
        assert r["request_id"] == "abc-123"

    def test_eccezione_serializzata(self, stream: io.StringIO):
        configura_logging(stream=stream)
        log = ottieni_logger("test")
        try:
            raise ValueError("kaboom")
        except ValueError:
            log.exception("errore catturato")
        r = parse_log_lines(stream.getvalue())[0]
        assert r["level"] == "error"
        assert "exc" in r
        assert "ValueError" in r["exc"]
        assert "kaboom" in r["exc"]

    def test_extra_non_serializzabile_diventa_repr(self):
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="x", lineno=1,
            msg="m", args=(), exc_info=None,
        )
        # oggetto non JSON-serializzabile
        class Custom:
            def __repr__(self):
                return "<Custom>"

        record.oggetto = Custom()  # type: ignore[attr-defined]
        out = formatter.format(record)
        parsed = json.loads(out)
        assert parsed["oggetto"] == "<Custom>"

    def test_livelli_minuscoli(self, stream: io.StringIO):
        configura_logging(level="DEBUG", stream=stream)
        log = ottieni_logger("test")
        log.debug("d")
        log.info("i")
        log.warning("w")
        log.error("e")
        livelli = [r["level"] for r in parse_log_lines(stream.getvalue())]
        assert livelli == ["debug", "info", "warning", "error"]

    def test_livello_filtra_inferiori(self, stream: io.StringIO):
        configura_logging(level="WARNING", stream=stream)
        log = ottieni_logger("test")
        log.debug("non vista")
        log.info("non vista")
        log.warning("vista")
        log.error("vista")
        righe = parse_log_lines(stream.getvalue())
        assert len(righe) == 2
        assert all(r["level"] in ("warning", "error") for r in righe)

    def test_caratteri_unicode_preservati(self, stream: io.StringIO):
        configura_logging(stream=stream)
        ottieni_logger("test").info("àèìòù — emoji 🎲")
        r = parse_log_lines(stream.getvalue())[0]
        assert "àèìòù" in r["msg"]
        assert "🎲" in r["msg"]


class TestRequestIdContext:
    def test_default_e_None(self):
        assert ottieni_request_id() is None

    def test_set_e_get(self):
        token = imposta_request_id("xyz")
        try:
            assert ottieni_request_id() == "xyz"
        finally:
            reset_request_id(token)
        assert ottieni_request_id() is None

    def test_isolamento_dopo_reset(self):
        t1 = imposta_request_id("uno")
        assert ottieni_request_id() == "uno"
        t2 = imposta_request_id("due")
        assert ottieni_request_id() == "due"
        reset_request_id(t2)
        assert ottieni_request_id() == "uno"
        reset_request_id(t1)
        assert ottieni_request_id() is None


class TestConfiguraLogging:
    def test_idempotente_non_duplica_handler(self, stream: io.StringIO):
        configura_logging(stream=stream)
        configura_logging(stream=stream)
        configura_logging(stream=stream)
        ottieni_logger("test").info("msg")
        # nonostante 3 configura, dovrebbe esserci 1 sola riga di output
        righe = parse_log_lines(stream.getvalue())
        assert len(righe) == 1

    def test_default_su_stdout_se_stream_none(self):
        # non testabile direttamente senza catturare stdout, ma verifichiamo
        # che non sollevi
        configura_logging()
