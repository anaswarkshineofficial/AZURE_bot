from __future__ import annotations

import discord


async def apply_channel_overrides(channel, allow_rules=None, deny_rules=None):
    allow_rules = allow_rules or {}
    deny_rules = deny_rules or {}
    overwrites = channel.overwrites
    for target, allow in allow_rules.items():
        if isinstance(target, discord.Role):
            overwrites[target] = discord.PermissionOverwrite(**allow)
    for target, deny in deny_rules.items():
        if isinstance(target, discord.Role):
            overwrites[target] = discord.PermissionOverwrite(**deny)
    await channel.edit(overwrites=overwrites)
