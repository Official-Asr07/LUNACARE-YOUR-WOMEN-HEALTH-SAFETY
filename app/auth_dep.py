"""
Replaces the old `firebase.auth().currentUser.uid` pattern from index.html.

The frontend still uses Firebase Auth client SDK to sign users in (phone,
email/password, email link) — that part doesn't need to move server-side.
What changes is: after signing in, the frontend sends the user's Firebase
ID token with every API call, and THIS backend verifies it before trusting
any uid. The browser can no longer just claim "I am uid X".
"""
from fastapi import Header, HTTPException, status

from .firebase_setup import get_auth


async def get_current_uid(authorization: str = Header(default="")) -> str:
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header. Expected: Bearer <Firebase ID token>",
        )
    id_token = authorization.removeprefix("Bearer ").strip()
    try:
        decoded = get_auth().verify_id_token(id_token)
    except Exception as exc:  # noqa: BLE001 — surfacing to client as 401 is intentional
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired ID token: {exc}",
        ) from exc
    return decoded["uid"]


async def get_optional_uid(authorization: str = Header(default="")) -> str | None:
    """For endpoints (like anonymous SOS telemetry) that work for signed-out users too."""
    if not authorization.startswith("Bearer "):
        return None
    try:
        decoded = get_auth().verify_id_token(authorization.removeprefix("Bearer ").strip())
        return decoded["uid"]
    except Exception:  # noqa: BLE001
        return None
