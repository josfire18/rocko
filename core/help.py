"""/help and /about, for everyone (not just admins).

/help lists what this server can use, grouped by add-on, and skips add-ons the server turned off.
/help command:<name> explains one command and its options.
"""
import subprocess
import time
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

REPO = "https://github.com/josfire18/rocko"
HERE = Path(__file__).resolve().parent.parent


def version():
    try:
        out = subprocess.run(["git", "-C", str(HERE), "log", "-1", "--format=%h %cs"], capture_output=True,
                             text=True, timeout=5)
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def leaves(cmd):
    if isinstance(cmd, app_commands.Group):
        return [c for c in cmd.walk_commands() if isinstance(c, app_commands.Command)]
    return [cmd]


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.started = time.time()
        self.version = version()

    def visible(self, interaction):
        """{add-on name, or None for Rocko itself: [commands]} for what this person can use here.
        Skips add-ons this server turned off and admin commands for people who aren't admins."""
        guild_id, mine = interaction.guild_id, interaction.permissions
        groups = {}
        for cmd in sorted(self.bot.tree.get_commands(), key=lambda c: c.name):
            owner = self.bot.command_owner.get(cmd.name)
            if owner and guild_id and not self.bot.addon_enabled(guild_id, owner):
                continue
            needs = cmd.default_permissions
            if needs and needs.value and mine is not None and not mine.is_superset(needs):
                continue
            groups.setdefault(owner, []).extend(leaves(cmd))
        return groups

    async def command_names(self, interaction: discord.Interaction, current: str):
        names = [c.qualified_name for cmds in self.visible(interaction).values() for c in cmds]
        return [app_commands.Choice(name=f"/{n}", value=n) for n in names if current.lower() in n.lower()][:25]

    @app_commands.command(name="help", description="What Rocko can do here, or how one command works")
    @app_commands.describe(command="A command to explain (optional)")
    @app_commands.autocomplete(command=command_names)
    async def help(self, interaction: discord.Interaction, command: str = None):
        groups = self.visible(interaction)
        if command:
            cmd = next((c for cmds in groups.values() for c in cmds if c.qualified_name == command.strip("/ ")), None)
            if not cmd:
                await interaction.response.send_message(f"There's no **/{command.strip('/ ')}** here.", ephemeral=True)
                return
            embed = discord.Embed(title=f"/{cmd.qualified_name}", description=cmd.description)
            for p in cmd.parameters:
                choices = f" · one of: {', '.join(c.name for c in p.choices)}" if p.choices else ""
                embed.add_field(name=f"{p.display_name}{'' if p.required else ' (optional)'}",
                                value=(p.description or "\u200b") + choices, inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        embeds = []
        order = sorted(groups, key=lambda o: (o is not None, o or ""))
        for owner in order:
            lines = [f"`/{c.qualified_name}` {c.description}" for c in groups[owner]]
            title = "Rocko" if owner is None else owner
            # Long add-ons get split across embeds so nothing is cut off.
            chunk = []
            for line in lines:
                if sum(len(x) + 1 for x in chunk) + len(line) > 4000:
                    embeds.append(discord.Embed(title=title, description="\n".join(chunk)))
                    chunk, title = [], f"{title} (more)"
                chunk.append(line)
            if chunk:
                embeds.append(discord.Embed(title=title, description="\n".join(chunk)))
        if embeds:
            embeds[-1].set_footer(text="/help command:<name> explains one · admins: /rocko settings turns add-ons on and off")
        batches, batch = [], []
        for e in embeds:
            if batch and (len(batch) == 10 or sum(len(x) for x in batch) + len(e) > 6000):
                batches.append(batch)
                batch = []
            batch.append(e)
        if batch:
            batches.append(batch)
        await interaction.response.send_message(embeds=batches[0] if batches else [], ephemeral=True,
                                                content=None if batches else "No commands here yet.")
        for b in batches[1:]:
            await interaction.followup.send(embeds=b, ephemeral=True)

    @app_commands.command(name="about", description="What Rocko is, what it runs here, and how to get your own")
    async def about(self, interaction: discord.Interaction):
        up = int(time.time() - self.started)
        days, rest = divmod(up, 86400)
        uptime = (f"{days}d " if days else "") + f"{rest // 3600}h {rest % 3600 // 60}m"
        enabled = [n for n in sorted(self.bot.addons)
                   if not interaction.guild_id or self.bot.addon_enabled(interaction.guild_id, n)]
        embed = discord.Embed(title="Rocko", url=REPO, description=(
            "A small Discord bot whose features come from add-ons. Every server picks the add-ons it wants, "
            "and anyone can run their own copy with just the ones they like, or write a new one in a few lines."))
        embed.add_field(name="Add-ons on here", value=", ".join(enabled) or "none", inline=False)
        embed.add_field(name="Up for", value=uptime)
        embed.add_field(name="Servers", value=str(len(self.bot.guilds)))
        embed.add_field(name="Version", value=self.version)
        embed.add_field(name="\u200b", value=f"[Source and setup]({REPO}) · /help for commands", inline=False)
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Help(bot))
