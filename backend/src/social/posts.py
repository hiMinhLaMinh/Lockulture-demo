"""Post grants, interactions and response projections."""
from .core import digest, new_id, require, timestamp
from .relationships import friends, live_group_grant, user, visible_group

REACTIONS = ("heart", "clap", "wow")


def can_read(tx, post, actor):
    if post["deleted"]:
        return False
    if actor == post["author_id"] or actor in post["direct"]:
        return True
    return any(group and live_group_grant(post, group, actor)
               for group in (tx.get("groups", group_id) for group_id in post["groups"]))


def visible_post(tx, actor, post_id):
    post = tx.get("posts", post_id)
    require(post and can_read(tx, post, actor), 404, "Post not found")
    return post


def reaction_dto(tx, post_id, actor, override=None):
    reactions = {row["user_id"]: row["reaction"] for row in tx.rows("reactions")
                 if row["post_id"] == post_id and row["reaction"] is not None}
    if override is not None:
        reactions[actor] = override
    return {"reaction": reactions.get(actor),
            "counts": {value: list(reactions.values()).count(value) for value in REACTIONS}}


def post_dto(tx, post, actor):
    post_id = post["id"]
    reactions = reaction_dto(tx, post_id, actor)
    return {
        **{key: post[key] for key in (
            "id", "discovery_id", "asset_id", "subject_name", "knowledge", "caption", "created_at",
        )},
        "author": user(tx, post["author_id"]),
        "my_reaction": reactions["reaction"], "reaction_counts": reactions["counts"],
        "comment_count": sum(row["post_id"] == post_id and not row["deleted"]
                             for row in tx.rows("comments")),
        "audience": {"friend_ids": post["direct"], "group_ids": list(post["groups"])}
        if actor == post["author_id"] else None,
    }


def group_snapshots(tx, actor, group_ids, existing):
    snapshots = {}
    for group_id in group_ids:
        if group_id in existing:
            continue
        group = visible_group(tx, actor, group_id)
        snapshots[group_id] = {person: membership["id"]
                               for person, membership in group["members"].items()}
    return snapshots


def publish(tx, actor, body, reader, time):
    discovery_id = str(body.discovery_id)
    discovery = reader.discovery(discovery_id)
    require(discovery and discovery["owner_id"] == actor, 404, "Discovery not found")
    require(reader.asset_owner(discovery["asset_id"]) == actor, 404, "Asset not found")
    require(tx.get("published", discovery_id) is None, 409, "Discovery already published")
    direct = list(map(str, body.friend_ids))
    require(all(friends(tx, actor, recipient) for recipient in direct), 422,
            "Direct recipients must be accepted friends")
    groups = group_snapshots(tx, actor, map(str, body.group_ids), {})
    post = {
        "id": new_id(), "discovery_id": discovery_id, "asset_id": discovery["asset_id"],
        "subject_name": discovery["name"], "knowledge": discovery["knowledge"],
        "caption": body.caption, "created_at": timestamp(time), "author_id": actor,
        "direct": direct, "groups": groups, "deleted": False,
    }
    result = post_dto(tx, post, actor)
    tx.put("posts", post["id"], post)
    tx.put("published", discovery_id, {"post_id": post["id"]})
    return result


def share(tx, actor, post_id, groups):
    post = visible_post(tx, actor, post_id)
    require(post["author_id"] == actor, 403, "Post author required")
    post["groups"].update(group_snapshots(tx, actor, groups, post["groups"]))
    result = post_dto(tx, post, actor)
    tx.put("posts", post_id, post)
    return result


def delete_post(tx, actor, post_id):
    post = tx.get("posts", post_id)
    require(post and (post["author_id"] == actor or can_read(tx, post, actor)), 404, "Post not found")
    require(post["author_id"] == actor, 403, "Post author required")
    tx.put("posts", post_id, {**post, "deleted": True})


def react(tx, actor, post_id, reaction):
    visible_post(tx, actor, post_id)
    result = reaction_dto(tx, post_id, actor, override=reaction) if reaction else None
    key = digest([post_id, actor])
    if reaction is None:
        tx.delete("reactions", key)
    else:
        tx.put("reactions", key, {"post_id": post_id, "user_id": actor, "reaction": reaction})
    return result


def comment_dto(tx, comment):
    return {**{key: comment[key] for key in ("id", "post_id", "text", "created_at")},
            "author": user(tx, comment["author_id"])}


def create_comment(tx, actor, post_id, text, time):
    visible_post(tx, actor, post_id)
    comment = {"id": new_id(), "post_id": post_id, "text": text, "created_at": timestamp(time),
               "author_id": actor, "deleted": False}
    result = comment_dto(tx, comment)
    tx.put("comments", comment["id"], comment)
    return result


def delete_comment(tx, actor, comment_id):
    comment = tx.get("comments", comment_id)
    require(comment is not None, 404, "Comment not found")
    if comment["author_id"] != actor:
        require(not comment["deleted"], 404, "Comment not found")
        visible_post(tx, actor, comment["post_id"])
        require(False, 403, "Comment author required")
    tx.put("comments", comment_id, {**comment, "deleted": True})
