"""
Replaces: _pushLocationToFirebase() (~line 5209) and
_pushSitReportToFirebase() (~line 5114) in index.html.

Same Realtime DB path (emergency_logs/{uid}) as before. Works for signed-in
users (verified uid) and anonymous ones (device id), matching the original
"web_anonymous_<deviceId>" fallback — but now the server sets the uid used
for the write instead of trusting whatever the browser sends.
"""
import time
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..auth_dep import get_optional_uid
from ..firebase_setup import get_rtdb

router = APIRouter(prefix="/api/emergency", tags=["emergency"])


def _resolve_uid(uid: str | None, device_id: str) -> str:
    return uid or f"web_anonymous_{device_id}"


# ── Live location telemetry ──────────────────────────────────────────────
class LocationPush(BaseModel):
    device_id: str
    location_data: dict[str, Any]  # lat, lng, speed, accuracy, sosTriggered, ...


@router.post("/location")
async def push_location(body: LocationPush, uid: str | None = Depends(get_optional_uid)):
    resolved_uid = _resolve_uid(uid, body.device_id)
    payload = {
        **body.location_data,
        "serverTimestamp": {".sv": "timestamp"},  # Realtime DB server-timestamp placeholder
        "deviceTimestamp": int(time.time() * 1000),
        "appVersion": "LunaCareBackendV1",
    }
    ref = get_rtdb().reference(f"emergency_logs/{resolved_uid}")
    ref.push(payload)
    return {"ok": True, "uid": resolved_uid}


# ── AI situational report (paired with /api/aviro/situational-analysis) ─
class SituationalReportPush(BaseModel):
    device_id: str
    ai_report: str
    transcript: str | None = None


@router.post("/situational-report")
async def push_situational_report(body: SituationalReportPush, uid: str | None = Depends(get_optional_uid)):
    resolved_uid = _resolve_uid(uid, body.device_id)
    payload = {
        "type": "AI_SITUATIONAL_REPORT",
        "aiReport": body.ai_report,
        "transcript": body.transcript,
        "serverTimestamp": {".sv": "timestamp"},
        "deviceTimestamp": int(time.time() * 1000),
        "appVersion": "LunaCareBackendV1",
    }
    ref = get_rtdb().reference(f"emergency_logs/{resolved_uid}/situational_analysis")
    ref.set(payload)
    return {"ok": True, "uid": resolved_uid}
