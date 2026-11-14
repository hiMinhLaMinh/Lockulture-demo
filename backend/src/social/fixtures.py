"""Explicit development adapters, backed by the contract's synthetic identities."""
import json
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
    def issue(self, asset_id, expires_at):
        return f"data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20viewBox='0%200%20640%20480'%3E%3Crect%20width='640'%20height='480'%20fill='%23174E4B'/%3E%3Cpath%20d='M0%20400L200%20180L340%20320L475%20135L640%20380V480H0Z'%20fill='%23356268'/%3E%3Ccircle%20cx='150'%20cy='105'%20r='37'%20fill='%23F4C568'/%3E%3C/svg%3E"


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
