"""/rocko: lets server admins see which add-ons are installed and turn them on or off for their server."""
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
