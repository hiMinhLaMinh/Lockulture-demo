"""Firebase Auth middleware: verify ID token → resolve actor UUID.

Mapping: auth_identities/{sha256(firebase_uid)} → user_id (UUID)
GET /me creates the mapping and profile atomically on first login.
"""
import hashlib
import json
import os
from datetime import datetime, timezone
from uuid import uuid4

from firebase_admin import auth as firebase_auth

from .firebase import get_db
from .social.core import ActorResolver, SocialError, digest, normalized, timestamp


def _uid_key(firebase_uid: str) -> str:
    return hashlib.sha256(firebase_uid.encode()).hexdigest()


def _gen_username(display_name: str, uid: str) -> str:
    """Generate a default username: normalized name + 4 hex chars."""
    base = normalized(display_name or "user").replace(" ", "")[:12] or "user"
    suffix = uid[:4]
    return f"{base}{suffix}"


class FirebaseActorResolver:
    """Verifies Firebase ID tokens and resolves to internal UUID."""

    def resolve(self, token: str) -> str | None:
        try:
            db = get_db()
            decoded = firebase_auth.verify_id_token(token, check_revoked=False)
            if not decoded.get("email_verified", False):
                return None
            firebase_uid = decoded["uid"]
            id_key = _uid_key(firebase_uid)
            snap = db.collection("auth_identities").document(id_key).get()
            if snap.exists:
                return snap.to_dict()["user_id"]
            return None  # /me will create it
        except Exception:
            return None

    def resolve_or_create(self, token: str) -> tuple[str, bool]:
        """Returns (user_id, created). Creates auth_identities + profile on first call."""
        db = get_db()
        try:
            decoded = firebase_auth.verify_id_token(token, check_revoked=False)
        except Exception as exc:
            raise SocialError(401, "Invalid or expired token") from exc
        if not decoded.get("email_verified", False):
            raise SocialError(401, "Email not verified")

        firebase_uid = decoded["uid"]
        email = decoded.get("email", "")
        display_name = decoded.get("name", "") or email.split("@")[0]

        id_key = _uid_key(firebase_uid)
        id_ref = db.collection("auth_identities").document(id_key)

        @db.transaction()
        def _run(tx):
            snap = id_ref.get(transaction=tx)
            if snap.exists:
                return snap.to_dict()["user_id"], False

            user_id = str(uuid4())
            username = _gen_username(display_name, user_id.replace("-", ""))

            # Ensure username uniqueness — append more chars if taken
            uname_ref = db.collection("usernames").document(username)
            uname_snap = uname_ref.get(transaction=tx)
            if uname_snap.exists:
                username = username + user_id.replace("-", "")[:4]

            now = datetime.now(timezone.utc)
            profile = {
                "schema_version": 1,
                "id": user_id,
                "display_name": display_name,
                "username": username,
                "bio": "",
                "xp_total": 0,
                "active_mission_id": None,
                "active_search_id": None,
                "created_at": now,
            }
            tx.set(id_ref, {"schema_version": 1, "user_id": user_id, "firebase_uid": firebase_uid})
            tx.set(db.collection("profiles").document(user_id), profile)
            tx.set(uname_ref, {"owner_id": user_id, "created_at": now})
            return user_id, True

        # Firestore transaction returns the value from the decorated function
        # but firebase-admin wraps it differently; call directly:
        return _create_or_get_identity(db, id_ref, firebase_uid, display_name)


def _create_or_get_identity(db, id_ref, firebase_uid: str, display_name: str) -> tuple[str, bool]:
    """Atomic get-or-create auth_identities + profile + username reservation."""
    @db.transaction()
    def run(transaction):
        snap = id_ref.get(transaction=transaction)
        if snap.exists:
            return snap.to_dict()["user_id"], False

        user_id = str(uuid4())
        username_base = normalized(display_name or "user").replace(" ", "")[:12] or "user"
        username = username_base + user_id.replace("-", "")[:4]

        uname_ref = db.collection("usernames").document(username)
        uname_snap = uname_ref.get(transaction=transaction)
        if uname_snap.exists:
            username = username_base + user_id.replace("-", "")[:8]

        now = datetime.now(timezone.utc)
        transaction.set(id_ref, {
            "schema_version": 1, "user_id": user_id, "firebase_uid": firebase_uid,
        })
        transaction.set(db.collection("profiles").document(user_id), {
            "schema_version": 1, "id": user_id,
            "display_name": display_name, "username": username,
            "bio": "", "xp_total": 0,
            "active_mission_id": None, "active_search_id": None,
            "created_at": now,
        })
        transaction.set(uname_ref, {"owner_id": user_id, "created_at": now})
        return user_id, True

    return run()
