from __future__ import annotations

THEMES = {
    "azor_redline": {
        "label": "AZOR REDLINE",
        "primary": 0xEF233C,
        "secondary": 0xFFFFFF,
        "embed": 0xEF233C,
        "roles": {
            "Founder": 0xFF1744, "Co-Founder": 0x9C27B0, "Head Admin": 0xFF6D00,
            "Admin": 0xE53935, "Moderator": 0x2979FF, "Support Team": 0x00B8D4,
            "VIP": 0xFFD600, "Whitelisted": 0x00C853, "PvP Veteran": 0x7C4DFF,
            "Member": 0x90A4AE, "Bots": 0x536DFE, "Staff": 0xE53935,
            "Coach": 0xFF6D00,
        },
    },
    "cyberpunk": {
        "label": "CYBERPUNK", "primary": 0xB026FF, "secondary": 0x00E5FF, "embed": 0xB026FF,
        "roles": {"Founder":0xFF2E88,"Co-Founder":0xB026FF,"Head Admin":0xFF7A00,"Admin":0xFF3D71,"Moderator":0x00B8D9,"Support Team":0x00E5FF,"VIP":0xF9E900,"Whitelisted":0x00FF9C,"PvP Veteran":0x8A5CFF,"Member":0xAAB7C4,"Bots":0x536DFE,"Staff":0xFF3D71,"Coach":0x00E5FF},
    },
    "royal_elite": {
        "label": "ROYAL ELITE", "primary": 0xD4AF37, "secondary": 0xE8E8E8, "embed": 0xD4AF37,
        "roles": {"Founder":0xD4AF37,"Co-Founder":0xB08D57,"Head Admin":0x8E44AD,"Admin":0xC0392B,"Moderator":0x2980B9,"Support Team":0x16A085,"VIP":0xF1C40F,"Whitelisted":0x27AE60,"PvP Veteran":0x6C5CE7,"Member":0xBDC3C7,"Bots":0x34495E,"Staff":0x8E44AD,"Coach":0x2980B9},
    },
    "frost": {
        "label": "FROST", "primary": 0x56CCF2, "secondary": 0xFFFFFF, "embed": 0x56CCF2,
        "roles": {"Founder":0x00A8E8,"Co-Founder":0x7B61FF,"Head Admin":0x4D96FF,"Admin":0x2979FF,"Moderator":0x00B8D4,"Support Team":0x80DEEA,"VIP":0xFDD835,"Whitelisted":0x00C853,"PvP Veteran":0x9575CD,"Member":0xB0BEC5,"Bots":0x536DFE,"Staff":0x2979FF,"Coach":0x00B8D4},
    },
    "tactical": {
        "label": "TACTICAL", "primary": 0x556B2F, "secondary": 0xD7D7C8, "embed": 0x556B2F,
        "roles": {"Founder":0xC0392B,"Co-Founder":0x8E44AD,"Head Admin":0xD35400,"Admin":0xB03A2E,"Moderator":0x2874A6,"Support Team":0x117864,"VIP":0xB7950B,"Whitelisted":0x4D7C0F,"PvP Veteran":0x6C5CE7,"Member":0xAAB7B8,"Bots":0x34495E,"Staff":0x2874A6,"Coach":0x117864},
    },
}

ROLE_EMOJIS = {
    "Founder":"👑", "Co-Founder":"💠", "Head Admin":"🔱", "Admin":"⚜️",
    "Moderator":"🛡️", "Support Team":"🎧", "VIP":"💎", "Whitelisted":"✅",
    "PvP Veteran":"⚔️", "Member":"🎮", "Bots":"🤖", "Staff":"🛡️", "Coach":"🎯",
}
CATEGORY_EMOJIS = {
    "INFORMATION":"📌", "INFO":"📌", "WHITELISTED":"🔐", "PVP COMMUNITY":"⚔️",
    "SUPPORT":"🛟", "VIP":"💎", "STAFF":"🛡️", "VOICE":"🎧", "GENERAL":"🌐",
    "ROLEPLAY":"🎭", "MATCHDAY":"🏆", "COMMUNITY":"💬",
}
CHANNEL_EMOJIS = {
    "welcome":"👋", "announcements":"📢", "rules":"📜", "server-information":"ℹ️",
    "how-to-connect":"🔌", "get-roles":"🎭", "server-ip":"🌐",
    "whitelist-announcements":"📢", "player-updates":"📰", "whitelisted-lobby":"🔊",
    "pvp-chat":"💬", "kill-feed":"🎯", "leaderboard":"🏆", "clips-and-highlights":"🎬",
    "screenshots":"📸", "find-a-team":"🤝", "create-ticket":"🎫", "player-reports":"🚨",
    "ban-appeals":"⚖️", "suggestions":"💡", "technical-support":"🧰",
    "vip-announcements":"📢", "vip-chat":"💬", "vip-voice":"🔊", "staff-chat":"💬",
    "staff-logs":"📋", "moderation-logs":"🛡️", "admin-alerts":"🚨",
    "staff-applications":"📝", "staff-voice":"🔊", "general-lobby":"🔊",
    "pvp-squad-1":"⚔️", "pvp-squad-2":"⚔️", "pvp-squad-3":"⚔️", "afk":"💤",
    "general":"💬", "lobby":"🔊", "rp-chat":"🎭", "voice-lobby":"🔊",
    "team-chat":"💬", "voice-room":"🎧", "lounge":"🛋️",
}

def clean_name(name: str) -> str:
    import re
    value = name.strip()
    # Strip one or more leading emoji/icon prefixes and their separators.
    while True:
        updated = re.sub(r"^[^\w]+(?:[・|│]\s*|\s+)", "", value, count=1, flags=re.UNICODE).strip()
        if updated == value:
            break
        value = updated
    return value.casefold()

def styled_name(name: str, emoji: str) -> str:
    if clean_name(name) == name.casefold():
        return f"{emoji}・{name}"
    return name


async def apply_theme_to_guild(guild, theme_name: str):
    """Apply a theme to every editable non-default role, category and channel.

    Role hierarchy and integration-managed restrictions are respected. Existing
    role permissions and channel permission overwrites are not modified.
    """
    import re
    import discord

    theme = THEMES[theme_name]
    warnings = []
    changed_roles = 0
    changed_channels = 0
    already_styled = 0
    skipped_roles = 0
    bot_top = guild.me.top_role if guild.me else None

    palette = list(theme["roles"].values()) or [theme["primary"], theme["secondary"]]
    role_items = list(guild.roles)
    for index, role in enumerate(role_items):
        if role.is_default() or role.managed:
            continue
        if bot_top is None or role >= bot_top:
            skipped_roles += 1
            warnings.append(f"Role skipped by hierarchy: {role.name}")
            continue

        plain = clean_name(role.name)
        role_key = next((k for k in theme["roles"] if k.casefold() == plain.casefold()), None)
        emoji_key = next((k for k in ROLE_EMOJIS if k.casefold() == plain.casefold()), None)
        color = theme["roles"].get(role_key) if role_key else palette[index % len(palette)]
        emoji = ROLE_EMOJIS.get(emoji_key) if emoji_key else "🔹"
        display = plain if plain else role.name
        target_name = f"{emoji}・{display}"
        if len(target_name) > 100:
            target_name = target_name[:100]
        if role.name == target_name and role.colour.value == color:
            already_styled += 1
            continue
        try:
            await role.edit(
                name=target_name,
                colour=discord.Colour(color),
                reason=f"AZURE: apply {theme['label']} theme",
            )
            changed_roles += 1
        except discord.Forbidden:
            skipped_roles += 1
            warnings.append(f"Role not editable: {role.name}")
        except discord.HTTPException as exc:
            warnings.append(f"Role update failed for {role.name}: {exc.__class__.__name__}")

    # Every category is styled, including categories not in the preset map.
    for category in list(guild.categories):
        plain = clean_name(category.name)
        emoji = CATEGORY_EMOJIS.get(plain.upper(), "📁")
        target_name = f"{emoji}・{plain.upper() or 'CATEGORY'}"
        if category.name == target_name:
            already_styled += 1
            continue
        try:
            await category.edit(
                name=target_name[:100],
                reason=f"AZURE: apply {theme['label']} theme",
            )
            changed_channels += 1
        except discord.Forbidden:
            warnings.append(f"Category not editable: {category.name}")
        except discord.HTTPException as exc:
            warnings.append(f"Category update failed for {category.name}: {exc.__class__.__name__}")

    # Style all channel types, not only names known to the original template.
    for channel in list(guild.channels):
        if isinstance(channel, discord.CategoryChannel):
            continue
        plain = clean_name(channel.name)
        if isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
            fallback = "🔊" if isinstance(channel, discord.VoiceChannel) else "🎙️"
        elif isinstance(channel, discord.ForumChannel):
            fallback = "🧵"
        else:
            fallback = "💬"
        emoji = CHANNEL_EMOJIS.get(plain, fallback)
        target_name = f"{emoji}・{plain or 'channel'}"
        if channel.name == target_name:
            already_styled += 1
            continue
        try:
            await channel.edit(
                name=target_name[:100],
                reason=f"AZURE: apply {theme['label']} theme",
            )
            changed_channels += 1
        except discord.Forbidden:
            warnings.append(f"Channel not editable: {channel.name}")
        except discord.HTTPException as exc:
            warnings.append(f"Channel update failed for {channel.name}: {exc.__class__.__name__}")

    return {
        "roles_updated": changed_roles,
        "channels_updated": changed_channels,
        "roles_skipped": skipped_roles,
        "already_styled": already_styled,
        "warnings": warnings,
    }
