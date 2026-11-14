"""Friendship and group operations on a repository transaction."""
from .core import digest, new_id, require, timestamp


def public_user(row):
    return {key: row[key] for key in ("id", "display_name", "username", "bio", "xp")}


def user(tx, user_id):
    result = tx.get("users", user_id)
    require(result is not None, 404, "User not found")
    return public_user(result)


def pair_key(first, second):
    return digest(sorted([first, second]))


def friends(tx, actor, other):
    pair = tx.get("pairs", pair_key(actor, other))
    return pair is not None and pair["status"] == "accepted"


def friend_users(tx, actor):
    return [
        user(tx, next(member for member in pair["users"] if member != actor))
        for pair in tx.rows("pairs")
        if pair["status"] == "accepted" and actor in pair["users"]
    ]


def request_dto(tx, row):
    return {
        "id": row["id"], "sender": user(tx, row["sender_id"]),
        "recipient": user(tx, row["recipient_id"]), "status": row["status"],
        "created_at": row["created_at"],
    }


def request_friend(tx, actor, target, time):
    require(actor != target, 422, "Cannot request yourself")
    user(tx, target)
    key = pair_key(actor, target)
    pair = tx.get("pairs", key)
    require(not pair or pair["status"] == "removed", 409, "Friendship or pending request exists")
    row = {"id": new_id(), "sender_id": actor, "recipient_id": target,
           "status": "pending", "created_at": timestamp(time)}
    result = request_dto(tx, row)
    tx.put("requests", row["id"], row)
    tx.put("pairs", key, {"users": sorted([actor, target]), "status": "pending", "request_id": row["id"]})
    return result


def respond_friend(tx, actor, request_id, action):
    row = tx.get("requests", request_id)
    require(row and actor in (row["sender_id"], row["recipient_id"]), 404, "Request not found")
    role = "sender_id" if action == "cancel" else "recipient_id"
    require(row[role] == actor, 403, "Action is unavailable to this participant")
    require(row["status"] == "pending", 409, "Request is already closed")
    row["status"] = {"accept": "accepted", "reject": "rejected", "cancel": "cancelled"}[action]
    result = request_dto(tx, row)
    people = sorted([row["sender_id"], row["recipient_id"]])
    tx.put("requests", request_id, row)
    tx.put("pairs", pair_key(*people), {
        "users": people, "status": "accepted" if action == "accept" else "removed",
        "request_id": None,
    })
    return result


def remove_friend(tx, actor, other):
    key = pair_key(actor, other)
    pair = tx.get("pairs", key)
    if pair and pair["status"] == "accepted":
        tx.put("pairs", key, {**pair, "status": "removed"})


def visible_group(tx, actor, group_id):
    group = tx.get("groups", group_id)
    require(group and not group["deleted"] and actor in group["members"], 404, "Group not found")
    return group


def owned_group(tx, actor, group_id):
    group = visible_group(tx, actor, group_id)
    require(group["owner_id"] == actor, 403, "Group owner required")
    return group


def live_group_grant(post, group, actor):
    membership = group["members"].get(actor)
    return bool(not group["deleted"] and membership and
                post["groups"].get(group["id"], {}).get(actor) == membership["id"])


def group_dto(tx, group, actor):
    return {
        **{key: group[key] for key in ("id", "name", "owner_id", "created_at")},
        "member_count": len(group["members"]),
        "post_count": sum(not post["deleted"] and live_group_grant(post, group, actor)
                          for post in tx.rows("posts")),
    }


def membership(time):
    return {"id": new_id(), "joined_at": timestamp(time)}


def add_group_members(tx, actor, group, targets, time):
    new_members = set(targets) - group["members"].keys()
    require(all(friends(tx, actor, other) for other in new_members), 422, "Members must be accepted friends")
    require(len(group["members"]) + len(new_members) <= 20, 409, "Group member limit reached")
    group["members"].update({target: membership(time) for target in sorted(new_members)})
    return save_group(tx, group, actor)


def create_group(tx, actor, name, targets, time):
    require(actor not in targets, 422, "Owner is already included")
    group = {"id": new_id(), "name": name, "owner_id": actor, "created_at": timestamp(time),
             "deleted": False, "members": {actor: membership(time)}}
    return add_group_members(tx, actor, group, targets, time)


def save_group(tx, group, actor):
    result = group_dto(tx, group, actor)
    tx.put("groups", group["id"], group)
    return result


def rename_group(tx, actor, group_id, name):
    group = owned_group(tx, actor, group_id)
    return save_group(tx, {**group, "name": name}, actor)


def dissolve_group(tx, actor, group_id):
    group = owned_group(tx, actor, group_id)
    tx.put("groups", group_id, {**group, "deleted": True})


def remove_member(tx, actor, group_id, target):
    group = visible_group(tx, actor, group_id)
    require(actor in (group["owner_id"], target), 403, "Cannot remove this member")
    require(target != group["owner_id"], 409, "Owner must dissolve the group")
    group["members"].pop(target, None)
    tx.put("groups", group_id, group)
