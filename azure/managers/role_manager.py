from __future__ import annotations

from typing import Iterable


def guild_get_role_by_name(guild, name: str):
    for role in guild.roles:
        if role.name == name:
            return role
    return None


async def ensure_roles(guild, role_names: Iterable[str]):
    created = []
    for name in role_names:
        if guild_get_role_by_name(guild, name) is None:
            role = await guild.create_role(name=name, mentionable=False, hoist=True)
            created.append(role.name)
    return created
