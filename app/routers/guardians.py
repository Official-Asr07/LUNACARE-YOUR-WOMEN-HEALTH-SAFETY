"""
The Guardian feature: a LunaCare user invites a trusted contact (who must
have their own LunaCare account) to become a "guardian". The invite sits
pending until the guardian approves it — only after approval can that
guardian ever read the owner's live SOS location. Nothing is shared by
default; every access is an explicit, revocable grant stored in
Firestore (collection: guardian_links).
"""
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from firebase_admin import firestore as fa_firestore
from pydantic import BaseModel

from ..auth_dep import get_current_uid
from ..firebase_setup import get_auth, get_firestore, get_rtdb

router = APIRouter(prefix="/api/guardians", tags=["guardians"])


def _links():
    return get_firestore().collection("guardian_links")


# ── Owner invites a guardian by email ────────────────────────────────────
class InviteRequest(BaseModel):
    guardian_email: str
    owner_name: str | None = None


class GuardianCodeRequest(BaseModel):
    owner_name: str | None = None


class RedeemCodeRequest(BaseModel):
    code: str


class ApproveRequest(BaseModel):
    guardian_phone: str


@router.post("/invite")
async def invite_guardian(body: InviteRequest, uid: str = Depends(get_current_uid)):
    try:
        guardian_user = get_auth().get_user_by_email(body.guardian_email)
    except Exception:
        raise HTTPException(
            status_code=404,
            detail="No LunaCare account found with that email. Ask them to sign up first, then invite again.",
        )

    if guardian_user.uid == uid:
        raise HTTPException(status_code=400, detail="You can't add yourself as a guardian.")

    # Avoid duplicate pending/approved invites to the same guardian.
    existing = (
        _links()
        .where("ownerUid", "==", uid)
        .where("guardianUid", "==", guardian_user.uid)
        .get()
    )
    for doc in existing:
        status = doc.to_dict().get("status")
        if status in ("pending", "approved"):
            return {"ok": True, "status": status, "already_existed": True}

    doc_ref = _links().document()
    doc_ref.set(
        {
            "ownerUid": uid,
            "ownerName": body.owner_name or "",
            "guardianUid": guardian_user.uid,
            "guardianEmail": body.guardian_email,
            "status": "pending",
            "createdAt": fa_firestore.SERVER_TIMESTAMP,
        }
    )
    return {"ok": True, "status": "pending", "link_id": doc_ref.id}


@router.post("/invite-code")
async def create_guardian_code(
    body: GuardianCodeRequest, uid: str = Depends(get_current_uid)
):
    """Create a short-lived, one-time code the owner can send to a trusted person."""
    code = secrets.token_urlsafe(6).replace("-", "").replace("_", "").upper()[:8]
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    code_ref = _links().document(f"code_{hashlib.sha256(code.encode()).hexdigest()}")
    code_ref.set(
        {
            "type": "guardian_code",
            "ownerUid": uid,
            "ownerName": body.owner_name or "",
            "codeHash": hashlib.sha256(code.encode()).hexdigest(),
            "status": "unused",
            "expiresAt": expires_at,
            "createdAt": fa_firestore.SERVER_TIMESTAMP,
        }
    )
    return {"ok": True, "code": code, "expires_at": expires_at.isoformat()}


@router.post("/redeem-code")
async def redeem_guardian_code(
    body: RedeemCodeRequest, uid: str = Depends(get_current_uid)
):
    """Turn an owner-generated code into a pending guardian approval request."""
    normalized = body.code.strip().upper()
    if len(normalized) < 6:
        raise HTTPException(status_code=400, detail="Enter the complete guardian code.")

    code_hash = hashlib.sha256(normalized.encode()).hexdigest()
    code_ref = _links().document(f"code_{code_hash}")
    code_doc = code_ref.get()
    if not code_doc.exists:
        raise HTTPException(status_code=404, detail="Guardian code is invalid or expired.")

    code_data = code_doc.to_dict()
    if code_data.get("type") != "guardian_code" or code_data.get("status") != "unused":
        raise HTTPException(status_code=400, detail="Guardian code has already been used.")
    expires_at = code_data.get("expiresAt")
    if expires_at and expires_at < datetime.now(timezone.utc):
        code_ref.update({"status": "expired"})
        raise HTTPException(status_code=400, detail="Guardian code has expired. Ask the owner for a new code.")
    if code_data.get("ownerUid") == uid:
        raise HTTPException(status_code=400, detail="You cannot use your own guardian code.")

    existing = (
        _links()
        .where("ownerUid", "==", code_data["ownerUid"])
        .where("guardianUid", "==", uid)
        .get()
    )
    for doc in existing:
        status = doc.to_dict().get("status")
        if status in ("pending", "approved"):
            return {"ok": True, "status": status, "already_existed": True}

    guardian_user = get_auth().get_user(uid)
    link_ref = _links().document()
    link_ref.set(
        {
            "ownerUid": code_data["ownerUid"],
            "ownerName": code_data.get("ownerName", ""),
            "guardianUid": uid,
            "guardianEmail": guardian_user.email or "",
            "status": "pending",
            "source": "code",
            "createdAt": fa_firestore.SERVER_TIMESTAMP,
        }
    )
    code_ref.update(
        {
            "status": "used",
            "redeemedBy": uid,
            "redeemedAt": fa_firestore.SERVER_TIMESTAMP,
        }
    )
    return {"ok": True, "status": "pending", "link_id": link_ref.id}


# ── Owner: see who they've invited ───────────────────────────────────────
@router.get("/my-invites")
async def my_invites(uid: str = Depends(get_current_uid)):
    docs = _links().where("ownerUid", "==", uid).get()
    return [{"id": d.id, **d.to_dict()} for d in docs]


@router.delete("/{link_id}")
async def revoke_guardian(link_id: str, uid: str = Depends(get_current_uid)):
    doc_ref = _links().document(link_id)
    doc = doc_ref.get()
    if not doc.exists or doc.to_dict().get("ownerUid") != uid:
        raise HTTPException(status_code=404, detail="Guardian link not found.")
    doc_ref.update({"status": "revoked", "revokedAt": fa_firestore.SERVER_TIMESTAMP})
    return {"ok": True, "status": "revoked"}


# ── Guardian: see pending invites addressed to them ──────────────────────
@router.get("/pending")
async def pending_invites(uid: str = Depends(get_current_uid)):
    docs = _links().where("guardianUid", "==", uid).where("status", "==", "pending").get()
    return [{"id": d.id, **d.to_dict()} for d in docs]


# ── Guardian: approve or deny an invite ──────────────────────────────────
@router.post("/{link_id}/approve")
async def approve_invite(
    link_id: str,
    body: ApproveRequest,
    uid: str = Depends(get_current_uid),
):
    phone = body.guardian_phone.strip()
    if len("".join(filter(str.isdigit, phone))) < 7:
        raise HTTPException(status_code=400, detail="Enter a valid guardian phone number.")
    doc_ref = _links().document(link_id)
    doc = doc_ref.get()
    if not doc.exists or doc.to_dict().get("guardianUid") != uid:
        raise HTTPException(status_code=404, detail="Invite not found.")
    doc_ref.update(
        {
            "status": "approved",
            "guardianPhone": phone,
            "approvedAt": fa_firestore.SERVER_TIMESTAMP,
        }
    )
    return {"ok": True, "status": "approved"}


@router.post("/{link_id}/deny")
async def deny_invite(link_id: str, uid: str = Depends(get_current_uid)):
    doc_ref = _links().document(link_id)
    doc = doc_ref.get()
    if not doc.exists or doc.to_dict().get("guardianUid") != uid:
        raise HTTPException(status_code=404, detail="Invite not found.")
    doc_ref.update({"status": "denied"})
    return {"ok": True, "status": "denied"}


# ── Guardian: list the people who approved them (their "wards") ─────────
@router.get("/my-wards")
async def my_wards(uid: str = Depends(get_current_uid)):
    docs = _links().where("guardianUid", "==", uid).where("status", "==", "approved").get()
    return [{"link_id": d.id, "ownerUid": d.to_dict().get("ownerUid"), "ownerName": d.to_dict().get("ownerName")} for d in docs]


# ── Guardian: read a ward's most recent live location + AI report ───────
@router.get("/live/{owner_uid}")
async def live_location(owner_uid: str, uid: str = Depends(get_current_uid)):
    approved = (
        _links()
        .where("ownerUid", "==", owner_uid)
        .where("guardianUid", "==", uid)
        .where("status", "==", "approved")
        .limit(1)
        .get()
    )
    if not approved:
        raise HTTPException(status_code=403, detail="You are not an approved guardian for this person.")

    rtdb = get_rtdb()
    logs_ref = rtdb.reference(f"emergency_logs/{owner_uid}")

    latest_location: dict[str, Any] = {}
    recent = logs_ref.order_by_key().limit_to_last(5).get() or {}
    for key, value in recent.items():
        if isinstance(value, dict) and "lat" in value:
            latest_location = value  # last one in insertion order wins (most recent)

    situational = logs_ref.child("situational_analysis").get() or {}

    return {"location": latest_location, "situational_analysis": situational}
