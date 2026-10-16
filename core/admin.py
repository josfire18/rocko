"""/rocko: lets server admins see which add-ons are installed and turn them on or off for their server.

/rocko settings shows everything in one place: each add-on, its commands, and this server's settings.
An add-on fills in its settings section by giving one of its cogs a method

    def rocko_settings(self, guild) -> list[str]     # may also be async

returning one line per setting. Add-ons without it get their stored values listed as they are.
"""
import inspect

import discord
from discord import app_commands
from discord.ext import commands


@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
class Admin(commands.GroupCog, group_name="rocko", group_description="Manage Rocko's add-ons in this server"):
    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    async def addon_names(self, interaction: discord.Interaction, current: str):
        return [app_commands.Choice(name=name, value=name)
                for name in sorted(self.bot.addons) if current.lower() in name.lower()][:25]

    @app_commands.command(name="addons", description="List installed add-ons and whether they're on here")
    async def list_addons(self, interaction: discord.Interaction):
        lines = []
        for name, addon in sorted(self.bot.addons.items()):
            state = "✅ on" if self.bot.addon_enabled(interaction.guild_id, name) else "⛔ off"
            commands_ = ", ".join(f"/{c}" for c, owner in sorted(self.bot.command_owner.items()) if owner == name)
            lines.append(f"**{name}** · {state} · {commands_ or 'no commands'} ({addon.source})")
        for name, why in sorted(self.bot.skipped.items()):
            lines.append(f"**{name}** · not available ({why})")
        await interaction.response.send_message("\n".join(lines) or "No add-ons are installed.", ephemeral=True)

    def command_lines(self, owner):
        lines = []
        for cmd in sorted(self.bot.tree.get_commands(), key=lambda c: c.name):
            if self.bot.command_owner.get(cmd.name) != owner:
                continue
            leaves = [c for c in cmd.walk_commands() if isinstance(c, app_commands.Command)] \
                if isinstance(cmd, app_commands.Group) else [cmd]
            lines += [f"`/{c.qualified_name}` {c.description}" for c in leaves]
        return lines

    async def settings_lines(self, guild, name):
        for cog in self.bot.addon_cogs.get(name, []):
            hook = getattr(cog, "rocko_settings", None)
            if hook:
                lines = hook(guild)
                return list(await lines if inspect.isawaitable(lines) else lines)
        # No hook: show what the add-on stored for this server, with channel IDs as channel links.
        return [f"**{key}:** {f'<#{value}>' if isinstance(value, int) and guild.get_channel(value) else value}"
                for key, value in sorted(self.bot.store.all(guild.id, name).items())]

    @app_commands.command(name="settings", description="Everything you can set up: add-ons, their commands and this server's settings")
    async def settings(self, interaction: discord.Interaction):
        guild = interaction.guild
        embeds = [discord.Embed(title="Rocko", description="\n".join(
            self.command_lines(None) + ["-# Commands for add-ons that are off here are hidden until you enable them."]))]
        for name, addon in sorted(self.bot.addons.items()):
            on = self.bot.addon_enabled(guild.id, name)
            parts = [f"{'✅ On' if on else '⛔ Off'} in this server · {addon.source}"]
            try:
                settings = await self.settings_lines(guild, name)
            except Exception as e:
                settings = [f"⚠️ Couldn't read its settings: {e}"]
            if settings:
                parts += ["", "**Settings here**", *settings]
            commands_ = self.command_lines(name)
            if commands_:
                parts += ["", "**Commands**", *commands_]
            embeds.append(discord.Embed(title=name, description="\n".join(parts)[:4096]))
        if self.bot.skipped:
            embeds.append(discord.Embed(title="Not loaded", description="\n".join(
                f"**{name}:** {why}" for name, why in sorted(self.bot.skipped.items()))[:4096]))
        # A message holds at most 10 embeds and 6000 characters across them; send the rest as follow-ups.
        batches, batch, size = [], [], 0
        for embed in embeds:
            if batch and (len(batch) == 10 or size + len(embed) > 6000):
                batches.append(batch)
                batch, size = [], 0
            batch.append(embed)
            size += len(embed)
        batches.append(batch)
        await interaction.response.send_message(embeds=batches[0], ephemeral=True)
        for batch in batches[1:]:
            await interaction.followup.send(embeds=batch, ephemeral=True)

    async def toggle(self, interaction, addon, enabled):
        if addon not in self.bot.addons:
            await interaction.response.send_message(f"There's no add-on called **{addon}**.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        self.bot.set_addon_enabled(interaction.guild_id, addon, enabled)
        await self.bot.sync_commands(interaction.guild)
        await interaction.followup.send(f"**{addon}** is now {'on' if enabled else 'off'} in this server.")

    @app_commands.command(name="enable", description="Turn an add-on on in this server")
    @app_commands.autocomplete(addon=addon_names)
    async def enable(self, interaction: discord.Interaction, addon: str):
        await self.toggle(interaction, addon, True)

    @app_commands.command(name="disable", description="Turn an add-on off in this server")
    @app_commands.autocomplete(addon=addon_names)
    async def disable(self, interaction: discord.Interaction, addon: str):
        await self.toggle(interaction, addon, False)


async def setup(bot):
    await bot.add_cog(Admin(bot))
