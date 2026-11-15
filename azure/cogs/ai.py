from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from azure.ai.local_ai import LocalAIClient


class AICog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ai = LocalAIClient()

    @app_commands.command(name="ai_preview", description="Preview AI-generated actions without executing changes.")
    @app_commands.describe(prompt="Describe the admin action to preview")
    async def ai_preview(self, interaction: discord.Interaction, prompt: str):
        preview = self.ai.generate_preview(prompt)
        await interaction.response.send_message(f"Preview: ```json\n{preview['json']}\n```", ephemeral=True)


async def setup(bot):
    await bot.add_cog(AICog(bot))
