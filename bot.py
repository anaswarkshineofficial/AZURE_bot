import discord
from discord.ext import commands

from azure.config import BOT_NAME, BOT_PREFIX, BOT_TOKEN
from azure.database import initialize_database


class AzureBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.guilds = True
        intents.members = True
        intents.messages = True
        intents.message_content = True
        super().__init__(command_prefix=BOT_PREFIX, help_command=None, intents=intents)

    async def setup_hook(self):
        initialize_database()
        await self.load_extension("azure.cogs.setup")
        await self.load_extension("azure.cogs.admin")
        await self.load_extension("azure.cogs.server")
        await self.load_extension("azure.cogs.community")
        await self.load_extension("azure.cogs.ai")

    async def on_ready(self):
        print(f"{BOT_NAME} is online as {self.user}.")
        synced = await self.tree.sync()
        print(f"Synced {len(synced)} commands.")


bot = AzureBot()
if __name__ == "__main__":
    bot.run(BOT_TOKEN)
