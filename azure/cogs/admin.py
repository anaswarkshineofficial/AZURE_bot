from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from azure.database import list_backups, save_backup
from azure.modules.backups import BackupModule
from azure.modules.cleanup import (
    cleanup_inventory, create_cleanup_backup, delete_azure_resources,
    recover_azure_resources_from_audit_log,
)


class AzureCleanupConfirm(discord.ui.View):
    def __init__(self, guild_id: int, user_id: int):
        super().__init__(timeout=60)
        self.guild_id = guild_id
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Only the administrator who requested this cleanup can confirm it.", ephemeral=True)
            return False
        if interaction.guild is None or interaction.guild.id != self.guild_id:
            await interaction.response.send_message("This confirmation belongs to another server.", ephemeral=True)
            return False
        if not (interaction.user.guild_permissions.manage_guild or interaction.user.guild_permissions.administrator):
            await interaction.response.send_message("Manage Server permission is required.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Confirm AZURE cleanup", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        guild = interaction.guild
        if guild is None:
            await interaction.followup.send("Server unavailable.", ephemeral=True)
            return
        # A fresh backup is taken immediately before deletion.
        backup_id = create_cleanup_backup(guild)
        result = await delete_azure_resources(guild)
        for child in self.children:
            child.disabled = True
        try:
            await interaction.message.edit(view=self)
        except discord.HTTPException:
            pass
        summary = (
            f"AZURE cleanup finished. Deleted {result['deleted_channels']} channels/categories "
            f"and {result['deleted_roles']} AZURE-created roles. Backup: #{backup_id}."
        )
        if result["skipped"]:
            summary += "\nSkipped: " + "; ".join(result["skipped"][:8])
        await interaction.followup.send(summary, ephemeral=True)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="AZURE cleanup cancelled. Nothing was deleted.", view=self)


class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="server_health", description="Show a basic server health report.")
    async def server_health(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("This command can only run inside a server.", ephemeral=True)
            return
        await interaction.response.send_message(
            f"Server health report for {interaction.guild.name}: {len(interaction.guild.roles)} roles, {len(interaction.guild.channels)} channels.",
            ephemeral=True,
        )

    @app_commands.command(name="backup_config", description="Create a backup snapshot for this server configuration.")
    async def backup_config(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("This command can only run inside a server.", ephemeral=True)
            return
        snapshot = BackupModule().snapshot(interaction.guild, "manual_backup")
        save_backup(str(interaction.guild.id), snapshot)
        await interaction.response.send_message("Configuration backup created.", ephemeral=True)

    @app_commands.command(name="restore_preview", description="Preview stored backups.")
    async def restore_preview(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("This command can only run inside a server.", ephemeral=True)
            return
        backups = list_backups(str(interaction.guild.id))
        if not backups:
            await interaction.response.send_message("No backups found.", ephemeral=True)
            return
        summary = "; ".join(f"#{row['id']} @ {row['created_at']}" for row in backups[:5])
        await interaction.response.send_message(f"Recent backups: {summary}", ephemeral=True)


    async def _show_clear_preview(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("Use this command inside a server.", ephemeral=True)
            return
        if not (interaction.user.guild_permissions.manage_guild or interaction.user.guild_permissions.administrator):
            await interaction.response.send_message("Manage Server permission is required.", ephemeral=True)
            return
        inventory = cleanup_inventory(interaction.guild)
        channel_names = [channel.name for channel in inventory["channels"]]
        role_names = [role.name for role in inventory["roles"]]
        embed = discord.Embed(title="AZURE cleanup preview", color=0xEF233C)
        embed.description = (
            "Only resources recorded in AZURE's ownership registry are eligible. "
            "Existing/manual resources are not selected. A backup is created immediately before deletion."
        )
        embed.add_field(name=f"Channels & categories ({len(channel_names)})", value="\n".join(channel_names[:20]) or "None", inline=False)
        embed.add_field(name=f"AZURE-created roles ({len(role_names)})", value="\n".join(role_names[:20]) or "None", inline=False)
        if not channel_names and not role_names:
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        await interaction.response.send_message(
            embed=embed,
            view=AzureCleanupConfirm(interaction.guild.id, interaction.user.id),
            ephemeral=True,
        )

    @app_commands.command(name="recover_azure_resources", description="Find resources AZURE created using Discord's audit log and register them for safe cleanup.")
    async def recover_azure_resources(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("Use this command inside a server.", ephemeral=True)
            return
        if not (interaction.user.guild_permissions.manage_guild or interaction.user.guild_permissions.administrator):
            await interaction.response.send_message("Manage Server permission is required.", ephemeral=True)
            return
        if self.bot.user is None:
            await interaction.response.send_message("AZURE is not fully ready yet. Try again shortly.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            recovered = await recover_azure_resources_from_audit_log(interaction.guild, self.bot.user.id)
        except discord.Forbidden:
            await interaction.followup.send("Discord denied audit-log access. Check AZURE's View Audit Log permission and role settings.", ephemeral=True)
            return
        except PermissionError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return
        except discord.HTTPException as exc:
            await interaction.followup.send(f"Could not read the audit log: {type(exc).__name__}.", ephemeral=True)
            return

        details = []
        for label, key in (("Categories", "categories"), ("Channels", "channels"), ("Roles", "roles")):
            names = recovered[key]
            details.append(f"**{label} ({len(names)})**\n" + ("\n".join(names[:15]) if names else "None"))
        message = (
            f"Audit-log recovery complete. Registered **{recovered['total']}** verified resources created by AZURE.\n\n"
            + "\n\n".join(details)
            + "\n\nRun `/clear_preview` to inspect the recovered resources. Nothing has been deleted."
        )
        await interaction.followup.send(message[:1900], ephemeral=True)

    @app_commands.command(name="clear_preview", description="Preview only the channels and roles AZURE has created.")
    async def clear_preview(self, interaction: discord.Interaction):
        await self._show_clear_preview(interaction)

    @app_commands.command(name="clear_server", description="Delete only AZURE-created channels, categories and roles after confirmation.")
    async def clear_server(self, interaction: discord.Interaction):
        await self._show_clear_preview(interaction)


async def setup(bot):
    await bot.add_cog(AdminCog(bot))
