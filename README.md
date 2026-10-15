# Rocko

A Discord bot I run for my friends' server. Rocko itself is a small core, and its features come from
add-ons, so anyone can run their own copy with just the add-ons they want. It runs on my PC, so it
only answers while that's on.

## Add-ons

| Add-on | Commands | Install line for `addons.txt` |
| --- | --- | --- |
| [ClipKit](https://github.com/josfire18/clipkit) | `/clip`: video link to captioned GIF + soundboard sound | `clipkit[rocko] @ git+https://github.com/josfire18/clipkit@v0.2.0` |
| [rocko-tarkov](https://github.com/josfire18/rocko-tarkov) | Escape from Tarkov: `/price`, `/needed`, `/ammo`, `/goons`, `/traders`, news posts, `/needs` | `rocko-tarkov[rocko] @ git+https://github.com/josfire18/rocko-tarkov@v0.1.2` |

Server admins (anyone with *Manage Server*) control add-ons with `/rocko`:

| Command | What it does |
| --- | --- |
| `/rocko addons` | Lists installed add-ons and whether they're on in this server |
| `/rocko enable <addon>` | Turns an add-on on here; its commands show up right away |
| `/rocko disable <addon>` | Turns an add-on off here; its commands disappear from this server |

Installed add-ons start out on in every server. Add-ons keep their own per-server settings (such
as which channel gets posts), set with their own commands.

## Running your own copy

You need Python 3.10+ and git. Some add-ons need more; ClipKit needs ffmpeg
(Windows: `winget install Gyan.FFmpeg`; macOS: `brew install ffmpeg`).

1. **Install:**
   ```
   git clone https://github.com/josfire18/rocko
   cd rocko
   python -m venv .venv
   .venv\Scripts\pip install -r requirements.txt -r addons.txt     (macOS/Linux: .venv/bin/pip ...)
   ```
   `addons.txt` lists the add-ons to install. Edit it to pick yours.
2. **Make a Discord bot** at <https://discord.com/developers/applications>: *New Application*, then
   go to **Bot**, click **Reset Token** and copy the token. No privileged intents are needed.
3. **Add the token.** Copy `.env.example` to `.env` and paste the token after `DISCORD_TOKEN=`.
   Keep `.env` private; anyone with the token controls the bot.
4. **Invite the bot.** Open this link, swapping in your app's *Application ID* from the **General Information** page:
   ```
   https://discord.com/oauth2/authorize?client_id=YOUR_APPLICATION_ID&scope=bot+applications.commands&permissions=8796093074432
   ```
   That grants View Channels, Send Messages, Embed Links, Attach Files and Create Expressions.
5. **Run it** with `.venv\Scripts\python bot.py`. On Windows, `start-bot.bat` runs it in the background
   with no window and logs to `bot.log`. To start it with Windows, put a shortcut to `start-bot.bat` in `shell:startup`.

To update, `git pull`, run the same `pip install` line again, and restart the bot. Per-server
settings live in `rocko.db` next to `bot.py`; keep it if you move the bot to another folder.

## Making an add-on

An add-on is a normal Python package with a discord.py
[extension](https://discordpy.readthedocs.io/en/stable/ext/commands/extensions.html) (a module with
`async def setup(bot)` that adds a cog). Register it in your `pyproject.toml`:

```toml
[project.entry-points."rocko.addons"]
myaddon = "my_package.rocko_addon"
```

Once it's `pip install`ed into Rocko's venv, Rocko loads it at startup. No Rocko changes needed.
ClipKit's [`rocko_clip.py`](https://github.com/josfire18/clipkit/blob/main/rocko_clip.py) is a full example.

Inside your cog, `bot.store.addon("myaddon")` gives you per-server settings:

```python
settings = bot.store.addon("myaddon")
settings.set(guild_id, "channel", channel.id)
settings.get(guild_id, "channel")
settings.guilds_with("channel")          # {guild_id: channel_id} for every server that set it
settings.unseen("news", [post_ids...])   # new IDs only, remembered across restarts
```

For posting to every server that picked a channel, `await bot.broadcast("myaddon", "channel", embed=...)`
skips servers that turned the add-on off. Use `discord.ext.tasks` loops for anything that polls.

For something just for your own copy, a `features/<name>.py` file with `setup(bot)` works too.
