"""FastAPI adapter for the v1 social contract."""
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

from . import relationships as relations
from .core import SocialError, created_key, mutate, normalized, now, page, require, user_key

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
Search = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=50)]
Limit = Annotated[int, Query(ge=1, le=50)]
Key = Annotated[UUID, Header(alias="Idempotency-Key")]
router = APIRouter(prefix="/api/v1")


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FriendInput(Input):
    target_user_id: UUID


class FriendAction(Input):
    action: Literal["accept", "reject", "cancel"]


class GroupName(Input):
    name: Name


def distinct_ids(ids, maximum):
    ids = list(dict.fromkeys(ids))
    if len(ids) > maximum:
        raise ValueError(f"At most {maximum} distinct IDs")
    return ids


class GroupInput(GroupName):
    member_ids: list[UUID]

    @field_validator("member_ids")
    @classmethod
    def check_ids(cls, ids):
        return distinct_ids(ids, 19)


class Members(Input):
    user_ids: list[UUID]

    @field_validator("user_ids")
    @classmethod
    def check_ids(cls, ids):
        return distinct_ids(ids, 19)


def context(request: Request, authorization: Annotated[str | None, Header()] = None):
    services = request.app.state.social
    scheme, _, token = (authorization or "").partition(" ")
    actor = services.actor.resolve(token) if services and scheme.lower() == "bearer" and token else None
    require(actor is not None, 401, "Authentication required")
    return services, actor


Context = Annotated[tuple, Depends(context)]


def read(ctx, operation):
    services, actor = ctx
    return services.repository.read(lambda tx: operation(tx, actor))


def write(ctx, operation_id, key, status, operation, *, path=(), body=None):
    services, actor = ctx
    result = mutate(
        services.repository, actor, operation_id, str(key), [str(value) for value in path],
        body.model_dump(mode="json") if body else None, status,
        lambda tx: operation(tx, actor, services.clock()), clock=services.clock,
    )
    if "error" in result:
        return JSONResponse({"error": result["error"]}, status_code=result["status"])
    if result["status"] == 204:
        return Response(status_code=204)
    return JSONResponse(result["body"], status_code=result["status"])


@router.get("/health", operation_id="health")
def health():
    return {"status": "ok", "contract_version": "1.0.0"}


@router.get("/me", operation_id="getMe")
def me(ctx: Context):
    return read(ctx, relations.user)


@router.get("/users", operation_id="searchUsers")
def search_users(ctx: Context, query: Search, limit: Limit = 20, cursor: str | None = None):
    term = normalized(query)

    def list_users(tx, actor):
        rows = [row for row in tx.rows("users") if row["id"] != actor and
                (term in normalized(row["display_name"]) or term in row["username"])]
        return page(rows, limit, cursor, ["users", actor, term], user_key)

    return read(ctx, list_users)


@router.get("/users/{user_id}", operation_id="getUser")
def get_user(user_id: UUID, ctx: Context):
    return read(ctx, lambda tx, _: relations.user(tx, str(user_id)))


@router.get("/friends", operation_id="listFriends")
def list_friends(ctx: Context, limit: Limit = 20, cursor: str | None = None):
    return read(ctx, lambda tx, actor: page(
        relations.friend_users(tx, actor), limit, cursor, ["friends", actor], user_key))


@router.get("/friend-requests", operation_id="listFriendRequests")
def list_requests(ctx: Context, direction: Literal["incoming", "outgoing"] = "incoming",
                  limit: Limit = 20, cursor: str | None = None):
    field = "recipient_id" if direction == "incoming" else "sender_id"

    def list_rows(tx, actor):
        rows = [relations.request_dto(tx, row) for row in tx.rows("requests")
                if row[field] == actor]
        return page(rows, limit, cursor, ["requests", actor, direction], created_key, descending=True)

    return read(ctx, list_rows)


@router.post("/friend-requests", operation_id="requestFriend", status_code=201)
def request_friend(body: FriendInput, key: Key, ctx: Context):
    return write(ctx, "requestFriend", key, 201, lambda tx, actor, time:
                 relations.request_friend(tx, actor, str(body.target_user_id), time), body=body)


@router.patch("/friend-requests/{request_id}", operation_id="respondFriendRequest")
def respond_friend(request_id: UUID, body: FriendAction, key: Key, ctx: Context):
    return write(ctx, "respondFriendRequest", key, 200, lambda tx, actor, _:
                 relations.respond_friend(tx, actor, str(request_id), body.action),
                 path=(request_id,), body=body)


@router.delete("/friends/{user_id}", operation_id="removeFriend", status_code=204)
def remove_friend(user_id: UUID, key: Key, ctx: Context):
    return write(ctx, "removeFriend", key, 204, lambda tx, actor, _:
                 relations.remove_friend(tx, actor, str(user_id)), path=(user_id,))


@router.get("/groups", operation_id="listGroups")
def list_groups(ctx: Context, limit: Limit = 20, cursor: str | None = None):
    def list_rows(tx, actor):
        rows = [group for group in tx.rows("groups")
                if not group["deleted"] and actor in group["members"]]
        result = page(rows, limit, cursor, ["groups", actor], created_key, descending=True)
        result["items"] = [relations.group_dto(tx, row, actor) for row in result["items"]]
        return result

    return read(ctx, list_rows)


@router.post("/groups", operation_id="createGroup", status_code=201)
def create_group(body: GroupInput, key: Key, ctx: Context):
    return write(ctx, "createGroup", key, 201, lambda tx, actor, time:
                 relations.create_group(tx, actor, body.name, list(map(str, body.member_ids)), time),
                 body=body)


@router.get("/groups/{group_id}", operation_id="getGroup")
def get_group(group_id: UUID, ctx: Context):
    return read(ctx, lambda tx, actor:
                relations.group_dto(tx, relations.visible_group(tx, actor, str(group_id)), actor))


@router.patch("/groups/{group_id}", operation_id="renameGroup")
def rename_group(group_id: UUID, body: GroupName, key: Key, ctx: Context):
    return write(ctx, "renameGroup", key, 200, lambda tx, actor, _:
                 relations.rename_group(tx, actor, str(group_id), body.name),
                 path=(group_id,), body=body)


@router.delete("/groups/{group_id}", operation_id="dissolveGroup", status_code=204)
def dissolve_group(group_id: UUID, key: Key, ctx: Context):
    return write(ctx, "dissolveGroup", key, 204, lambda tx, actor, _:
                 relations.dissolve_group(tx, actor, str(group_id)), path=(group_id,))


@router.get("/groups/{group_id}/members", operation_id="listMembers")
def list_members(group_id: UUID, ctx: Context, limit: Limit = 20, cursor: str | None = None):
    def list_rows(tx, actor):
        group = relations.visible_group(tx, actor, str(group_id))
        rows = [{"user": relations.user(tx, user_id), "joined_at": member["joined_at"],
                 "role": "owner" if user_id == group["owner_id"] else "member"}
                for user_id, member in group["members"].items()]
        return page(rows, limit, cursor, ["members", actor, str(group_id)],
                    lambda row: user_key(row["user"]))

    return read(ctx, list_rows)


@router.post("/groups/{group_id}/members", operation_id="addMembers")
def add_members(group_id: UUID, body: Members, key: Key, ctx: Context):
    def add(tx, actor, time):
        group = relations.owned_group(tx, actor, str(group_id))
        return relations.add_group_members(tx, actor, group, list(map(str, body.user_ids)), time)

    return write(ctx, "addMembers", key, 200, add, path=(group_id,), body=body)


@router.delete("/groups/{group_id}/members/{user_id}", operation_id="removeMember", status_code=204)
def remove_member(group_id: UUID, user_id: UUID, key: Key, ctx: Context):
    return write(ctx, "removeMember", key, 204, lambda tx, actor, _:
                 relations.remove_member(tx, actor, str(group_id), str(user_id)), path=(group_id, user_id))
