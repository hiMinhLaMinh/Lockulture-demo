"""Firestore-backed implementations of SocialRepository, DiscoveryReader, AssetUrlIssuer.

Key design notes (from DATA_TRANSACTIONS.md):
- All reads before writes in Firestore transactions.
- Callbacks may be re-run on contention; must not call AI/Maps/Storage/Tasks inside.
- Buffer writes so reads in callback precede commit.
- atomic() uses db.transaction() with retry; raises SocialError(503) on exhaustion.
"""
import datetime
import json
from typing import Callable, TypeVar

from google.cloud import firestore as fs
from google.cloud.storage import Blob

from .firebase import get_db, get_storage_bucket
from .social.core import (
    ActorResolver, AssetUrlIssuer, DiscoveryReader,
    SocialError, SocialRepository, SocialTransaction,
    digest, now, timestamp,
)

T = TypeVar("T")

# ---------------------------------------------------------------------------
# Firestore transaction adapter
# ---------------------------------------------------------------------------

class _FirestoreTx:
    """Wraps a Firestore transaction as a SocialTransaction.

    Reads go through the transaction for consistency.
    Writes are buffered and applied at commit via the transaction object.
    """
    def __init__(self, db: fs.Client, tx: fs.Transaction):
        self._db = db
        self._tx = tx
        self._pending_puts: list = []
        self._pending_deletes: list = []
        self._cache: dict = {}

    @staticmethod
    def _collection_name(collection: str) -> str:
        return {
            "users": "profiles",
            "pairs": "friend_pairs",
            "requests": "friend_requests",
            "published": "published_discoveries",
            "idempotency": "idempotency_keys",
        }.get(collection, collection)

    @staticmethod
    def _datetime(value):
        if isinstance(value, str):
            return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return value

    @staticmethod
    def _iso(value):
        if isinstance(value, datetime.datetime):
            return timestamp(value)
        return value

    def _decode(self, collection: str, record: dict | None) -> dict | None:
        if record is None:
            return None
        row = dict(record)
        if collection == "users":
            row["xp"] = row.pop("xp_total", 0)
        elif collection == "pairs":
            row["request_id"] = row.pop("pending_request_id", None)
        elif collection == "groups":
            row["deleted"] = row.get("deleted_at") is not None
            row["created_at"] = self._iso(row.get("created_at"))
            row["members"] = {
                user_id: {
                    "id": member.get("incarnation_id", member.get("id"))
                    if isinstance(member, dict) else member,
                    "joined_at": self._iso(member.get("joined_at"))
                    if isinstance(member, dict) else None,
                }
                for user_id, member in row.get("members", {}).items()
            }
        elif collection == "posts":
            row["direct"] = row.pop("direct_user_ids", [])
            row["groups"] = row.pop("group_grants", {})
            row["deleted"] = row.get("deleted_at") is not None
            row["created_at"] = self._iso(row.get("created_at"))
        elif collection == "comments":
            row["deleted"] = row.get("deleted_at") is not None
            row["created_at"] = self._iso(row.get("created_at"))
        elif collection == "published":
            row["post_id"] = row.get("post_id")
        elif collection == "idempotency":
            response = row.get("response") or {}
            row = {
                **response,
                "status": row.get("status_code", response.get("status")),
                "hash": row.get("request_hash"),
                "expires_at": row.get("expires_at"),
            }
        else:
            if "created_at" in row:
                row["created_at"] = self._iso(row["created_at"])
        return row

    def _encode(self, collection: str, record: dict) -> dict:
        row = dict(record)
        row.setdefault("schema_version", 1)
        if collection == "users":
            row["xp_total"] = row.pop("xp", 0)
            row.pop("created_at", None)
        elif collection == "pairs":
            row["pending_request_id"] = row.pop("request_id", None)
        elif collection == "groups":
            row["deleted_at"] = now() if row.pop("deleted", False) else None
            row["created_at"] = self._datetime(row.get("created_at"))
            row["members"] = {
                user_id: {
                    "incarnation_id": member["id"],
                    "joined_at": self._datetime(member.get("joined_at")),
                }
                for user_id, member in row.get("members", {}).items()
            }
        elif collection == "posts":
            row["direct_user_ids"] = row.pop("direct", [])
            row["group_grants"] = row.pop("groups", {})
            row["deleted_at"] = now() if row.pop("deleted", False) else None
            row["created_at"] = self._datetime(row.get("created_at"))
        elif collection == "comments":
            row["deleted_at"] = now() if row.pop("deleted", False) else None
            row["created_at"] = self._datetime(row.get("created_at"))
        elif collection == "published":
            pass
        elif collection == "idempotency":
            status = row.pop("status", None)
            request_hash = row.pop("hash", None)
            expires_at = self._datetime(row.pop("expires_at", None))
            response = row
            row = {
                "request_hash": request_hash,
                "response": response,
                "status_code": status,
                "expires_at": expires_at,
            }
        else:
            for field in ("created_at", "updated_at"):
                if field in row:
                    row[field] = self._datetime(row[field])
        return row

    # ------------------------------------------------------------------
    # Collection key helpers
    # ------------------------------------------------------------------

    def _ref(self, collection: str, key: str):
        return self._db.collection(self._collection_name(collection)).document(key)

    # ------------------------------------------------------------------
    # Read interface
    # ------------------------------------------------------------------

    def get(self, collection: str, key: str) -> dict | None:
        cache_key = f"{collection}/{key}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        snap = self._ref(collection, key).get(transaction=self._tx)
        result = self._decode(collection, snap.to_dict() if snap.exists else None)
        self._cache[cache_key] = result
        return result

    def rows(self, collection: str) -> list[dict]:
        # Full collection scan for MVP; Firestore has no SQL JOIN.
        # For large collections, use targeted queries from FirestoreRepository.
        docs = self._db.collection(self._collection_name(collection)).get(transaction=self._tx)
        return [self._decode(collection, d.to_dict()) for d in docs if d.exists]

    # ------------------------------------------------------------------
    # Write interface (buffered)
    # ------------------------------------------------------------------

    def put(self, collection: str, key: str, record: dict) -> None:
        self._pending_puts.append((collection, key, self._encode(collection, record)))
        self._cache[f"{collection}/{key}"] = record

    def delete(self, collection: str, key: str) -> None:
        self._pending_deletes.append((collection, key))
        self._cache[f"{collection}/{key}"] = None

    def flush(self):
        """Apply buffered writes to the Firestore transaction."""
        for collection, key, record in self._pending_puts:
            # Convert datetime objects so they store as Firestore Timestamps
            self._tx.set(self._ref(collection, key), record)
        for collection, key in self._pending_deletes:
            self._tx.delete(self._ref(collection, key))


class FirestoreRepository:
    """Implements SocialRepository backed by Firestore."""

    def __init__(self, db: fs.Client | None = None):
        self._db = db

    def _client(self) -> fs.Client:
        if self._db is None:
            self._db = get_db()
        return self._db

    def read(self, operation: Callable[[SocialTransaction], T]) -> T:
        """Read-only: runs operation inside a snapshot read for consistency."""
        db = self._client()
        tx = db.transaction(read_only=True)
        fs_tx = _FirestoreTx(db, tx)
        # Firestore read-only transactions don't use begin/commit the same way,
        # so we just open a transaction context.
        try:
            with tx:
                result = operation(fs_tx)
        except SocialError:
            raise
        except Exception as exc:
            raise SocialError(503, "Storage error") from exc
        return result

    def atomic(self, operation: Callable[[SocialTransaction], T]) -> T:
        """Read-then-write in a Firestore transaction with contention retry."""
        db = self._client()
        # Use @db.transaction decorator idiom
        result_holder = [None]

        @db.transaction(max_attempts=5)
        def run(tx):
            fs_tx = _FirestoreTx(db, tx)
            try:
                result = operation(fs_tx)
            except SocialError as exc:
                if exc.status == 409:
                    # Store conflict result; don't flush writes
                    result_holder[0] = exc
                    return
                raise
            fs_tx.flush()
            result_holder[0] = result

        try:
            run()
        except SocialError:
            raise
        except Exception as exc:
            raise SocialError(503, "Transaction failed; please retry") from exc

        held = result_holder[0]
        if isinstance(held, SocialError):
            raise held
        return held


# ---------------------------------------------------------------------------
# Discovery Reader backed by Firestore
# ---------------------------------------------------------------------------

class FirestoreDiscoveryReader:
    """Reads from the 'discoveries' Firestore collection."""

    def __init__(self, db: fs.Client | None = None):
        self._db = db

    def _client(self) -> fs.Client:
        if self._db is None:
            self._db = get_db()
        return self._db

    def _snap_to_dict(self, snap) -> dict | None:
        if not snap.exists:
            return None
        d = snap.to_dict()
        # Convert Firestore Timestamps to ISO strings for API responses
        for field in ("created_at",):
            if isinstance(d.get(field), datetime.datetime):
                d[field] = timestamp(d[field])
        return d

    def discovery(self, discovery_id: str) -> dict | None:
        snap = self._client().collection("discoveries").document(discovery_id).get()
        result = self._snap_to_dict(snap)
        return self._discovery_dto(result)

    def discoveries(self, owner_id: str) -> list[dict]:
        snaps = (self._client().collection("discoveries")
                 .where("owner_id", "==", owner_id)
                 .stream())
        result = []
        for s in snaps:
            d = self._snap_to_dict(s)
            if d:
                result.append(self._discovery_dto(d))
        return result

    def asset_owner(self, asset_id: str) -> str | None:
        snaps = (self._client().collection("discoveries")
                 .where("asset_id", "==", asset_id)
                 .limit(1)
                 .stream())
        for s in snaps:
            d = s.to_dict()
            return d.get("owner_id")
        return None

    @staticmethod
    def _discovery_dto(record: dict | None) -> dict | None:
        if record is None:
            return None
        row = dict(record)
        row.setdefault("name", row.get("subject_name") or row.get("subject_key", "Khám phá"))
        if row.get("reward_reason") == "valid":
            row["reward_reason"] = "granted"
        return row


# ---------------------------------------------------------------------------
# Storage URL Issuer (60-second signed URLs)
# ---------------------------------------------------------------------------

class StorageUrlIssuer:
    """Issues 60-second signed read URLs for private Storage objects."""

    EXPIRY_SECONDS = 60

    def __init__(self, bucket=None):
        self._bucket = bucket  # injected or lazily loaded

    def _get_bucket(self):
        if self._bucket is None:
            self._bucket = get_storage_bucket()
        return self._bucket

    def issue(self, asset_id: str, expires_at: datetime.datetime) -> str:
        """Return a signed URL for the asset. expires_at is used as deadline."""
        # Look up the object path from the assets collection
        db = get_db()
        snap = db.collection("assets").document(asset_id).get()
        if not snap.exists:
            raise SocialError(404, "Asset not found")
        asset = snap.to_dict()
        if asset.get("state") not in ("ready", "attached"):
            raise SocialError(404, "Asset not ready")

        if os.getenv("STORAGE_TYPE", "firebase").strip().lower() == "local":
            if os.getenv("ENV", "production") not in {"development", "test"}:
                raise SocialError(503, "Local asset storage is not available in production")
            expires = int(expires_at.timestamp())
            from .assets_routes import _local_signature
            signature = _local_signature(asset_id, expires)
            return f"/api/v1/assets/{asset_id}/file?expires={expires}&signature={signature}"

        blob: Blob = self._get_bucket().blob(asset["object_path"])
        url = blob.generate_signed_url(
            expiration=datetime.timedelta(seconds=self.EXPIRY_SECONDS),
            method="GET",
            version="v4",
        )
        return url


def load_firebase_social_services():
    """Create lazy Firestore-backed services for the live API."""
    from .auth import FirebaseActorResolver
    from .social.fixtures import SocialServices

    return SocialServices(
        actor=FirebaseActorResolver(),
        repository=FirestoreRepository(),
        discovery=FirestoreDiscoveryReader(),
        urls=StorageUrlIssuer(),
    )
