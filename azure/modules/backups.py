from __future__ import annotations


class BackupModule:
    def snapshot(self, guild, template_name):
        return {
            "guild_id": str(guild.id),
            "template_name": template_name,
            "roles": [role.name for role in guild.roles],
            "categories": [category.name for category in guild.categories],
            "channels": [channel.name for channel in guild.channels],
        }

    def save(self, guild, template_name, database):
        snapshot = self.snapshot(guild, template_name)
        database.save_backup(str(guild.id), snapshot)
        return snapshot
