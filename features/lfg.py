"""/lfg: "who's playing?" posts for any game, with Join and Leave buttons.

The post shows who's in and when it starts (in each reader's own time zone). When the squad fills up
or the start time comes, Rocko pings everyone who joined. Buttons keep working after a restart.
"""
import logging
import secrets
import time

import discord
from discord import app_commands
from discord.ext import commands, tasks

log = logging.getLogger("rocko.lfg")
ADDON = "lfg"
KEEP_FOR = 6 * 3600  # how long after the start time a post's buttons keep working


def post_embed(p):
    roster = p["roster"]
    full = len(roster) >= p["slots"]
    state = {"cancelled": "❌ Cancelled", "started": "🎮 Started"}.get(p["state"], "✅ Full" if full else "🟢 Open")
    lines = [f"**When:** <t:{p['start']}:t> · <t:{p['start']}:R>" if p["start"] > time.time() - 60 else f"**When:** <t:{p['start']}:R>",
             f"**Squad:** {len(roster)}/{p['slots']} · {state}"]
    if p.get("note"):
        lines.append(f"> {discord.utils.escape_markdown(p['note'])}")
    lines.append("")
    lines += [f"{'👑' if uid == p['host'] else '•'} <@{uid}>" for uid in roster]
    lines += ["◦ *open slot*"] * max(0, p["slots"] - len(roster))
    color = discord.Color.green() if p["state"] == "open" and not full else discord.Color.dark_gray()
    embed = discord.Embed(title=f"🎮 {p['game']}", description="\n".join(lines), color=color)
    embed.set_footer(text="Join and I'll ping you when it's time")
    return embed


class LfgButton(discord.ui.DynamicItem[discord.ui.Button],
                template=r"lfg:(?P<action>join|leave|cancel):(?P<post>[0-9a-f]{8})"):
    STYLE = {"join": ("Join", "✋", discord.ButtonStyle.success), "leave": ("Leave", None, discord.ButtonStyle.secondary),
             "cancel": ("Cancel", None, discord.ButtonStyle.danger)}

    def __init__(self, action, post, disabled=False):
        label, emoji, style = self.STYLE[action]
        super().__init__(discord.ui.Button(label=label, emoji=emoji, style=style, disabled=disabled,
                                           custom_id=f"lfg:{action}:{post}"))
        self.action, self.post = action, post

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["action"], match["post"])

    async def callback(self, interaction):
        cog = interaction.client.get_cog("Lfg")
        if cog is None or not interaction.client.addon_enabled(interaction.guild_id, ADDON):
            await interaction.response.send_message("Looking-for-group is turned off here.", ephemeral=True)
            return
        await cog.press(interaction, self.action, self.post)


def post_view(post_id, closed=False):
    view = discord.ui.View(timeout=None)
    for action in ("join", "leave", "cancel"):
        view.add_item(LfgButton(action, post_id, disabled=closed))
    return view


class Lfg(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.settings = bot.store.addon(ADDON)

    async def cog_load(self):
        self.bot.add_dynamic_items(LfgButton)
        self.reminder_loop.start()

    async def cog_unload(self):
        self.reminder_loop.cancel()
        self.bot.remove_dynamic_items(LfgButton)

    def posts(self, guild_id):
        return dict(self.settings.get(guild_id, "posts", {}))

    def save(self, guild_id, posts):
        self.settings.set(guild_id, "posts", posts or None)

    @app_commands.command(name="lfg", description="Find people to play with: a post with Join buttons and a ping at start time")
    @app_commands.describe(game="What you're playing", in_minutes="Starts in how many minutes (0 = now)",
                           slots="How many players in total, including you", note="Anything else (optional)",
                           ping="A role to ping about it, like @Tarkov (optional)")
    @app_commands.guild_only()
    async def lfg(self, interaction: discord.Interaction, game: app_commands.Range[str, 1, 80],
                  in_minutes: app_commands.Range[int, 0, 10080] = 0, slots: app_commands.Range[int, 2, 50] = 5,
                  note: app_commands.Range[str, 0, 200] = None, ping: discord.Role = None):
        post_id = secrets.token_hex(4)
        p = {"host": interaction.user.id, "game": game, "start": int(time.time() + in_minutes * 60), "slots": slots,
             "note": note or None, "roster": [interaction.user.id], "channel": interaction.channel_id,
             "message": None, "state": "open"}
        content, mentions = None, discord.AllowedMentions.none()
        if ping:
            if not ping.mentionable and not interaction.permissions.mention_everyone:
                await interaction.response.send_message(f"{ping.mention} can't be pinged by you here, so I didn't post. "
                                                        "Try again without ping.", ephemeral=True)
                return
            content, mentions = f"{ping.mention} {interaction.user.display_name} is looking for players", \
                discord.AllowedMentions(roles=[ping])
        await interaction.response.send_message(content=content, embed=post_embed(p), view=post_view(post_id),
                                                allowed_mentions=mentions)
        message = await interaction.original_response()
        p["message"] = message.id
        posts = self.posts(interaction.guild_id)
        posts[post_id] = p
        self.save(interaction.guild_id, posts)

    async def press(self, interaction, action, post_id):
        posts = self.posts(interaction.guild_id)
        p = posts.get(post_id)
        if not p or p["state"] != "open" and action != "leave":
            await interaction.response.send_message("This post is closed.", ephemeral=True)
            return
        uid = interaction.user.id
        if action == "join":
            if uid in p["roster"]:
                await interaction.response.send_message("You're already in.", ephemeral=True)
                return
            if len(p["roster"]) >= p["slots"]:
                await interaction.response.send_message("The squad is full. Leave a ✋ next time!", ephemeral=True)
                return
            p["roster"].append(uid)
        elif action == "leave":
            if uid not in p["roster"]:
                await interaction.response.send_message("You weren't in this one.", ephemeral=True)
                return
            p["roster"].remove(uid)
            if uid == p["host"] and p["roster"]:
                p["host"] = p["roster"][0]  # the next person takes over
            if not p["roster"]:
                p["state"] = "cancelled"
        elif action == "cancel":
            if uid != p["host"] and not interaction.permissions.manage_messages:
                await interaction.response.send_message("Only the host can cancel.", ephemeral=True)
                return
            p["state"] = "cancelled"
        save_now = dict(posts, **{post_id: p})
        self.save(interaction.guild_id, save_now)
        closed = p["state"] != "open"
        await interaction.response.edit_message(embed=post_embed(p), view=post_view(post_id, closed))
        if action == "join" and len(p["roster"]) >= p["slots"] and p["start"] > time.time() + 60:
            await interaction.followup.send(f"✅ **{p['game']}** squad is full: {' '.join(f'<@{u}>' for u in p['roster'])}. "
                                            f"I'll ping you again <t:{p['start']}:R>.")

    @tasks.loop(seconds=30)
    async def reminder_loop(self):
        now = time.time()
        for guild_id in list(self.settings.guilds_with("posts")):
            posts, changed = self.posts(guild_id), False
            for post_id, p in list(posts.items()):
                if p["state"] == "open" and p["start"] <= now:
                    p["state"] = "started"
                    changed = True
                    channel = self.bot.get_channel(p["channel"])
                    if channel and self.bot.addon_enabled(guild_id, ADDON):
                        try:
                            if len(p["roster"]) > 1 or p["slots"] <= 1:
                                await channel.send(f"🎮 **{p['game']}** time! {' '.join(f'<@{u}>' for u in p['roster'])}",
                                                   allowed_mentions=discord.AllowedMentions(users=True))
                            else:
                                await channel.send(f"🎮 Nobody joined <@{p['host']}> for **{p['game']}** this time.",
                                                   allowed_mentions=discord.AllowedMentions(users=True))
                            msg = channel.get_partial_message(p["message"]) if p.get("message") else None
                            if msg:
                                await msg.edit(embed=post_embed(p), view=post_view(post_id, closed=True))
                        except discord.HTTPException as e:
                            log.warning("Couldn't post LFG reminder in %s: %s", channel, e)
                if p["start"] < now - KEEP_FOR:
                    posts.pop(post_id)
                    changed = True
            if changed:
                self.save(guild_id, posts)

    @reminder_loop.before_loop
    async def before(self):
        await self.bot.wait_until_ready()

    def rocko_settings(self, guild):
        active = [p for p in self.posts(guild.id).values() if p["state"] == "open"]
        return [f"**Open posts:** {len(active)}", "-# No settings. Anyone can /lfg."]


async def setup(bot):
    await bot.add_cog(Lfg(bot))
