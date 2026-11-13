"""Turn race alerts (push notifications) on and off for a device.

Auth, when enabled, is enforced by the /api middleware in main.py.
"""

import asyncio

from fastapi import APIRouter, Body, HTTPException

from services import push

router = APIRouter(prefix="/api/push", tags=["push"])


def _require_enabled() -> None:
    if not push.push_enabled():
        raise HTTPException(status_code=404, detail="Alertas desligados neste servidor")


@router.get("/key")
async def vapid_key():
    _require_enabled()
    return {"public_key": await asyncio.to_thread(push.public_key)}


@router.post("/subscribe")
async def subscribe(subscription: dict = Body(...)):
    _require_enabled()
    if not push.valid_subscription(subscription):
        raise HTTPException(status_code=400, detail="Inscrição inválida")
    await asyncio.to_thread(push.add_subscription, subscription)
    return {"ok": True}


@router.post("/unsubscribe")
async def unsubscribe(endpoint: str = Body(..., embed=True)):
    _require_enabled()
    await asyncio.to_thread(push.remove_subscription, endpoint)
    return {"ok": True}


@router.post("/status")
async def status(endpoint: str = Body(..., embed=True)):
    """Whether this device is still subscribed on the server."""
    _require_enabled()
    return {"subscribed": await asyncio.to_thread(push.has_subscription, endpoint)}


@router.post("/test")
async def test(endpoint: str = Body(..., embed=True)):
    _require_enabled()
    ok = await asyncio.to_thread(
        push.send_to, endpoint, "🏎️ Box Box", "Alertas ligados! Você vai receber a largada, Safety Car, bandeiras e o resultado.",
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Este aparelho não está inscrito")
    return {"ok": True}
