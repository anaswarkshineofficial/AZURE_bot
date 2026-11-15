from __future__ import annotations

import discord

from azure.database import (
    track_managed_resource, get_guild_theme, set_guild_theme,
)
from azure.themes import (
    THEMES, ROLE_EMOJIS, CATEGORY_EMOJIS, CHANNEL_EMOJIS,
    clean_name, styled_name,
)


class BaseBuilder:
    def __init__(self, guild, admin_user, template_name):
        self.guild = guild
        self.admin_user = admin_user
        self.template_name = template_name
        from azure.config import BASE_DIR
        import json
        template_path = BASE_DIR / "azure" / "templates" / f"{template_name}.json"
        with template_path.open("r", encoding="utf-8") as handle:
            self.template = json.load(handle)
        self.theme_name = get_guild_theme(guild.id)
        self.theme = THEMES.get(self.theme_name, THEMES["azor_redline"])
        self.warnings = []
        self.role_objects = {}

    def _find_role(self, name):
        for role in self.guild.roles:
            if clean_name(role.name) == name.casefold():
                return role
        return None

    async def _ensure_roles(self):
        created = []
        top_role = self.guild.me.top_role if self.guild.me else None
        for spec in self.template.get("roles", []):
            name = spec["name"]
            role = self._find_role(name)
            color = self.theme["roles"].get(name, self.theme["secondary"])
            emoji = ROLE_EMOJIS.get(name, "🔹")
            styled = f"{emoji}・{name}"
            if role is None:
                role = await self.guild.create_role(
                    name=styled, colour=discord.Colour(color),
                    hoist=True, mentionable=False,
                    reason=f"AZURE: create {self.template_name} role",
                )
                track_managed_resource(self.guild.id, "role", role.id, role.name)
                created.append(role.name)
            elif role.managed:
                self.warnings.append(f"Skipped integration-managed role {role.name}")
            elif top_role is None or role >= top_role:
                self.warnings.append(f"Skipped role above AZURE: {role.name}")
            else:
                try:
                    # Preserve all existing role permissions; update visual identity only.
                    await role.edit(name=styled, colour=discord.Colour(color),
                                    reason=f"AZURE: apply {self.theme['label']} theme")
                except discord.Forbidden:
                    self.warnings.append(f"Cannot edit role {role.name}; check AZURE role hierarchy")
            self.role_objects[name] = role
        return created

    def _category_overwrites(self, category_name):
        # PvP private areas are protected at category level. Existing channel
        # overwrites are not changed by the standalone theme_apply command.
        if self.template_name != "pvp":
            return None
        everyone = self.guild.default_role
        staff_names = {"Founder", "Co-Founder", "Head Admin", "Admin", "Moderator", "Support Team"}
        staff_roles = [self.role_objects[n] for n in staff_names if n in self.role_objects]
        allow_staff = discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True,
            connect=True, speak=True,
        )
        overwrites = {everyone: discord.PermissionOverwrite(view_channel=True)}
        if category_name == "INFORMATION":
            overwrites[everyone] = discord.PermissionOverwrite(
                view_channel=True, send_messages=False, read_message_history=True
            )
        elif category_name == "WHITELISTED":
            overwrites[everyone] = discord.PermissionOverwrite(view_channel=False)
            role = self.role_objects.get("Whitelisted")
            if role:
                overwrites[role] = allow_staff
            for role in staff_roles:
                overwrites[role] = allow_staff
        elif category_name == "VIP":
            overwrites[everyone] = discord.PermissionOverwrite(view_channel=False)
            role = self.role_objects.get("VIP")
            if role:
                overwrites[role] = allow_staff
            for role in staff_roles:
                overwrites[role] = allow_staff
        elif category_name == "STAFF":
            overwrites[everyone] = discord.PermissionOverwrite(view_channel=False)
            for role in staff_roles:
                overwrites[role] = allow_staff
        return overwrites

    async def _ensure_category(self, spec):
        plain = spec["name"]
        emoji = CATEGORY_EMOJIS.get(plain, "📁")
        styled = f"{emoji}・{plain}"
        overwrites = self._category_overwrites(plain)
        category = next((c for c in self.guild.categories if clean_name(c.name) == plain.casefold()), None)
        if category is None:
            # discord.py requires `overwrites` to be a mapping when supplied.
            # For public categories, omit the argument entirely instead of
            # passing None (which raises: overwrites parameter expects a dict).
            create_kwargs = {"reason": "AZURE: create themed category"}
            if overwrites is not None:
                create_kwargs["overwrites"] = overwrites
            category = await self.guild.create_category(styled, **create_kwargs)
            track_managed_resource(self.guild.id, "category", category.id, category.name)
        else:
            try:
                edit_kwargs = {"name": styled}
                if overwrites is not None:
                    edit_kwargs["overwrites"] = overwrites
                await category.edit(**edit_kwargs, reason="AZURE: apply category theme")
            except discord.Forbidden:
                self.warnings.append(f"Cannot rename category {category.name}")
        return category

    async def _ensure_channel(self, category, spec):
        plain = spec["name"]
        kind = spec["type"]
        emoji = CHANNEL_EMOJIS.get(plain, "💬")
        styled = f"{emoji}・{plain}"
        pool = self.guild.text_channels if kind == "text" else self.guild.voice_channels
        channel = next((c for c in pool if clean_name(c.name) == plain.casefold()), None)
        if channel is None:
            if kind == "text":
                channel = await self.guild.create_text_channel(
                    styled, category=category, topic=spec.get("topic", ""),
                    reason="AZURE: create themed text channel",
                )
            else:
                channel = await self.guild.create_voice_channel(
                    styled, category=category, reason="AZURE: create themed voice channel",
                )
            track_managed_resource(self.guild.id, "channel", channel.id, channel.name)
        else:
            try:
                await channel.edit(name=styled, category=category,
                                   reason="AZURE: apply channel theme")
            except discord.Forbidden:
                self.warnings.append(f"Cannot update channel {channel.name}")
        return channel

    async def run(self):
        if self.guild.me is None:
            raise RuntimeError("AZURE is not available in this server.")
        perms = self.guild.me.guild_permissions
        missing = [p for p in ("manage_roles", "manage_channels") if not getattr(perms, p)]
        if missing:
            raise RuntimeError("Missing bot permissions: " + ", ".join(missing))

        created_roles = await self._ensure_roles()
        categories = []
        for category_spec in self.template.get("categories", []):
            category = await self._ensure_category(category_spec)
            categories.append(category.name)
            for channel_spec in category_spec.get("channels", []):
                await self._ensure_channel(category, channel_spec)

        set_guild_theme(self.guild.id, self.theme_name)
        return {
            "template": self.template["name"],
            "theme": self.theme["label"],
            "roles": created_roles,
            "categories": categories,
            "warnings": self.warnings[:30],
        }
