"""
Initializes the Firebase Admin SDK exactly once, giving the backend
privileged server-side access to Auth, Firestore, and the Realtime DB —
the same three services index.html was talking to directly before.
"""
import json

import firebase_admin
from firebase_admin import auth, credentials, db, firestore

from .config import get_settings

_settings = get_settings()
_app = None


def init_firebase():
    global _app
    if _app is not None:
        return _app

    if _settings.FIREBASE_CREDENTIALS_JSON:
        cred = credentials.Certificate(json.loads(_settings.FIREBASE_CREDENTIALS_JSON))
    elif _settings.FIREBASE_CREDENTIALS_PATH:
        cred = credentials.Certificate(_settings.FIREBASE_CREDENTIALS_PATH)
    else:
        raise RuntimeError(
            "No Firebase credentials configured. Set FIREBASE_CREDENTIALS_JSON "
            "or FIREBASE_CREDENTIALS_PATH in your environment."
        )

    _app = firebase_admin.initialize_app(
        cred,
        {"databaseURL": _settings.FIREBASE_DATABASE_URL} if _settings.FIREBASE_DATABASE_URL else None,
    )
    return _app


def get_firestore():
    init_firebase()
    return firestore.client()


def get_rtdb():
    init_firebase()
    return db


def get_auth():
    init_firebase()
    return auth
