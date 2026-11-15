from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands


class ServerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="role_inspect", description="Inspect the server role hierarchy.")
    async def role_inspect(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("This command can only run in a server.", ephemeral=True)
            return
        roles = ", ".join(role.name for role in interaction.guild.roles[:10])
        await interaction.response.send_message(f"Current roles: {roles}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(ServerCog(bot))
