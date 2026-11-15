# AZURE ? Instant Discord Server Generator

AZURE is a locally hosted Discord administration and server-generation bot built in Python using `discord.py` and SQLite.

## Features

- `/setup_pvp`, `/setup_rp`, `/setup_gaming`, `/setup_esports`, `/setup_community`
- Idempotent template setup for roles, categories, and channels
- Validation of bot permissions and admin authorization
- SQLite-backed metadata and audit logging
- Optional local AI preview integration with Ollama
- Backup and restore preview commands

## Quick start

1. Copy the example environment file to `data/.env`.
2. Add your Discord bot token as `DISCORD_TOKEN`.
3. Install dependencies:
   `py -3 -m pip install -r requirements.txt`
4. Run the bot:
   `py -3 bot.py`

## Security notes

- Never commit secrets.
- Keep `.env` local.
- Do not assign administrator permissions automatically.
- Protect the bot's role hierarchy and role-based permissions.


## AZURE-only cleanup

- `/clear_preview` lists only resources whose IDs AZURE recorded when it created them.
- `/clear_server` opens the same preview and requires an explicit confirmation button.
- A SQLite configuration snapshot is saved immediately before deletion.
- Resources created manually or by another bot are not selected. The guild owner, @everyone, managed/integration roles, and roles at/above AZURE's top role are never deleted.
- **Important migration note:** resources AZURE created before ownership tracking was added are not automatically recognized. They will not be deleted by this cleanup. Run a new AZURE setup after installing this version to begin tracking newly created resources.
- Backups are configuration snapshots, not a one-click full restore of Discord messages, integrations, or historical content.
