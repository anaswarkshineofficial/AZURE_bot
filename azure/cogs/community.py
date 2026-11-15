from __future__ import annotations

import re
import discord
from discord import app_commands
from discord.ext import commands

from azure.database import (
    initialize_community_tables, create_whitelist_application,
    set_whitelist_review_message, get_whitelist_application,
    update_whitelist_status, create_support_ticket, close_support_ticket,
)
from azure.permissions import user_is_admin

STAFF_ROLE_NAMES = {"Founder", "Co-Founder", "Head Admin", "Admin", "Moderator", "Support Team"}
MEMBER_ROLE_NAME = "Member"
UNVERIFIED_ROLE_NAME = "Unverified"
WHITELIST_ROLE_NAME = "Whitelisted"


def plain_name(name: str) -> str:
    return name.split("・", 1)[-1].strip().casefold()


def find_role(guild: discord.Guild, name: str):
    target = name.casefold()
    return next((r for r in guild.roles if plain_name(r.name) == target or r.name.casefold() == target), None)


def find_category(guild: discord.Guild, name: str):
    target = name.casefold()
    return next((c for c in guild.categories if plain_name(c.name) == target or c.name.casefold() == target), None)


def find_text_channel(guild: discord.Guild, name: str):
    target = name.casefold()
    return next((c for c in guild.text_channels if plain_name(c.name) == target or c.name.casefold() == target), None)


def staff_roles(guild: discord.Guild):
    return [r for r in guild.roles if plain_name(r.name) in {x.casefold() for x in STAFF_ROLE_NAMES}]


async def ensure_role(guild: discord.Guild, name: str, colour: int = 0x90A4AE):
    role = find_role(guild, name)
    if role:
        return role
    return await guild.create_role(name=name, colour=discord.Colour(colour),
                                   reason="AZURE community features setup")


async def ensure_text_channel(guild, name, category, overwrites=None, topic=None):
    channel = find_text_channel(guild, name)
    if channel:
        # Do not rewrite existing permission overwrites silently.
        return channel
    kwargs = {"category": category, "topic": topic,
              "reason": "AZURE community features setup"}
    # discord.py requires a mapping when `overwrites` is supplied;
    # omit the argument entirely for public/default-permission channels.
    if overwrites is not None:
        kwargs["overwrites"] = overwrites
    return await guild.create_text_channel(name, **kwargs)


class VerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Verify me", style=discord.ButtonStyle.success,
                       emoji="✅", custom_id="azure:verify")
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Use this button inside the server.", ephemeral=True)
            return
        member = interaction.user
        unverified = find_role(interaction.guild, UNVERIFIED_ROLE_NAME)
        member_role = find_role(interaction.guild, MEMBER_ROLE_NAME)
        if not member_role:
            await interaction.response.send_message("Member role is missing. Ask an administrator to run `/community_setup`.", ephemeral=True)
            return
        try:
            if unverified and unverified in member.roles:
                await member.remove_roles(unverified, reason="AZURE member verification")
            if member_role not in member.roles:
                await member.add_roles(member_role, reason="AZURE member verification")
            await interaction.response.send_message("✅ You are verified. Welcome to AZOR AHAI!", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("AZURE cannot assign these roles. Move its bot role above Member and Unverified.", ephemeral=True)


class WhitelistModal(discord.ui.Modal, title="AZOR AHAI Whitelist Application"):
    game_name = discord.ui.TextInput(label="FiveM character / in-game name", max_length=64)
    age = discord.ui.TextInput(label="Age", max_length=3)
    experience = discord.ui.TextInput(label="PvP experience", style=discord.TextStyle.paragraph, max_length=500)
    reason = discord.ui.TextInput(label="Why should we whitelist you?", style=discord.TextStyle.paragraph, max_length=800)

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Apply from inside the server.", ephemeral=True)
            return
        review_channel = find_text_channel(guild, "whitelist-review")
        if review_channel is None:
            await interaction.response.send_message("Whitelist review channel is missing. Ask an admin to run `/community_setup`.", ephemeral=True)
            return
        app_id = create_whitelist_application(
            guild.id, interaction.user.id, str(self.game_name), str(self.age),
            str(self.experience), str(self.reason),
        )
        embed = discord.Embed(title=f"📨 Whitelist application #{app_id}", colour=discord.Colour.orange())
        embed.add_field(name="Applicant", value=f"{interaction.user.mention}\n`{interaction.user.id}`", inline=False)
        embed.add_field(name="In-game name", value=str(self.game_name), inline=True)
        embed.add_field(name="Age", value=str(self.age), inline=True)
        embed.add_field(name="PvP experience", value=str(self.experience), inline=False)
        embed.add_field(name="Reason", value=str(self.reason), inline=False)
        embed.set_footer(text="Status: Pending staff review")
        message = await review_channel.send(embed=embed, view=WhitelistReviewView())
        set_whitelist_review_message(app_id, review_channel.id, message.id)
        await interaction.response.send_message(f"✅ Application **#{app_id}** submitted. Staff will review it.", ephemeral=True)


class WhitelistApplyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Apply for whitelist", style=discord.ButtonStyle.primary,
                       emoji="📝", custom_id="azure:whitelist_apply")
    async def apply(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(WhitelistModal())


class WhitelistReviewView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def _review(self, interaction: discord.Interaction, approved: bool):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("This action must be used in the server.", ephemeral=True)
            return
        if not (interaction.user.guild_permissions.manage_guild or any(r in staff_roles(interaction.guild) for r in interaction.user.roles)):
            await interaction.response.send_message("Only staff can review whitelist applications.", ephemeral=True)
            return
        message = interaction.message
        match = re.search(r"application #(\d+)", message.embeds[0].title or "", re.I) if message.embeds else None
        if not match:
            await interaction.response.send_message("Application ID could not be read.", ephemeral=True)
            return
        app_id = int(match.group(1))
        application = get_whitelist_application(app_id)
        if not application or application["status"] != "pending":
            await interaction.response.send_message("This application has already been reviewed or no longer exists.", ephemeral=True)
            return
        status = "approved" if approved else "rejected"
        update_whitelist_status(app_id, status)
        if approved:
            role = find_role(interaction.guild, WHITELIST_ROLE_NAME)
            member = interaction.guild.get_member(int(application["user_id"]))
            if role and member:
                try:
                    await member.add_roles(role, reason=f"Whitelist application #{app_id} approved")
                except discord.Forbidden:
                    await interaction.response.send_message("Application recorded, but AZURE cannot assign Whitelisted. Move its bot role above that role.", ephemeral=True)
                    return
        embed = message.embeds[0]
        embed.colour = discord.Colour.green() if approved else discord.Colour.red()
        embed.add_field(name="Review result", value=f"**{status.title()}** by {interaction.user.mention}", inline=False)
        await message.edit(embed=embed, view=None)
        member = interaction.guild.get_member(int(application["user_id"]))
        if member:
            try:
                await member.send(f"Your AZOR AHAI whitelist application **#{app_id}** was **{status}**.")
            except discord.Forbidden:
                pass
        await interaction.response.send_message(f"Application #{app_id} {status}.", ephemeral=True)

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success, emoji="✅",
                       custom_id="azure:whitelist_approve")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._review(interaction, True)

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.danger, emoji="❌",
                       custom_id="azure:whitelist_reject")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._review(interaction, False)


class TicketModal(discord.ui.Modal, title="AZOR AHAI Support Request"):
    subject = discord.ui.TextInput(label="Subject", max_length=100)
    details = discord.ui.TextInput(label="Describe your issue / report", style=discord.TextStyle.paragraph, max_length=1500)

    def __init__(self, ticket_type: str):
        super().__init__()
        self.ticket_type = ticket_type

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Open a ticket inside the server.", ephemeral=True)
            return
        category = find_category(guild, "SUPPORT")
        if category is None:
            await interaction.response.send_message("Support category is missing. Ask an admin to run `/community_setup`.", ephemeral=True)
            return
        # One open ticket per member and type; avoid accidental duplicates.
        existing = next((c for c in category.text_channels if c.topic and f"azure-owner:{interaction.user.id}" in c.topic and "azure-status:open" in c.topic), None)
        if existing:
            await interaction.response.send_message(f"You already have an open ticket: {existing.mention}", ephemeral=True)
            return
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True, embed_links=True),
        }
        for role in staff_roles(guild):
            overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_messages=True)
        bot_member = guild.me
        if bot_member:
            overwrites[bot_member] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_channels=True)
        safe = re.sub(r"[^a-z0-9-]", "-", str(self.subject).lower()).strip("-")[:24] or "ticket"
        channel = await guild.create_text_channel(
            name=f"{self.ticket_type}-{safe}"[:90], category=category,
            overwrites=overwrites,
            topic=f"azure-owner:{interaction.user.id} | azure-type:{self.ticket_type} | azure-status:open",
            reason=f"AZURE {self.ticket_type} ticket",
        )
        create_support_ticket(guild.id, channel.id, interaction.user.id, self.ticket_type)
        embed = discord.Embed(title=f"{self.ticket_type.replace('-', ' ').title()}",
                              description=str(self.details), colour=discord.Colour.red())
        embed.add_field(name="Opened by", value=interaction.user.mention)
        embed.add_field(name="Subject", value=str(self.subject))
        await channel.send(content=f"{interaction.user.mention} • Staff will assist you.", embed=embed, view=CloseTicketView())
        await interaction.response.send_message(f"🎫 Ticket created: {channel.mention}", ephemeral=True)


class SingleTicketPanelView(discord.ui.View):
    """A dedicated one-button panel for one request type."""
    def __init__(self, ticket_type: str, label: str, style: discord.ButtonStyle,
                 emoji: str, custom_id: str):
        super().__init__(timeout=None)
        self.ticket_type = ticket_type
        button = discord.ui.Button(label=label, style=style, emoji=emoji, custom_id=custom_id)
        button.callback = self.open_ticket
        self.add_item(button)

    async def open_ticket(self, interaction: discord.Interaction):
        await interaction.response.send_modal(TicketModal(self.ticket_type))


class TicketPanelView(SingleTicketPanelView):
    def __init__(self):
        super().__init__("support", "Open Support Ticket", discord.ButtonStyle.primary,
                         "🎫", "azure:ticket_support")


class PlayerReportPanelView(SingleTicketPanelView):
    def __init__(self):
        super().__init__("player-report", "Submit Player Report", discord.ButtonStyle.danger,
                         "🚨", "azure:ticket_report")


class BanAppealPanelView(SingleTicketPanelView):
    def __init__(self):
        super().__init__("ban-appeal", "Submit Ban Appeal", discord.ButtonStyle.secondary,
                         "⚖️", "azure:ticket_appeal")


class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close ticket", style=discord.ButtonStyle.danger,
                       emoji="🔒", custom_id="azure:ticket_close")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel) or not channel.topic or "azure-owner:" not in channel.topic:
            await interaction.response.send_message("This is not an AZURE ticket channel.", ephemeral=True)
            return
        owner_match = re.search(r"azure-owner:(\d+)", channel.topic)
        owner_id = int(owner_match.group(1)) if owner_match else 0
        is_staff = isinstance(interaction.user, discord.Member) and (
            interaction.user.guild_permissions.manage_guild or
            any(r in staff_roles(interaction.guild) for r in interaction.user.roles)
        )
        if interaction.user.id != owner_id and not is_staff:
            await interaction.response.send_message("Only the ticket owner or staff can close this ticket.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        close_support_ticket(channel.id)
        if interaction.guild:
            overwrites = channel.overwrites
            owner = interaction.guild.get_member(owner_id)
            if owner:
                overwrites[owner] = discord.PermissionOverwrite(view_channel=True, send_messages=False, read_message_history=True)
            await channel.edit(overwrites=overwrites, name=f"closed-{channel.name}"[:100],
                               topic=re.sub(r"azure-status:open", "azure-status:closed", channel.topic or ""),
                               reason="AZURE ticket closed")
        await interaction.followup.send("Ticket closed. Staff can delete this channel when appropriate.", ephemeral=True)


class CommunityCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        initialize_community_tables()
        self.bot.add_view(VerifyView())
        self.bot.add_view(WhitelistApplyView())
        self.bot.add_view(WhitelistReviewView())
        self.bot.add_view(TicketPanelView())
        self.bot.add_view(PlayerReportPanelView())
        self.bot.add_view(BanAppealPanelView())
        self.bot.add_view(CloseTicketView())

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        unverified = find_role(member.guild, UNVERIFIED_ROLE_NAME)
        if unverified:
            try:
                await member.add_roles(unverified, reason="AZURE: new member pending verification")
            except discord.Forbidden:
                pass
        welcome = find_text_channel(member.guild, "welcome")
        if welcome:
            embed = discord.Embed(
                title="Welcome to AZOR AHAI! 🔴⚪",
                description=f"Welcome {member.mention}! Please read the rules and verify to unlock the community.",
                colour=discord.Colour.red(),
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            await welcome.send(embed=embed)

    @app_commands.command(name="community_setup", description="Install welcome, verification, whitelist and support panels.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def community_setup(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Run this inside your Discord server.", ephemeral=True)
            return
        me = guild.me
        if not me or not me.guild_permissions.manage_roles or not me.guild_permissions.manage_channels:
            await interaction.response.send_message("AZURE needs Manage Roles and Manage Channels.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            # Roles used by the three features.
            unverified = await ensure_role(guild, UNVERIFIED_ROLE_NAME, 0x78909C)
            await ensure_role(guild, MEMBER_ROLE_NAME, 0x90A4AE)
            await ensure_role(guild, WHITELIST_ROLE_NAME, 0x00C853)

            # Use the existing template categories where possible; create only missing feature channels.
            info = find_category(guild, "INFORMATION")
            if info is None:
                info = await guild.create_category("📌・INFORMATION", reason="AZURE community setup")
            support = find_category(guild, "SUPPORT")
            if support is None:
                support = await guild.create_category("🎫・SUPPORT", reason="AZURE community setup")
            staff = find_category(guild, "STAFF") or find_category(guild, "STAFF HQ")
            if staff is None:
                staff = await guild.create_category("🛡️・STAFF", reason="AZURE community setup")

            # Staff review channel is private to staff roles and the bot.
            review_overwrites = {guild.default_role: discord.PermissionOverwrite(view_channel=False)}
            for role in staff_roles(guild):
                review_overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
            review_overwrites[me] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
            review = await ensure_text_channel(guild, "whitelist-review", staff, review_overwrites)

            welcome = await ensure_text_channel(guild, "welcome", info)
            verify = await ensure_text_channel(guild, "verify", info)
            whitelist_apply = await ensure_text_channel(guild, "whitelist-application", info)
            tickets = await ensure_text_channel(guild, "create-ticket", support)
            player_reports = await ensure_text_channel(guild, "player-reports", support)
            ban_appeals = await ensure_text_channel(guild, "ban-appeals", support)

            # Add a role-level deny for Unverified to existing categories, then explicit allows
            # on welcome/verify/whitelist application so unverified users have a limited entry point.
            for category in guild.categories:
                try:
                    ow = category.overwrites
                    ow[unverified] = discord.PermissionOverwrite(view_channel=False)
                    if category.id == info.id:
                        ow[unverified] = discord.PermissionOverwrite(view_channel=True, read_message_history=True, send_messages=False)
                    await category.edit(overwrites=ow, reason="AZURE: restrict unverified members")
                except discord.Forbidden:
                    pass
            for channel in (welcome, verify, whitelist_apply):
                ow = channel.overwrites
                ow[unverified] = discord.PermissionOverwrite(view_channel=True, read_message_history=True, send_messages=False)
                await channel.edit(overwrites=ow, reason="AZURE: verification entry channels")
            # Verification channel must permit button use (no message posting needed).
            # Post panels once per setup invocation; older panels remain functional.
            welcome_embed = discord.Embed(
                title="Welcome to AZOR AHAI 🔴⚪",
                description="Read the rules, verify your account, and apply for whitelist access.",
                colour=discord.Colour.red(),
            )
            await welcome.send(embed=welcome_embed)
            await verify.send(
                embed=discord.Embed(title="Server Verification", description="Press the button below to unlock the Member channels.", colour=discord.Colour.green()),
                view=VerifyView(),
            )
            await whitelist_apply.send(
                embed=discord.Embed(title="Whitelist Application", description="Already verified? Submit your FiveM details for staff review. Approval is required before whitelist access is granted.", colour=discord.Colour.red()),
                view=WhitelistApplyView(),
            )
            # Remove the previous combined three-button panel from create-ticket,
            # while preserving all other messages in that channel.
            async for old_message in tickets.history(limit=50):
                if old_message.author.id == self.bot.user.id and any(
                    (embed.title or "") == "AZOR AHAI Support Center"
                    for embed in old_message.embeds
                ):
                    await old_message.delete()

            await tickets.send(
                embed=discord.Embed(title="AZOR AHAI Support", description="Need help with the server? Open a private support ticket below. AZURE will create a channel visible only to you and staff.", colour=discord.Colour.red()),
                view=TicketPanelView(),
            )
            await player_reports.send(
                embed=discord.Embed(title="AZOR AHAI Player Reports", description="Report a player for rule violations. Include their name, what happened, and any evidence you have. Your report will be sent to a private staff-review ticket.", colour=discord.Colour.red()),
                view=PlayerReportPanelView(),
            )
            await ban_appeals.send(
                embed=discord.Embed(title="AZOR AHAI Ban Appeals", description="If you believe your ban was a mistake or want to appeal it, submit your details below. Your appeal will be sent to a private staff-review ticket.", colour=discord.Colour.orange()),
                view=BanAppealPanelView(),
            )
            await interaction.followup.send(
                "✅ **AZURE community update installed.**\n"
                f"• Welcome: {welcome.mention}\n• Verification: {verify.mention}\n"
                f"• Whitelist applications: {whitelist_apply.mention}\n"
                f"• Private staff review: {review.mention}\n• Support panel: {tickets.mention}\n\n"
                "Features 4 (kill feed) and 5 (FiveM status/player count) were not changed.",
                ephemeral=True,
            )
        except discord.Forbidden:
            await interaction.followup.send("Discord denied a setup action. Check Manage Roles, Manage Channels, and AZURE's role position.", ephemeral=True)
        except Exception as exc:
            await interaction.followup.send(f"❌ Community setup failed: `{type(exc).__name__}: {exc}`", ephemeral=True)
            raise


async def setup(bot):
    await bot.add_cog(CommunityCog(bot))
