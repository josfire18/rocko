"""/tk: a friendly-fire log and leaderboard, for any game.

Anyone can log a team kill. Whoever logged an entry (or anyone with Manage Messages) can take it
back. Entries are kept per server in rocko.db.
"""
import time

import discord
from discord import app_commands
from discord.ext import commands

ADDON = "teamkills"
MAX_KEPT = 2000  # per server, oldest dropped first

TITLES = ["🏆 Most Dangerous Teammate", "🥈 Friendly Fire Enthusiast", "🥉 Trigger Discipline Pending"]
VICTIM_TITLES = ["🎯 Human Shield", "🩹 Frequent Patient", "😵 Wrong Place, Wrong Time"]


def tally(kills, key):
    counts = {}
    for k in kills:
        counts[k[key]] = counts.get(k[key], 0) + 1
    return sorted(counts.items(), key=lambda kv: -kv[1])


@app_commands.guild_only()
class TeamKills(commands.GroupCog, group_name="tk", group_description="Log team kills and see who's the biggest menace"):
    def __init__(self, bot):
        self.bot = bot
        self.settings = bot.store.addon(ADDON)
        super().__init__()

    def kills(self, guild_id):
        return list(self.settings.get(guild_id, "kills", []))

    @app_commands.command(name="add", description="Log a team kill")
    @app_commands.describe(killer="Who did it", victim="Who got got", game="Which game (optional)",
                           note="What happened (optional)")
    async def add(self, interaction: discord.Interaction, killer: discord.Member, victim: discord.Member,
                  game: str = None, note: str = None):
        kills = self.kills(interaction.guild_id)
        kills.append({"killer": killer.id, "victim": victim.id, "by": interaction.user.id, "at": int(time.time()),
                      "game": (game or "")[:50] or None, "note": (note or "")[:200] or None})
        self.settings.set(interaction.guild_id, "kills", kills[-MAX_KEPT:])
        total = sum(1 for k in kills if k["killer"] == killer.id)
        on_victim = sum(1 for k in kills if k["killer"] == killer.id and k["victim"] == victim.id)
        line = f"💀 **{killer.display_name}** team killed **{victim.display_name}**"
        if game:
            line += f" in {discord.utils.escape_markdown(game[:50])}"
        if note:
            line += f"\n> {discord.utils.escape_markdown(note[:200])}"
        line += f"\n-# That's {total} for {killer.display_name}" + (
            f", {on_victim} of them on {victim.display_name}" if on_victim > 1 else "") + ". /tk undo if that was a mistake."
        await interaction.response.send_message(line, allowed_mentions=discord.AllowedMentions.none())

    @app_commands.command(name="undo", description="Take back the last team kill you logged")
    async def undo(self, interaction: discord.Interaction):
        kills = self.kills(interaction.guild_id)
        mine = [i for i, k in enumerate(kills) if k["by"] == interaction.user.id]
        if not mine:
            await interaction.response.send_message("You haven't logged any team kills here.", ephemeral=True)
            return
        k = kills.pop(mine[-1])
        self.settings.set(interaction.guild_id, "kills", kills or None)
        await interaction.response.send_message(
            f"Took back <@{k['killer']}> → <@{k['victim']}> from <t:{k['at']}:R>.",
            allowed_mentions=discord.AllowedMentions.none(), ephemeral=True)

    @app_commands.command(name="board", description="The team kill leaderboard")
    @app_commands.describe(game="Only count this game (optional)", days="Only the last N days (optional)")
    async def board(self, interaction: discord.Interaction, game: str = None, days: app_commands.Range[int, 1, 3650] = None):
        kills = self.kills(interaction.guild_id)
        if game:
            kills = [k for k in kills if (k.get("game") or "").lower() == game.lower()]
        if days:
            kills = [k for k in kills if k["at"] >= time.time() - days * 86400]
        if not kills:
            await interaction.response.send_message("No team kills logged yet. Suspiciously peaceful.")
            return
        killers, victims = tally(kills, "killer"), tally(kills, "victim")
        top = [f"{TITLES[i] if i < 3 else f'`#{i + 1}`'} <@{uid}> · **{n}**" for i, (uid, n) in enumerate(killers[:10])]
        hurt = [f"{VICTIM_TITLES[i] if i < 3 else f'`#{i + 1}`'} <@{uid}> · **{n}**" for i, (uid, n) in enumerate(victims[:5])]
        pairs = tally([{"pair": (k["killer"], k["victim"])} for k in kills], "pair")
        scope = " · ".join(x for x in (game, f"last {days} days" if days else None) if x)
        embed = discord.Embed(title="Team kill leaderboard" + (f" ({scope})" if scope else ""),
                              color=discord.Color.red(), description="\n".join(top))
        embed.add_field(name="Most team killed", value="\n".join(hurt), inline=False)
        (killer, victim), n = pairs[0]
        if n > 1:
            embed.add_field(name="💔 Worst rivalry", value=f"<@{killer}> → <@{victim}> · {n} times", inline=False)
        embed.set_footer(text=f"{len(kills)} team kills logged · /tk add to log one")
        await interaction.response.send_message(embed=embed, allowed_mentions=discord.AllowedMentions.none())

    @app_commands.command(name="list", description="Someone's team kills, newest first")
    @app_commands.describe(member="Whose record (default: yours)")
    async def list_(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        kills = [k for k in self.kills(interaction.guild_id) if member.id in (k["killer"], k["victim"])]
        did = sum(1 for k in kills if k["killer"] == member.id)
        lines = []
        for k in reversed(kills[-15:]):
            arrow = f"killed <@{k['victim']}>" if k["killer"] == member.id else f"killed by <@{k['killer']}>"
            extra = " · ".join(x for x in (k.get("game"), k.get("note")) if x)
            lines.append(f"<t:{k['at']}:d> {arrow}" + (f" · {discord.utils.escape_markdown(extra)}" if extra else ""))
        embed = discord.Embed(title=f"{member.display_name}: {did} team kills, {len(kills) - did} time{'' if len(kills) - did == 1 else 's'} the victim",
                              description="\n".join(lines) or "Clean record. For now.", color=discord.Color.red())
        await interaction.response.send_message(embed=embed, allowed_mentions=discord.AllowedMentions.none())

    @app_commands.command(name="remove", description="Remove a team kill entry (whoever logged it, or moderators)")
    @app_commands.describe(member="Whose most recent team kill to remove")
    async def remove(self, interaction: discord.Interaction, member: discord.Member):
        kills = self.kills(interaction.guild_id)
        idx = next((i for i in range(len(kills) - 1, -1, -1) if kills[i]["killer"] == member.id), None)
        if idx is None:
            await interaction.response.send_message(f"{member.display_name} has no team kills logged.", ephemeral=True)
            return
        mod = interaction.permissions.manage_messages
        if kills[idx]["by"] != interaction.user.id and not mod:
            await interaction.response.send_message("Only whoever logged it, or someone with Manage Messages, can remove it.",
                                                    ephemeral=True)
            return
        k = kills.pop(idx)
        self.settings.set(interaction.guild_id, "kills", kills or None)
        await interaction.response.send_message(f"Removed <@{k['killer']}> → <@{k['victim']}> from <t:{k['at']}:R>.",
                                                allowed_mentions=discord.AllowedMentions.none(), ephemeral=True)

    def rocko_settings(self, guild):
        return [f"**Team kills logged here:** {len(self.kills(guild.id))}", "-# No settings. Anyone can /tk add."]


async def setup(bot):
    await bot.add_cog(TeamKills(bot))
