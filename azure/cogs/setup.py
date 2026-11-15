from __future__ import annotations

import json
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from azure.build import get_builder
from azure.database import (
    get_guild_template, get_guild_theme, log_event,
    set_guild_template, set_guild_theme,
)
from azure.permissions import bot_has_required_permissions, user_is_admin
from azure.themes import THEMES, apply_theme_to_guild

TEMPLATES = {"pvp", "rp", "gaming", "esports", "community"}


class ThemeConfirmView(discord.ui.View):
    def __init__(self, cog, guild_id: int, requester_id: int, theme_key: str):
        super().__init__(timeout=60)
        self.cog = cog
        self.guild_id = guild_id
        self.requester_id = requester_id
        self.theme_key = theme_key

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message("Only the person who requested this preview can confirm it.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Confirm theme", style=discord.ButtonStyle.danger, emoji="🎨")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild is None or interaction.guild.id != self.guild_id:
            await interaction.response.send_message("This confirmation belongs to another server.", ephemeral=True)
            return
        if not user_is_admin(interaction.user):
            await interaction.response.send_message("Administrator permission is required.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            result = await apply_theme_to_guild(interaction.guild, self.theme_key)
            set_guild_theme(interaction.guild.id, self.theme_key)
            log_event(interaction.guild.id, "theme", f"Applied theme {self.theme_key}")
            for child in self.children:
                child.disabled = True
            await interaction.edit_original_response(view=self)
            msg = (
                f"✅ Applied **{THEMES[self.theme_key]['label']}**. "
                f"Updated **{result['roles_updated']} roles** and "
                f"**{result['channels_updated']} categories/channels**. "
                f"Skipped **{result['roles_skipped']} roles**; "
                f"already styled: **{result['already_styled']}**."
            )
            if result["warnings"]:
                msg += "\n\n**Skipped / warnings:**\n" + "\n".join(f"• {w}" for w in result["warnings"][:15])
            await interaction.followup.send(msg, ephemeral=True)
        except Exception as exc:
            await interaction.followup.send(f"Theme apply failed: `{type(exc).__name__}: {exc}`", ephemeral=True)
            raise

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="Theme change cancelled. Nothing was changed.", view=self)


class SetupCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _run_template(self, interaction: discord.Interaction, template_name: str):
        if interaction.guild is None:
            await interaction.response.send_message("Use this command inside a server.", ephemeral=True)
            return
        if not user_is_admin(interaction.user):
            await interaction.response.send_message("Only server administrators can run AZURE setup.", ephemeral=True)
            return
        ok, missing = bot_has_required_permissions(interaction.guild)
        if not ok:
            await interaction.response.send_message(
                f"AZURE is missing: {', '.join(missing)}", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            builder = get_builder(interaction.guild, interaction.user, template_name)
            report = await builder.run()
            set_guild_template(interaction.guild.id, template_name)
            log_event(interaction.guild.id, "setup", f"Configured {template_name} using {report.get('theme', 'theme')}")
            warnings = report.get("warnings", [])
            msg = (
                f"✅ **{report.get('template', template_name)} setup complete**\n"
                f"Theme: **{report.get('theme', 'AZOR REDLINE')}**\n"
                f"Categories: {len(report.get('categories', []))} • New roles: {len(report.get('roles', []))}"
            )
            if warnings:
                msg += "\n\n**Skipped / warnings:**\n" + "\n".join(f"• {w}" for w in warnings[:10])
            await interaction.followup.send(msg, ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send(
                "Discord denied an operation. Check Manage Roles/Manage Channels and move AZURE's bot role above the roles it must edit. Protected roles will be skipped.",
                ephemeral=True,
            )
        except Exception as exc:
            await interaction.followup.send(f"❌ Setup failed: `{type(exc).__name__}: {exc}`", ephemeral=True)
            raise

    @app_commands.command(name="setup_pvp", description="Build the AZOR AHAI PvP server.")
    async def setup_pvp(self, interaction: discord.Interaction):
        await self._run_template(interaction, "pvp")

    @app_commands.command(name="setup_rp", description="Build a roleplay server.")
    async def setup_rp(self, interaction: discord.Interaction):
        await self._run_template(interaction, "rp")

    @app_commands.command(name="setup_gaming", description="Build a gaming server.")
    async def setup_gaming(self, interaction: discord.Interaction):
        await self._run_template(interaction, "gaming")

    @app_commands.command(name="setup_esports", description="Build an esports server.")
    async def setup_esports(self, interaction: discord.Interaction):
        await self._run_template(interaction, "esports")

    @app_commands.command(name="setup_community", description="Build a community server.")
    async def setup_community(self, interaction: discord.Interaction):
        await self._run_template(interaction, "community")

    @app_commands.command(name="custom_build", description="Build using a supported template.")
    @app_commands.describe(template_name="pvp, rp, gaming, esports or community")
    async def custom_build(self, interaction: discord.Interaction, template_name: str):
        template_name = template_name.lower().strip()
        if template_name not in TEMPLATES:
            await interaction.response.send_message("Choose pvp, rp, gaming, esports or community.", ephemeral=True)
            return
        await self._run_template(interaction, template_name)

    @app_commands.command(name="server_preview", description="Preview a server template.")
    @app_commands.describe(template_name="Template to preview")
    async def server_preview(self, interaction: discord.Interaction, template_name: str):
        template_name = template_name.lower().strip()
        if template_name not in TEMPLATES:
            await interaction.response.send_message("Unsupported template.", ephemeral=True)
            return
        template_path = Path(__file__).resolve().parent.parent / "templates" / f"{template_name}.json"
        data = json.loads(template_path.read_text(encoding="utf-8"))
        categories = ", ".join(c["name"] for c in data.get("categories", []))
        theme = THEMES[get_guild_theme(interaction.guild.id)]["label"] if interaction.guild else "AZOR REDLINE"
        await interaction.response.send_message(
            f"**{data['name']}**\nTheme: **{theme}**\nCategories: {categories}",
            ephemeral=True,
        )

    @app_commands.command(name="theme_list", description="List all AZURE visual themes.")
    async def theme_list(self, interaction: discord.Interaction):
        lines = [f"🎨 **{t['label']}** — `{key}`" for key, t in THEMES.items()]
        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    @app_commands.command(name="theme_preview", description="Preview a theme without changing the server.")
    @app_commands.describe(theme_name="azor_redline, cyberpunk, royal_elite, frost or tactical")
    async def theme_preview(self, interaction: discord.Interaction, theme_name: str):
        key = theme_name.lower().strip()
        theme = THEMES.get(key)
        if not theme:
            await interaction.response.send_message("Unknown theme. Use `/theme_list`.", ephemeral=True)
            return
        embed = discord.Embed(
            title=f"🎨 {theme['label']}",
            description="Theme preview only. No server changes have been made.",
            colour=discord.Colour(theme["embed"]),
        )
        embed.add_field(name="Primary", value=f"`#{theme['primary']:06X}`", inline=True)
        embed.add_field(name="Secondary", value=f"`#{theme['secondary']:06X}`", inline=True)
        embed.add_field(
            name="Role palette",
            value="\n".join(f"• **{name}** — `#{color:06X}`" for name, color in list(theme["roles"].items())[:12]),
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="theme_apply", description="Preview and confirm a complete visual theme.")
    @app_commands.describe(theme_name="Theme key from /theme_list")
    async def theme_apply(self, interaction: discord.Interaction, theme_name: str):
        if interaction.guild is None:
            await interaction.response.send_message("Use this command inside a server.", ephemeral=True)
            return
        if not user_is_admin(interaction.user):
            await interaction.response.send_message("Only server administrators can apply themes.", ephemeral=True)
            return
        key = theme_name.lower().strip()
        if key not in THEMES:
            await interaction.response.send_message("Unknown theme. Use `/theme_list`.", ephemeral=True)
            return
        theme = THEMES[key]
        embed = discord.Embed(
            title=f"Confirm {theme['label']}",
            description="This will style every eligible role, category and channel with this theme's colors and emoji prefixes. Protected/higher roles are skipped. Existing permissions are not changed.",
            colour=discord.Colour(theme["embed"]),
        )
        embed.add_field(name="Role colors", value=f"{len(theme['roles'])} palette entries", inline=True)
        embed.add_field(name="Primary accent", value=f"#{theme['primary']:06X}", inline=True)
        await interaction.response.send_message(
            embed=embed,
            view=ThemeConfirmView(self, interaction.guild.id, interaction.user.id, key),
            ephemeral=True,
        )

    @app_commands.command(name="theme_reset", description="Preview and confirm reset to AZOR REDLINE.")
    async def theme_reset(self, interaction: discord.Interaction):
        if interaction.guild is None or not user_is_admin(interaction.user):
            await interaction.response.send_message("Only server administrators can reset a server theme.", ephemeral=True)
            return
        theme = THEMES["azor_redline"]
        embed = discord.Embed(
            title="Reset to AZOR REDLINE?",
            description="Preview the default AZOR REDLINE identity. No changes happen until you confirm.",
            colour=discord.Colour(theme["embed"]),
        )
        await interaction.response.send_message(
            embed=embed,
            view=ThemeConfirmView(self, interaction.guild.id, interaction.user.id, "azor_redline"),
            ephemeral=True,
        )



async def setup(bot):
    await bot.add_cog(SetupCog(bot))
