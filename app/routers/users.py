"""
Replaces: _saveUserProfileToFirestore(), _saveMoodToFirestore(),
_saveJournalToFirestore(), _loadCloudDataToLocal() (~line 6620-6708) in
index.html. Same Firestore paths (users/{uid}, .../moods, .../journals) —
now written by the server after verifying the caller's ID token, instead
of the browser writing with open Firestore security rules.
"""
from typing import Any

from fastapi import APIRouter, Depends
from firebase_admin import firestore as fa_firestore
from pydantic import BaseModel

from ..auth_dep import get_current_uid
from ..firebase_setup import get_firestore

router = APIRouter(prefix="/api/users", tags=["users"])


# ── Profile ──────────────────────────────────────────────────────────────
class ProfileUpdate(BaseModel):
    data: dict[str, Any]


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
