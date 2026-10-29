"""The built-in features against a real store and a fake Discord."""
import time
from types import SimpleNamespace

import discord
import pytest
from discord import app_commands

from core.help import Help
from core.store import Store
from features import lfg, teamkills


class Resp:
    def __init__(self, sent):
        self.sent = sent

    async def send_message(self, content=None, **kw):
        self.sent.append(("send", content, kw))

    async def edit_message(self, **kw):
        self.sent.append(("edit", None, kw))

    def is_done(self):
        return bool(self.sent)


class Followup:
    def __init__(self, sent):
        self.sent = sent

    async def send(self, content=None, **kw):
        self.sent.append(("followup", content, kw))


def member(uid, name):
    return SimpleNamespace(id=uid, display_name=name, mention=f"<@{uid}>")


def interaction(uid=1, perms=None):
    sent = []
    i = SimpleNamespace(guild_id=10, channel_id=99, user=member(uid, f"user{uid}"), response=Resp(sent),
                        followup=Followup(sent), sent=sent,
                        permissions=perms or discord.Permissions(send_messages=True))

    async def original_response():
        return SimpleNamespace(id=555)
    i.original_response = original_response
    return i


@pytest.fixture
def bot(tmp_path):
    b = SimpleNamespace(store=Store(tmp_path / "t.db"), addons={}, command_owner={}, guilds=[1, 2],
                        addon_enabled=lambda g, n: True, tree=app_commands.CommandTree(discord.Client(intents=discord.Intents.none())))
    return b


def cmd(cog, name):
    for c in cog.walk_app_commands():
        if c.name == name:
            return c
    raise KeyError(name)


async def test_teamkills(bot):
    tk = teamkills.TeamKills(bot)
    joey, sam, ali = member(1, "Joey"), member(2, "Sam"), member(3, "Ali")
    for killer, victim in ((joey, sam), (joey, sam), (ali, joey)):
        await cmd(tk, "add").callback(tk, interaction(), killer=killer, victim=victim, game="Tarkov", note=None)
    i = interaction()
    await cmd(tk, "board").callback(tk, i, game=None, days=None)
    e = i.sent[0][2]["embed"]
    assert e.description.startswith("🏆 Most Dangerous Teammate <@1> · **2**")
    assert "<@1> → <@2> · 2 times" in str(e.to_dict())
    i = interaction(uid=1)
    await cmd(tk, "undo").callback(tk, i)
    assert len(tk.kills(10)) == 2
    i = interaction(uid=7)
    await cmd(tk, "remove").callback(tk, i, member=joey)  # logged by user 1, not 7, no mod rights
    assert "Only whoever logged it" in i.sent[0][1] and len(tk.kills(10)) == 2
    i = interaction(uid=7, perms=discord.Permissions(manage_messages=True))
    await cmd(tk, "remove").callback(tk, i, member=joey)
    assert len(tk.kills(10)) == 1
    i = interaction()
    await cmd(tk, "list").callback(tk, i, member=sam)
    assert "0 team kills, 1 time the victim" in i.sent[0][2]["embed"].title


async def test_lfg_flow(bot):
    cog = lfg.Lfg(bot)
    i = interaction(uid=1)
    await cmd(cog, "lfg").callback(cog, i, game="Tarkov", in_minutes=30, slots=2, note="Labs run", ping=None)
    posts = cog.posts(10)
    (post_id, p), = posts.items()
    assert p["roster"] == [1] and p["message"] == 555 and "Labs run" in i.sent[0][2]["embed"].description
    i = interaction(uid=2)
    await cog.press(i, "join", post_id)
    assert cog.posts(10)[post_id]["roster"] == [1, 2]
    assert i.sent[1][0] == "followup" and "squad is full" in i.sent[1][1]
    i = interaction(uid=3)
    await cog.press(i, "join", post_id)
    assert "full" in i.sent[0][1]
    i = interaction(uid=3)
    await cog.press(i, "cancel", post_id)
    assert "Only the host" in i.sent[0][1]
    i = interaction(uid=1)
    await cog.press(i, "leave", post_id)
    assert cog.posts(10)[post_id]["host"] == 2   # host leaves, next in line takes over


async def test_lfg_reminder(bot):
    sent = []

    class Channel:
        async def send(self, content, **kw):
            sent.append(content)

        def get_partial_message(self, mid):
            async def edit(**kw):
                sent.append("edited")
            return SimpleNamespace(edit=edit)
    bot.get_channel = lambda cid: Channel()
    cog = lfg.Lfg(bot)
    cog.save(10, {"abcd1234": {"host": 1, "game": "Tarkov", "start": int(time.time()) - 5, "slots": 3, "note": None,
                               "roster": [1, 2], "channel": 99, "message": 5, "state": "open"}})
    await cog.reminder_loop.coro(cog)
    await cog.reminder_loop.coro(cog)
    assert sent == ["🎮 **Tarkov** time! <@1> <@2>", "edited"]
    assert cog.posts(10)["abcd1234"]["state"] == "started"


async def test_lfg_buttons_round_trip():
    import re
    item = lfg.LfgButton("join", "abcd1234")
    m = re.fullmatch(lfg.LfgButton.__discord_ui_compiled_template__, item.item.custom_id)
    again = await lfg.LfgButton.from_custom_id(None, None, m)
    assert (again.action, again.post) == ("join", "abcd1234")


async def test_help_lists_visible_commands(bot):
    h = Help(bot)
    tk = teamkills.TeamKills(bot)
    bot.tree.add_command(tk.__cog_app_commands_group__)
    bot.command_owner["tk"] = "teamkills"
    bot.tree.add_command(h.help)
    i = interaction()
    await h.help.callback(h, i, command=None)
    text = str([e.to_dict() for e in i.sent[0][2]["embeds"]])
    assert "/tk add" in text and "/help" in text
    i = interaction()
    await h.help.callback(h, i, command="tk add")
    assert i.sent[0][2]["embed"].title == "/tk add"
    bot.addon_enabled = lambda g, n: n != "teamkills"
    i = interaction()
    await h.help.callback(h, i, command=None)
    assert "/tk add" not in str([e.to_dict() for e in i.sent[0][2]["embeds"]])
