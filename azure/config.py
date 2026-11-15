import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
ENV_PATH = DATA_DIR / ".env"

if ENV_PATH.exists():
    load_dotenv(ENV_PATH)

BOT_TOKEN = os.getenv("DISCORD_TOKEN", "")
BOT_PREFIX = os.getenv("BOT_PREFIX", "/")
BOT_NAME = os.getenv("BOT_NAME", "AZURE")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

REQUIRED_DISCORD_PERMISSIONS = {
    "manage_roles",
    "manage_channels",
    "view_channel",
    "send_messages",
    "embed_links",
    "read_message_history",
}
