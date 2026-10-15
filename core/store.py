"""Per-server settings and seen-item tracking, in one SQLite file next to bot.py (gitignored).

Add-ons get their own namespace with bot.store.addon("name"), so two add-ons can both have a
"channel" setting without clashing. Values are stored as JSON, so ints, strings, lists and dicts work.
"""
import json
import sqlite3
from pathlib import Path


class Store:
    def __init__(self, path: Path):
        self.db = sqlite3.connect(path)
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS settings (
                guild_id INTEGER NOT NULL, addon TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL,
                PRIMARY KEY (guild_id, addon, key));
            CREATE TABLE IF NOT EXISTS seen (
                feed TEXT NOT NULL, item_id TEXT NOT NULL, PRIMARY KEY (feed, item_id));
        """)
        self.db.commit()

    def addon(self, name):
        return AddonSettings(self, name)

    def get(self, guild_id, addon, key, default=None):
        row = self.db.execute("SELECT value FROM settings WHERE guild_id=? AND addon=? AND key=?",
                              (guild_id, addon, key)).fetchone()
        return json.loads(row[0]) if row else default

    def set(self, guild_id, addon, key, value):
        if value is None:
            self.db.execute("DELETE FROM settings WHERE guild_id=? AND addon=? AND key=?", (guild_id, addon, key))
        else:
            self.db.execute("INSERT OR REPLACE INTO settings VALUES (?, ?, ?, ?)",
                            (guild_id, addon, key, json.dumps(value)))
        self.db.commit()

    def all(self, guild_id, addon):
        rows = self.db.execute("SELECT key, value FROM settings WHERE guild_id=? AND addon=?", (guild_id, addon))
        return {key: json.loads(value) for key, value in rows}

    def guilds_with(self, addon, key):
        """{guild_id: value} for every server that has set this key, e.g. a news channel."""
        rows = self.db.execute("SELECT guild_id, value FROM settings WHERE addon=? AND key=?", (addon, key))
        return {guild_id: json.loads(value) for guild_id, value in rows}

    def unseen(self, feed, item_ids):
        """Returns the IDs not seen before for this feed and remembers them, so restarts don't repost.

        The first time a feed is checked, everything is marked seen and nothing is returned, so a new
        feed doesn't flood channels with its whole backlog.
        """
        item_ids = [str(i) for i in item_ids]
        first_run = self.db.execute("SELECT 1 FROM seen WHERE feed=? LIMIT 1", (feed,)).fetchone() is None
        known = {row[0] for row in self.db.execute("SELECT item_id FROM seen WHERE feed=?", (feed,))}
        new = [i for i in item_ids if i not in known]
        self.db.executemany("INSERT OR IGNORE INTO seen VALUES (?, ?)", [(feed, i) for i in new])
        self.db.commit()
        return [] if first_run else new


class AddonSettings:
    """One add-on's slice of the store: settings.get(guild_id, "channel")."""

    def __init__(self, store, name):
        self.store = store
        self.name = name

    def get(self, guild_id, key, default=None):
        return self.store.get(guild_id, self.name, key, default)

    def set(self, guild_id, key, value):
        self.store.set(guild_id, self.name, key, value)

    def all(self, guild_id):
        return self.store.all(guild_id, self.name)

    def guilds_with(self, key):
        return self.store.guilds_with(self.name, key)

    def unseen(self, feed, item_ids):
        return self.store.unseen(f"{self.name}:{feed}", item_ids)
