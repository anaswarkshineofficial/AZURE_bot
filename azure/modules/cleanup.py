from __future__ import annotations

import discord

from azure.database import (
    forget_managed_resource,
    list_managed_resources,
    save_backup,
)
from azure.modules.backups import BackupModule


def cleanup_inventory(guild: discord.Guild) -> dict:
    tracked = list_managed_resources(guild.id)
    channel_ids = {int(row["resource_id"]) for row in tracked if row["resource_type"] in {"channel", "category"}}
    role_ids = {int(row["resource_id"]) for row in tracked if row["resource_type"] == "role"}
    channels = [channel for channel in guild.channels if channel.id in channel_ids]
    roles = [role for role in guild.roles if role.id in role_ids and not role.is_default() and not role.managed and role < guild.me.top_role]
    return {"channels": channels, "roles": roles, "tracked_rows": tracked}


def create_cleanup_backup(guild: discord.Guild) -> int:
    inventory = cleanup_inventory(guild)
    snapshot = BackupModule().snapshot(guild, "pre_azure_cleanup")
    snapshot["azure_managed_resources"] = [
        {"type": row["resource_type"], "id": row["resource_id"], "name": row["resource_name"]}
        for row in inventory["tracked_rows"]
    ]
    save_backup(str(guild.id), snapshot)
    backups = __import__("azure.database", fromlist=["list_backups"]).list_backups(str(guild.id))
    return backups[0]["id"] if backups else 0


async def delete_azure_resources(guild: discord.Guild) -> dict:
    inventory = cleanup_inventory(guild)
    deleted_channels = 0
    deleted_roles = 0
    skipped = []

    # Delete child channels before categories; all IDs must have been recorded by AZURE.
    channels = sorted(inventory["channels"], key=lambda ch: isinstance(ch, discord.CategoryChannel))
    for channel in channels:
        try:
            await channel.delete(reason="AZURE cleanup: resource recorded as AZURE-created")
            kind = "category" if isinstance(channel, discord.CategoryChannel) else "channel"
            forget_managed_resource(guild.id, kind, channel.id)
            # Older records may have been stored as generic channel.
            forget_managed_resource(guild.id, "channel", channel.id)
            deleted_channels += 1
        except (discord.Forbidden, discord.HTTPException) as exc:
            skipped.append(f"{channel.name}: {type(exc).__name__}")

    for role in inventory["roles"]:
        try:
            await role.delete(reason="AZURE cleanup: resource recorded as AZURE-created")
            forget_managed_resource(guild.id, "role", role.id)
            deleted_roles += 1
        except (discord.Forbidden, discord.HTTPException) as exc:
            skipped.append(f"{role.name}: {type(exc).__name__}")

    return {"deleted_channels": deleted_channels, "deleted_roles": deleted_roles, "skipped": skipped}


async def recover_azure_resources_from_audit_log(guild: discord.Guild, bot_user_id: int) -> dict:
    """Register only live resources whose Discord create-audit entry names this bot as actor.

    Discord audit logs are retained for a limited period (normally 45 days); this
    recovery does not guess from resource names or claim manually-created objects.
    """
    if guild.me is None or not guild.me.guild_permissions.view_audit_log:
        raise PermissionError("AZURE needs the View Audit Log permission.")

    from azure.database import track_managed_resource

    recovered = {"channels": [], "categories": [], "roles": []}
    already_tracked = {
        (row["resource_type"], str(row["resource_id"]))
        for row in list_managed_resources(guild.id)
    }

    async for entry in guild.audit_logs(limit=500):
        if entry.user is None or entry.user.id != bot_user_id:
            continue

        if entry.action == discord.AuditLogAction.role_create:
            target_id = getattr(entry.target, "id", None)
            role = guild.get_role(target_id) if target_id else None
            if role is None or role.is_default() or role.managed:
                continue
            key = ("role", str(role.id))
            if key not in already_tracked:
                track_managed_resource(guild.id, "role", role.id, role.name)
                recovered["roles"].append(role.name)
                already_tracked.add(key)

        elif entry.action == discord.AuditLogAction.channel_create:
            target_id = getattr(entry.target, "id", None)
            channel = guild.get_channel(target_id) if target_id else None
            if channel is None:
                continue
            kind = "category" if isinstance(channel, discord.CategoryChannel) else "channel"
            key = (kind, str(channel.id))
            if key not in already_tracked:
                track_managed_resource(guild.id, kind, channel.id, channel.name)
                recovered["categories" if kind == "category" else "channels"].append(channel.name)
                already_tracked.add(key)

    recovered["total"] = sum(len(recovered[key]) for key in ("channels", "categories", "roles"))
    return recovered
