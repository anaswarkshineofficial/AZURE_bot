from __future__ import annotations

import discord


async def ensure_category(guild, category_name: str):
    category = discord.utils.get(guild.categories, name=category_name)
    if category is None:
        category = await guild.create_category(category_name)
    return category


async def ensure_text_channel(guild, category, channel_name: str, topic: str = ""):
    channel = discord.utils.get(guild.text_channels, name=channel_name)
    if channel is None:
        channel = await guild.create_text_channel(channel_name, category=category, topic=topic)
    if category and channel.category_id != category.id:
        await channel.edit(category=category)
    return channel


async def ensure_voice_channel(guild, category, channel_name: str):
    channel = discord.utils.get(guild.voice_channels, name=channel_name)
    if channel is None:
        channel = await guild.create_voice_channel(channel_name, category=category)
    if category and channel.category_id != category.id:
        await channel.edit(category=category)
    return channel
