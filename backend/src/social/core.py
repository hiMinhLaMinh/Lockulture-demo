"""Social transaction boundary and shared API rules."""
import base64
import binascii
import hashlib
import json
import unicodedata
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Callable, Protocol, TypeVar
from uuid import UUID, uuid4

T = TypeVar("T")
Record = dict


class ActorResolver(Protocol):
    def resolve(self, token: str) -> str | None: ...


class DiscoveryReader(Protocol):
    def discovery(self, discovery_id: str) -> Record | None: ...
    def discoveries(self, owner_id: str) -> list[Record]: ...
    def asset_owner(self, asset_id: str) -> str | None: ...


class AssetUrlIssuer(Protocol):
    def issue(self, asset_id: str, expires_at: datetime) -> str: ...


class SocialTransaction(Protocol):
    def get(self, collection: str, key: str) -> Record | None: ...
    def rows(self, collection: str) -> list[Record]: ...
    def put(self, collection: str, key: str, record: Record) -> None: ...
    def delete(self, collection: str, key: str) -> None: ...


class SocialRepository(Protocol):
    def read(self, operation: Callable[[SocialTransaction], T]) -> T: ...
    def atomic(self, operation: Callable[[SocialTransaction], T]) -> T: ...


class MemoryTransaction:
    def __init__(self, tables: dict):
        self.tables = tables

    def get(self, collection, key):
        return deepcopy(self.tables.get(collection, {}).get(key))

    def rows(self, collection):
        return deepcopy(list(self.tables.get(collection, {}).values()))

    def put(self, collection, key, record):
        self.tables.setdefault(collection, {})[key] = deepcopy(record)


    def delete(self, collection, key):
        self.tables.get(collection, {}).pop(key, None)


class MemoryRepository:
    def __init__(self, seed: dict):
        self._tables = deepcopy(seed)
        self._lock = RLock()

    def read(self, operation):
        with self._lock:
            return operation(MemoryTransaction(deepcopy(self._tables)))

    def atomic(self, operation):
        with self._lock:
            transaction = MemoryTransaction(deepcopy(self._tables))
            result = operation(transaction)
            self._tables = transaction.tables
            return result


class SocialError(Exception):
    def __init__(self, status: int, message: str, code: str | None = None):
        self.status = status
        self.message = message
        self.code = code or {
            401: "unauthorized", 403: "forbidden", 404: "not_found",
            409: "conflict", 422: "validation_error", 503: "provider_failed",
        }[status]


def require(condition: bool, status: int, message: str):
    if not condition:
        raise SocialError(status, message)


def now():
    return datetime.now(timezone.utc)


def timestamp(value):
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def new_id():
    return str(uuid4())


def digest(value):
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(data.encode()).hexdigest()


def normalized(value):
    decomposed = unicodedata.normalize("NFKD", value.casefold().replace("đ", "d"))
    return "".join(character for character in decomposed if not unicodedata.combining(character))


def page(rows, limit, cursor, scope, key, *, descending=False):
    scope_hash = digest(scope)
    boundary = None
    if cursor is not None:
        try:
            require(0 < len(cursor) <= 2048 and "=" not in cursor, 422, "Invalid cursor")
            raw = base64.b64decode(cursor + "=" * (-len(cursor) % 4), altchars=b"-_", validate=True)
            parsed = json.loads(raw)
            require(isinstance(parsed, list) and len(parsed) == 3, 422, "Invalid cursor")
            stored_scope, sort_value, item_id = parsed
            require(stored_scope == scope_hash and isinstance(sort_value, str), 422, "Invalid cursor scope")
            require(str(UUID(item_id)) == item_id, 422, "Invalid cursor ID")
            if descending:
                require(timestamp(datetime.fromisoformat(sort_value)) == sort_value, 422, "Invalid cursor date")
            boundary = (sort_value, item_id)
        except (ValueError, TypeError, AttributeError, binascii.Error) as error:
            raise SocialError(422, "Invalid cursor") from error

    ordered = sorted(rows, key=key, reverse=descending)
    if boundary is not None:
        if descending:
            ordered = [row for row in ordered if key(row) < boundary]
        else:
            ordered = [row for row in ordered if key(row) > boundary]
    next_cursor = None
    if len(ordered) > limit:
        raw = json.dumps([scope_hash, *key(ordered[limit - 1])], separators=(",", ":")).encode()
        next_cursor = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    return {"items": ordered[:limit], "next_cursor": next_cursor}


def user_key(row):
    return row["username"], row["id"]


def created_key(row):
    return timestamp(datetime.fromisoformat(row["created_at"])), row["id"]


def mutate(repository, actor, operation_id, key, path, body, status, operation, clock=now):
    storage_key = digest([actor, operation_id, key])
    request_hash = digest([path, body])

    def execute(transaction):
        current_time = clock()
        stored = transaction.get("idempotency", storage_key)
        if stored and stored["expires_at"] > current_time:
            if stored["hash"] != request_hash:
                raise SocialError(409, "Idempotency key already used", "idempotency_conflict")
            return stored

        try:
            result = {"status": status, "body": operation(transaction)}
        except SocialError as error:
            if error.status != 409:
                raise
            # Business conflicts are raised before any domain writes.
            result = {"status": 409, "error": {
                "code": error.code, "message": error.message,
                "retryable": False, "request_id": new_id(),
            }}
        result.update(hash=request_hash, expires_at=current_time + timedelta(days=7))
        transaction.put("idempotency", storage_key, result)
        return result

    return repository.atomic(execute)
