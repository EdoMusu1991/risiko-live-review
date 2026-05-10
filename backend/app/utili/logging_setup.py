"""
Setup logging strutturato JSON per il backend.

Produce log line per line in formato JSON con campi:
- ts: ISO 8601 UTC
- level: debug/info/warning/error/critical
- logger: nome del modulo
- msg: messaggio
- request_id: se disponibile (settato dal middleware)
- extra: campi addizionali passati con `extra=`

Vantaggi vs format human-readable: parseabile da Loki/Datadog/CloudWatch
senza regex, query strutturate (`level=error AND request_id=xyz`).

Uso:

    from app.utili.logging_setup import configura_logging, ottieni_logger
    configura_logging(level="INFO")
    log = ottieni_logger(__name__)
    log.info("evento", extra={"chiave": "valore"})
"""
from __future__ import annotations

import contextvars
import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any, ClassVar

# context var per propagare request_id senza passarlo esplicitamente
_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)


def imposta_request_id(value: str | None) -> contextvars.Token[str | None]:
    """Imposta il request_id nella context corrente. Ritorna token per reset."""
    return _request_id.set(value)


def ottieni_request_id() -> str | None:
    return _request_id.get()


def reset_request_id(token: contextvars.Token[str | None]) -> None:
    _request_id.reset(token)


class JsonFormatter(logging.Formatter):
    """Formatter che serializza ogni record come JSON line."""

    # campi standard di LogRecord da non mettere in `extra`
    _RESERVED: ClassVar[set[str]] = {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "taskName",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "msg": record.getMessage(),
        }
        rid = ottieni_request_id()
        if rid is not None:
            payload["request_id"] = rid

        # campi extra: tutto quello in record.__dict__ non riservato
        for k, v in record.__dict__.items():
            if k in self._RESERVED or k.startswith("_"):
                continue
            if k in payload:
                continue
            try:
                json.dumps(v)  # check serializzabile
                payload[k] = v
            except (TypeError, ValueError):
                payload[k] = repr(v)

        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configura_logging(level: str = "INFO", stream: Any = None) -> None:
    """
    Configura il root logger per usare il formatter JSON.

    Idempotente: chiamate ripetute rimuovono i vecchi handler.

    `stream`: default sys.stdout. Test possono passare StringIO per catturare.
    """
    if stream is None:
        stream = sys.stdout

    root = logging.getLogger()
    # rimuovi handler precedenti per evitare duplicati
    for h in list(root.handlers):
        root.removeHandler(h)

    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level.upper())


def ottieni_logger(name: str) -> logging.Logger:
    """Ottiene un logger dedicato per il modulo."""
    return logging.getLogger(name)
