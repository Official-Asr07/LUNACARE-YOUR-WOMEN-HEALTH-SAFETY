"""
Replaces: _saveUserProfileToFirestore(), _saveMoodToFirestore(),
_saveJournalToFirestore(), _loadCloudDataToLocal() (~line 6620-6708) in
index.html. Same Firestore paths (users/{uid}, .../moods, .../journals) —
now written by the server after verifying the caller's ID token, instead
of the browser writing with open Firestore security rules.
"""
from typing import Any
import hashlib
import hmac
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException
from firebase_admin import firestore as fa_firestore
from pydantic import BaseModel

from ..auth_dep import get_current_uid
from ..firebase_setup import get_firestore
from ..config import get_settings
import httpx

router = APIRouter(prefix="/api/users", tags=["users"])


# ── Profile ──────────────────────────────────────────────────────────────
class ProfileUpdate(BaseModel):
    data: dict[str, Any]


class ContactsUpdate(BaseModel):
    contacts: list[dict[str, Any]]


class PinUpdate(BaseModel):
    pin: str


class PinVerify(BaseModel):
    pin: str


@router.put("/me")
async def update_profile(body: ProfileUpdate, uid: str = Depends(get_current_uid)):
    db = get_firestore()
    db.collection("users").document(uid).set(
        {"uid": uid, "updatedAt": fa_firestore.SERVER_TIMESTAMP, **body.data},
        merge=True,
    )
    return {"ok": True}


@router.get("/me")
async def get_profile(uid: str = Depends(get_current_uid)):
    doc = get_firestore().collection("users").document(uid).get()
    return doc.to_dict() if doc.exists else {}


@router.put("/me/security-pin")
async def set_security_pin(body: PinUpdate, uid: str = Depends(get_current_uid)):
    if not body.pin.isdigit() or len(body.pin) < 4 or len(body.pin) > 12:
        raise HTTPException(status_code=400, detail="PIN must contain 4 to 12 digits.")
    salt = secrets.token_hex(16)
    pin_hash = hashlib.pbkdf2_hmac("sha256", body.pin.encode(), salt.encode(), 120_000).hex()
    get_firestore().collection("users").document(uid).set(
        {"securityPinHash": pin_hash, "securityPinSalt": salt, "securityPinLength": len(body.pin)},
        merge=True,
    )
    return {"ok": True, "configured": True}


@router.post("/me/security-pin/verify")
async def verify_security_pin(body: PinVerify, uid: str = Depends(get_current_uid)):
    doc = get_firestore().collection("users").document(uid).get()
    data = doc.to_dict() if doc.exists else {}
    salt = data.get("securityPinSalt")
    expected = data.get("securityPinHash")
    if not salt or not expected or not body.pin.isdigit() or len(body.pin) < 4:
        return {"ok": True, "valid": False}
    actual = hashlib.pbkdf2_hmac(
        "sha256", body.pin.encode(), salt.encode(), 120_000
    ).hex()
    return {"ok": True, "valid": hmac.compare_digest(actual, expected)}


@router.put("/me/sos-contacts")
async def replace_sos_contacts(body: ContactsUpdate, uid: str = Depends(get_current_uid)):
    if len(body.contacts) > 50:
        raise HTTPException(status_code=400, detail="You can add up to 50 SOS contacts.")
    cleaned = [
        {"name": str(c.get("name", "")).strip(), "phone": str(c.get("phone", "")).strip()}
        for c in body.contacts
        if str(c.get("name", "")).strip() and str(c.get("phone", "")).strip()
    ]
    get_firestore().collection("users").document(uid).set(
        {"sosContacts": cleaned}, merge=True
    )
    return {"ok": True, "contacts": cleaned}


@router.get("/me/sos-contacts")
async def get_sos_contacts(uid: str = Depends(get_current_uid)):
    doc = get_firestore().collection("users").document(uid).get()
    return doc.to_dict().get("sosContacts", []) if doc.exists else []


@router.get("/cron/monthly-summary")
async def monthly_summary(
    authorization: str = Header(default=""),
):
    settings = get_settings()
    cron_secret = authorization.removeprefix("Bearer ").strip()
    if not settings.MONTHLY_SUMMARY_CRON_SECRET or not hmac.compare_digest(
        cron_secret, settings.MONTHLY_SUMMARY_CRON_SECRET
    ):
        raise HTTPException(status_code=401, detail="Invalid cron secret.")
    if not settings.RESEND_API_KEY:
        raise HTTPException(status_code=503, detail="RESEND_API_KEY is not configured.")

    sent = 0
    for doc in get_firestore().collection("users").stream():
        data = doc.to_dict()
        email = data.get("email") or data.get("contact")
        if not email or "@" not in str(email):
            continue
        contacts = data.get("sosContacts", [])
        body = (
            "<h2>Your LunaCare monthly safety review</h2>"
            "<p>Review your trusted contacts and Guardian access in LunaCare. "
            "Remove anyone you no longer trust and confirm every phone number is current.</p>"
            f"<p><strong>SOS contacts saved:</strong> {len(contacts)}</p>"
            "<p>This email does not include live location or health journal contents.</p>"
        )
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
                json={
                    "from": settings.RESEND_FROM_EMAIL,
                    "to": [email],
                    "subject": "LunaCare monthly safety review",
                    "html": body,
                },
            )
        response.raise_for_status()
        sent += 1
    return {"ok": True, "sent": sent}


# ── Moods ────────────────────────────────────────────────────────────────
class MoodEntry(BaseModel):
    data: dict[str, Any]


@router.post("/me/moods")
async def add_mood(body: MoodEntry, uid: str = Depends(get_current_uid)):
    db = get_firestore()
    db.collection("users").document(uid).collection("moods").add(
        {**body.data, "serverTimestamp": fa_firestore.SERVER_TIMESTAMP}
    )
    return {"ok": True}


@router.get("/me/moods")
async def list_moods(uid: str = Depends(get_current_uid), limit: int = 200):
    db = get_firestore()
    snap = (
        db.collection("users")
        .document(uid)
        .collection("moods")
        .order_by("serverTimestamp", direction=fa_firestore.Query.DESCENDING)
        .limit(limit)
        .get()
    )
    return [d.to_dict() for d in snap]


# ── Journals ─────────────────────────────────────────────────────────────
class JournalEntry(BaseModel):
    data: dict[str, Any]


@router.post("/me/journals")
async def add_journal(body: JournalEntry, uid: str = Depends(get_current_uid)):
    db = get_firestore()
    db.collection("users").document(uid).collection("journals").add(
        {**body.data, "serverTimestamp": fa_firestore.SERVER_TIMESTAMP}
    )
    return {"ok": True}


@router.get("/me/journals")
async def list_journals(uid: str = Depends(get_current_uid), limit: int = 365):
    db = get_firestore()
    snap = (
        db.collection("users")
        .document(uid)
        .collection("journals")
        .order_by("serverTimestamp", direction=fa_firestore.Query.DESCENDING)
        .limit(limit)
        .get()
    )
    return [d.to_dict() for d in snap]
