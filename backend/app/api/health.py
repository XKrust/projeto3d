"""Endpoint de health check - usado pelo frontend para saber se o backend esta de pe."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}
