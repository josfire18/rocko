# Rocko

A Discord bot I run for my friends' server. It's a home for whatever fun tools we want. It runs on my
PC, so it only answers while that's on.

## Features

### `/clip`: soundboard sounds and GIFs from video links

```
/clip link:https://www.instagram.com/p/... phrase:bweak yourself
```

Paste an Instagram, TikTok, YouTube, X or Reddit link and say which part you want. Rocko replies with
a **captioned GIF** and an **MP3** sized for the soundboard (5.2 s max). Anyone with *Create
Expressions* can click **🔊 Add to soundboard** to add the sound to the server soundboard.

| Option | What it does |
| --- | --- |
| `link` | The video link |
| `phrase` | Words said in the clip. Rocko cuts around them and uses *your* spelling as the caption, so "bweak" stays "bweak" even though it hears "break". |
| `start` / `end` | Pick the part by time instead: `12.5` or `0:12.5` |
| `caption` | Caption text, if you want something other than the phrase |
| `no_caption` | GIF without a caption |

A long clip with no `phrase` or times gets a reply listing what's said and when, so you can pick.
The clipping itself is [ClipKit](https://github.com/josfire18/clipkit), a separate tool that also
works on the command line.

## Adding a feature

Each feature is a [cog](https://discordpy.readthedocs.io/en/stable/ext/commands/cogs.html) in
`features/`. Every `features/<name>.py` that has an `async def setup(bot)` is loaded at startup, so
a new feature is just a new file. `features/clip.py` is the example to copy. Slash commands show
up in each server as soon as the bot restarts.

## Running your own copy

You need Python 3.10+, git, and ffmpeg (Windows: `winget install Gyan.FFmpeg`; macOS: `brew install ffmpeg`).

1. **Install:**
   ```
   git clone https://github.com/josfire18/rocko
   cd rocko
   python -m venv .venv
   .venv\Scripts\pip install -r requirements.txt     (macOS/Linux: .venv/bin/pip ...)
   ```
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

The first `/clip` downloads the speech model (about 500 MB for `small`; set `WHISPER_MODEL` in `.env`
to change it).
