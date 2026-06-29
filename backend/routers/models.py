from __future__ import annotations

from fastapi import APIRouter

from services.model_catalog import MODEL_CATALOG

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("")
def list_models() -> dict[str, list[str]]:
    """Selectable providers and their suggested models — consumed by the UI so it
    no longer hardcodes the catalog."""
    return MODEL_CATALOG
