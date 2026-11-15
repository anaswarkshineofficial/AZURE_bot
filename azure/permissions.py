from __future__ import annotations

from typing import Iterable

from azure.config import REQUIRED_DISCORD_PERMISSIONS


def user_is_admin(member) -> bool:
    if member is None:
        return False
    if member.guild_permissions.administrator:
        return True
    if member.guild_permissions.manage_guild:
        return True
    if any(role.name.lower() in {"admin", "founder", "head admin", "co-founder"} for role in member.roles):
        return True
    return False


def bot_has_required_permissions(guild) -> tuple[bool, list[str]]:
    if guild is None or guild.me is None:
        return False, ["guild unavailable"]
    missing = []
    for perm in REQUIRED_DISCORD_PERMISSIONS:
        if not getattr(guild.me.guild_permissions, perm, False):
            missing.append(perm)
    return not missing, missing


def role_hierarchy_ok(guild, managed_role) -> bool:
    me = guild.me
    if me is None:
        return False
    if me.top_role is None:
        return False
    return me.top_role >= managed_role


def get_missing_permissions(member, required: Iterable[str]) -> list[str]:
    perms = member.guild_permissions
    missing = []
    for name in required:
        if not getattr(perms, name, False):
            missing.append(name)
    return missing
