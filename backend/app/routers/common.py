from __future__ import annotations

from ..core.cache import Envelope
from ..core.errors import AppError

DEMO_USER = "demo"


def ok(env: Envelope) -> dict:
    return {"data": env.data, "meta": env.meta()}


def err(e: AppError) -> dict:
    return {"error": {"code": e.code, "message": e.message}}


async def section(coro) -> dict:
    """Run a data fetch and return either {data, meta} or {error} so one failing
    provider doesn't break the whole page."""
    try:
        return ok(await coro)
    except AppError as e:
        return err(e)
