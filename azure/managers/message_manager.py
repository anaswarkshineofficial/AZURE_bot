from __future__ import annotations

import discord


async def publish_welcome_messages(guild, channel_name: str, message_text: str):
    channel = discord.utils.get(guild.text_channels, name=channel_name)
    if channel is None:
        return None
    return await channel.send(message_text)
