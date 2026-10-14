"""Rocko: a Discord bot for the friends' server.

Each feature is a cog in features/. Every features/<name>.py with a setup() is loaded at startup,
so adding a feature means adding a file there.

Put DISCORD_TOKEN=... in a .env file next to this script, then run:  python bot.py
"""
import logging
import os
from pathlib import Path

import discord
from discord.ext import commands

HERE = Path(__file__).resolve().parent
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                    handlers=[logging.FileHandler(HERE / "bot.log", encoding="utf-8"), logging.StreamHandler()])
log = logging.getLogger("rocko")


def load_env():
    env_file = HERE / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.partition("=")
            if sep and not line.lstrip().startswith("#"):
                os.environ.setdefault(key.strip(), value.strip().strip('"'))


class Rocko(commands.Bot):
    def __init__(self):
        # Slash commands only, so no message-content intent; mentions are the (unused) text prefix.
        super().__init__(command_prefix=commands.when_mentioned, intents=discord.Intents.default())

    async def setup_hook(self):
        for path in sorted((HERE / "features").glob("*.py")):
            if path.stem.startswith("_"):
                continue
            await self.load_extension(f"features.{path.stem}")
            log.info("Loaded feature: %s", path.stem)

    async def sync_commands(self, guild):
        # Per-server sync shows commands right away; a global sync can take a while to appear.
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)

    async def on_ready(self):
        for guild in self.guilds:
            await self.sync_commands(guild)
        log.info("Logged in as %s, serving %d server(s)", self.user, len(self.guilds))

    async def on_guild_join(self, guild):
        await self.sync_commands(guild)


if __name__ == "__main__":
    load_env()
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise SystemExit(f"No DISCORD_TOKEN. Put DISCORD_TOKEN=... in {HERE / '.env'} (see README).")
    Rocko().run(token, log_handler=None)
