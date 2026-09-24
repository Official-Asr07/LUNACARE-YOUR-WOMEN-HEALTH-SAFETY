"""
The Guardian feature: a LunaCare user invites a trusted contact (who must
have their own LunaCare account) to become a "guardian". The invite sits
pending until the guardian approves it — only after approval can that
guardian ever read the owner's live SOS location. Nothing is shared by
default; every access is an explicit, revocable grant stored in
Firestore (collection: guardian_links).
"""
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


# ── Owner: see who they've invited ───────────────────────────────────────
@router.get("/my-invites")
async def my_invites(uid: str = Depends(get_current_uid)):
    docs = _links().where("ownerUid", "==", uid).get()
    return [{"id": d.id, **d.to_dict()} for d in docs]


# ── Guardian: see pending invites addressed to them ──────────────────────
@router.get("/pending")
async def pending_invites(uid: str = Depends(get_current_uid)):
    docs = _links().where("guardianUid", "==", uid).where("status", "==", "pending").get()
    return [{"id": d.id, **d.to_dict()} for d in docs]


# ── Guardian: approve or deny an invite ──────────────────────────────────
@router.post("/{link_id}/approve")
async def approve_invite(link_id: str, uid: str = Depends(get_current_uid)):
    doc_ref = _links().document(link_id)
    doc = doc_ref.get()
    if not doc.exists or doc.to_dict().get("guardianUid") != uid:
        raise HTTPException(status_code=404, detail="Invite not found.")
    doc_ref.update({"status": "approved", "approvedAt": fa_firestore.SERVER_TIMESTAMP})
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
