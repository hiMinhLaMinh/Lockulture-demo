"""Explicit development adapters, backed by the contract's synthetic identities."""
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from .core import ActorResolver, AssetUrlIssuer, DiscoveryReader, MemoryRepository, SocialRepository, now
from .relationships import membership, pair_key

CONTRACTS = Path(__file__).resolve().parents[3] / "contracts"


@dataclass
class SocialServices:
    actor: ActorResolver
    repository: SocialRepository
    discovery: DiscoveryReader
    urls: AssetUrlIssuer
    clock: Callable[[], datetime] = now


class FixtureActors:
    def __init__(self, users):
        self.tokens = {f"lockulture-dev-{name}": row["id"] for name, row in users.items()}

    def resolve(self, token):
        return self.tokens.get(token)


class FixtureDiscoveries:
    def __init__(self, rows):
        self.rows = {row["id"]: row for row in rows}

    def discovery(self, discovery_id):
        return self.rows.get(discovery_id)

    def discoveries(self, owner_id):
        return [row for row in self.rows.values() if row["owner_id"] == owner_id]

    def asset_owner(self, asset_id):
        return next((row["owner_id"] for row in self.rows.values() if row["asset_id"] == asset_id), None)


class FixtureUrls:
    image = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 480">
    <rect width="640" height="480" fill="#174E4B"/>
    <path d="M0 400L200 180L340 320L475 135L640 380V480H0Z" fill="#356268"/>
    <circle cx="150" cy="105" r="37" fill="#F4C568"/></svg>"""

    def __init__(self):
        self.secret = secrets.token_bytes(32)

    def signature(self, asset_id, expires):
        return hmac.digest(self.secret, f"{asset_id}:{expires}".encode(), "sha256").hex()

    def issue(self, asset_id, expires_at):
        expires = int(expires_at.timestamp())
        return f"/_dev/social-assets/{asset_id}?expires={expires}&signature={self.signature(asset_id, expires)}"

    def valid(self, asset_id, expires, signature, time):
        return (time.timestamp() < expires and signature.isascii()
                and hmac.compare_digest(signature, self.signature(asset_id, expires)))


def load_fixture_services():
    identities = json.loads((CONTRACTS / "fixtures/identities.json").read_text())
    users = identities["users"]
    group = identities["group"]
    owner = users[group["owner"]]["id"]
    joined = datetime.fromisoformat("2026-11-11T00:00:00+00:00")
    seed = {"users": {row["id"]: row for row in users.values()}, "pairs": {}, "groups": {}}
    for first, second in identities["friends"]:
        pair = sorted([users[first]["id"], users[second]["id"]])
        seed["pairs"][pair_key(*pair)] = {"users": pair, "status": "accepted", "request_id": None}
    seed["groups"][group["id"]] = {
        "id": group["id"], "owner_id": owner, "name": "Khám phá Huế",
        "created_at": "2026-11-11T00:00:00Z", "deleted": False,
        "members": {users[name]["id"]: membership(joined) for name in group["members"]},
    }
    discovery = json.loads((CONTRACTS / "examples/discovery.json").read_text())["data"]
    return SocialServices(FixtureActors(users), MemoryRepository(seed),
                          FixtureDiscoveries([discovery]), FixtureUrls())
