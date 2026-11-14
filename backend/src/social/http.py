"""FastAPI adapter for the v1 social contract."""
from datetime import timedelta
from urllib.parse import urljoin
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

from . import posts, relationships as relations
from .core import SocialError, created_key, mutate, normalized, page, require, timestamp, user_key

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
Search = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=50)]
EraId = Literal[
    "ERA_ANCIENT", "ERA_BAC_THUOC", "ERA_NGO_DINH_TIEN_LE", "ERA_LY_TRAN", "ERA_LE_SO",
    "ERA_MAC_LE_TRUNG_HUNG", "ERA_TAY_SON", "ERA_NGUYEN", "ERA_MODERN", "ERA_CONTEMPORARY",
]
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
    ids = sorted(set(ids))
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
        rows = [relations.public_user(row) for row in tx.rows("users") if row["id"] != actor and
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


class PublishInput(Input):
    discovery_id: UUID
    caption: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]
    friend_ids: list[UUID]
    group_ids: list[UUID]

    @field_validator("friend_ids", "group_ids")
    @classmethod
    def check_ids(cls, ids, info):
        return distinct_ids(ids, 50 if info.field_name == "friend_ids" else 10)


class ShareInput(Input):
    group_ids: list[UUID]

    @field_validator("group_ids")
    @classmethod
    def check_ids(cls, ids):
        return distinct_ids(ids, 10)


class ReactionInput(Input):
    reaction: Literal["heart", "clap", "wow"]


class CommentInput(Input):
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]


@router.post("/posts", operation_id="publishPost", status_code=201)
def publish_post(body: PublishInput, key: Key, ctx: Context):
    require(body.friend_ids or body.group_ids, 422, "Select at least one recipient")
    return write(ctx, "publishPost", key, 201, lambda tx, actor, time:
                 posts.publish(tx, actor, body, ctx[0].discovery, time), body=body)


@router.get("/posts", operation_id="listPosts")
def list_posts(ctx: Context, group_id: UUID | None = None,
               limit: Limit = 20, cursor: str | None = None):
    def list_rows(tx, actor):
        group = relations.visible_group(tx, actor, str(group_id)) if group_id else None
        rows = [post for post in tx.rows("posts") if not post["deleted"] and
                (relations.live_group_grant(post, group, actor) if group else posts.can_read(tx, post, actor))]
        result = page(rows, limit, cursor, ["posts", actor, str(group_id)], created_key, descending=True)
        result["items"] = [posts.post_dto(tx, post, actor) for post in result["items"]]
        return result

    return read(ctx, list_rows)


@router.get("/posts/{post_id}", operation_id="getPost")
def get_post(post_id: UUID, ctx: Context):
    return read(ctx, lambda tx, actor: posts.post_dto(tx, posts.visible_post(tx, actor, str(post_id)), actor))


@router.delete("/posts/{post_id}", operation_id="deletePost", status_code=204)
def delete_post(post_id: UUID, key: Key, ctx: Context):
    return write(ctx, "deletePost", key, 204, lambda tx, actor, _:
                 posts.delete_post(tx, actor, str(post_id)), path=(post_id,))


@router.post("/posts/{post_id}/shares", operation_id="addPostGroups")
def share_post(post_id: UUID, body: ShareInput, key: Key, ctx: Context):
    return write(ctx, "addPostGroups", key, 200, lambda tx, actor, _:
                 posts.share(tx, actor, str(post_id), map(str, body.group_ids)), path=(post_id,), body=body)


@router.put("/posts/{post_id}/reaction", operation_id="setReaction")
def set_reaction(post_id: UUID, body: ReactionInput, key: Key, ctx: Context):
    return write(ctx, "setReaction", key, 200, lambda tx, actor, _:
                 posts.react(tx, actor, str(post_id), body.reaction), path=(post_id,), body=body)


@router.delete("/posts/{post_id}/reaction", operation_id="removeReaction", status_code=204)
def remove_reaction(post_id: UUID, key: Key, ctx: Context):
    return write(ctx, "removeReaction", key, 204, lambda tx, actor, _:
                 posts.react(tx, actor, str(post_id), None), path=(post_id,))


@router.get("/posts/{post_id}/comments", operation_id="listComments")
def list_comments(post_id: UUID, ctx: Context, limit: Limit = 20, cursor: str | None = None):
    def list_rows(tx, actor):
        posts.visible_post(tx, actor, str(post_id))
        rows = [row for row in tx.rows("comments") if row["post_id"] == str(post_id) and not row["deleted"]]
        result = page(rows, limit, cursor, ["comments", actor, str(post_id)], created_key, descending=True)
        result["items"] = [posts.comment_dto(tx, row) for row in result["items"]]
        return result

    return read(ctx, list_rows)


@router.post("/posts/{post_id}/comments", operation_id="createComment", status_code=201)
def create_comment(post_id: UUID, body: CommentInput, key: Key, ctx: Context):
    return write(ctx, "createComment", key, 201, lambda tx, actor, time:
                 posts.create_comment(tx, actor, str(post_id), body.text, time), path=(post_id,), body=body)


@router.delete("/comments/{comment_id}", operation_id="deleteComment", status_code=204)
def delete_comment(comment_id: UUID, key: Key, ctx: Context):
    return write(ctx, "deleteComment", key, 204, lambda tx, actor, _:
                 posts.delete_comment(tx, actor, str(comment_id)), path=(comment_id,))


@router.get("/assets/{asset_id}/url", operation_id="getAssetUrl")
def asset_url(asset_id: UUID, request: Request, response: Response, ctx: Context, post_id: UUID | None = None):
    services, _ = ctx
    asset = str(asset_id)

    def check_asset(tx, actor):
        owner = services.discovery.asset_owner(asset)
        require(owner is not None, 404, "Asset not found")
        if owner != actor:
            require(post_id is not None, 404, "Asset not found")
            post = posts.visible_post(tx, actor, str(post_id))
            require(post["asset_id"] == asset, 404, "Asset not found")

    read(ctx, check_asset)
    expires_at = services.clock() + timedelta(seconds=60)
    url = services.urls.issue(asset, expires_at)
    response.headers["Cache-Control"] = "no-store"
    return {"url": urljoin(str(request.base_url), url), "expires_at": timestamp(expires_at)}


@router.get("/discoveries", operation_id="listDiscoveries")
def list_discoveries(ctx: Context, limit: Limit = 20, cursor: str | None = None,
                     era_id: EraId | None = None, mode: Literal["free", "mission"] | None = None):
    services, actor = ctx
    rows = [row for row in services.discovery.discoveries(actor) if row["owner_id"] == actor and
            (era_id is None or row["era_id"] == era_id) and (mode is None or row["mode"] == mode)]
    return page(rows, limit, cursor, ["discoveries", actor, era_id, mode], created_key, descending=True)


@router.get("/discoveries/{discovery_id}", operation_id="getDiscovery")
def get_discovery(discovery_id: UUID, ctx: Context):
    services, actor = ctx
    row = services.discovery.discovery(str(discovery_id))
    require(row and row["owner_id"] == actor, 404, "Discovery not found")
    return row


@router.get("/leaderboard", operation_id="getLeaderboard")
def leaderboard(ctx: Context, scope: Literal["friends"] = "friends"):
    def rank_users(tx, actor):
        users = sorted([relations.user(tx, actor), *relations.friend_users(tx, actor)],
                       key=lambda row: (-row["xp"], *user_key(row)))
        ranks = {}
        items = []
        for index, user in enumerate(users, 1):
            rank = ranks.setdefault(user["xp"], index)
            items.append({"user": user, "rank": rank})
        return {"items": items, "my_rank": ranks[relations.user(tx, actor)["xp"]],
                "as_of": timestamp(ctx[0].clock())}

    return read(ctx, rank_users)
