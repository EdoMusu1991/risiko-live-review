"""Endpoint API organizzati per dominio."""

from app.routers import (
    esportazione,
    eventi,
    import_bundle,
    partite,
    ricostruzione,
    risorse,
    video,
)

__all__ = [
    "esportazione",
    "eventi",
    "import_bundle",
    "partite",
    "ricostruzione",
    "risorse",
    "video",
]
