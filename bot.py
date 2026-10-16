"""Rocko: a general-purpose Discord bot. Features come from add-ons.

An add-on is either an installed package that registers a "rocko.addons" entry point (see
core/addons.py) or a local features/<name>.py with an async setup(bot). Each server can turn add-ons
on and off with /rocko, and add-ons keep their per-server settings in bot.store.

Put DISCORD_TOKEN=... in a .env file next to this script, then run:  python bot.py
"""
import logging
import os
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from core import addons
from core.store import Store

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


class RockoTree(app_commands.CommandTree):
    async def interaction_check(self, interaction):
        # Backstop for a server that still shows an add-on's command after turning the add-on off.
        addon = self.client.addon_of(interaction.command)
        if addon and interaction.guild and not self.client.addon_enabled(interaction.guild.id, addon):
            await interaction.response.send_message(
                f"The **{addon}** add-on is turned off in this server.", ephemeral=True)
            return False
        return True


class Rocko(commands.Bot):
    def __init__(self):
        # Slash commands only, so no message-content intent; mentions are the (unused) text prefix.
        super().__init__(command_prefix=commands.when_mentioned, intents=discord.Intents.default(),
                         tree_cls=RockoTree)
        self.store = Store(HERE / "rocko.db")
        self.addons = {}         # name -> addons.Addon, for every add-on that loaded
        self.skipped = {}        # name -> why it didn't load
        self.command_owner = {}  # top-level command name -> add-on name
        self.addon_cogs = {}     # add-on name -> the cogs it added

    async def setup_hook(self):
        await self.load_extension("core.admin")
        disabled = {name.strip() for name in os.environ.get("ROCKO_DISABLED", "").split(",") if name.strip()}
        for addon in addons.discover(HERE / "features"):
            if addon.name in disabled:
                self.skipped[addon.name] = "turned off in .env (ROCKO_DISABLED)"
                continue
            before = {cmd.name for cmd in self.tree.get_commands()}
            cogs_before = set(self.cogs)
            try:
                await self.load_extension(addon.module)
            except Exception as e:
                # One broken add-on shouldn't take the whole bot down.
                log.exception("Add-on %s failed to load", addon.name)
                self.skipped[addon.name] = f"failed to load: {e}"
                continue
            for cmd in self.tree.get_commands():
                if cmd.name not in before:
                    self.command_owner[cmd.name] = addon.name
            self.addon_cogs[addon.name] = [cog for name, cog in self.cogs.items() if name not in cogs_before]
            self.addons[addon.name] = addon
            log.info("Loaded add-on: %s (%s)", addon.name, addon.source)

    def addon_of(self, command):
        if command is None:
            return None
        root = getattr(command, "root_parent", None) or command  # /tarkov price -> tarkov
        return self.command_owner.get(root.name)

    def addon_enabled(self, guild_id, name):
        return name not in self.store.get(guild_id, "rocko", "disabled", [])

    def set_addon_enabled(self, guild_id, name, enabled):
        disabled = set(self.store.get(guild_id, "rocko", "disabled", []))
        disabled.discard(name) if enabled else disabled.add(name)
        self.store.set(guild_id, "rocko", "disabled", sorted(disabled) or None)

    async def sync_commands(self, guild):
        # Per-server sync shows commands right away and lets each server have only its enabled add-ons.
        self.tree.clear_commands(guild=guild)
        for cmd in self.tree.get_commands():
            owner = self.command_owner.get(cmd.name)
            if owner is None or self.addon_enabled(guild.id, owner):
                self.tree.add_command(cmd, guild=guild, override=True)
        await self.tree.sync(guild=guild)

    async def broadcast(self, addon, channel_key, **send_kwargs):
        """Sends a message to every server that set a channel for this add-on (e.g. news posts).

        Skips servers that turned the add-on off or where the channel is gone or off-limits. Pass
        embeds/content, not files: a discord.File can only be sent once.
        """
        for guild_id, channel_id in self.store.guilds_with(addon, channel_key).items():
            if not self.addon_enabled(guild_id, addon):
                continue
            channel = self.get_channel(channel_id)
            if channel is None:
                continue
            try:
                await channel.send(**send_kwargs)
            except discord.HTTPException as e:
                log.warning("Couldn't post %s to #%s in %s: %s", addon, channel, channel.guild, e)

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
