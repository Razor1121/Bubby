"""
cogs/server_settings.py – Per-guild ARK server rate configuration.

Commands (all grouped under /server_config)
--------------------------------------------
/server_config view            – Display active server multipliers.
/server_config import_ini      – Open a modal to paste Game.ini lines.
/server_config set_wild_mult   – Manually set a wild stat multiplier.
/server_config set_tamed_add   – Manually set a tamed-additive multiplier.
/server_config set_breeding    – Manually set a breeding timer multiplier.
/server_config reset           – Reset all settings back to vanilla defaults.

All write commands require the Manage Server (manage_guild) permission.
"""

from __future__ import annotations

from typing import Optional
import discord
from discord import app_commands
from discord.ext import commands

import config
from utils.server_settings import (
    ServerSettings,
    load_guild_settings,
    save_guild_settings,
    parse_ini_text,
    SPECIES_BREEDING_TIMES,
    DEFAULT_WILD_MULTS,
    DEFAULT_TAMED_ADD,
    DEFAULT_TAMED_AFF,
)
from utils import database as db
from utils.ark_stats import STAT_NAMES, STAT_SHORT, STAT_EMOJI
from utils.prefix_adapter import as_interaction

NUM_STATS = 8

# ── Stat choices for manual multiplier commands ───────────────────────────────
ALL_STAT_CHOICES = [
    app_commands.Choice(name=STAT_NAMES[i], value=i)
    for i in range(NUM_STATS)
]

# ── Breeding timer setting choices ────────────────────────────────────────────
BREEDING_SETTING_CHOICES = [
    app_commands.Choice(name="Egg Hatch Speed",                value="egg_hatch_speed_mult"),
    app_commands.Choice(name="Baby Mature Speed",              value="baby_mature_speed_mult"),
    app_commands.Choice(name="Mating Interval",                value="mating_interval_mult"),
    app_commands.Choice(name="Baby Cuddle Interval",           value="baby_cuddle_interval_mult"),
    app_commands.Choice(name="Baby Food Consumption Speed",    value="baby_food_consumption_speed"),
    app_commands.Choice(name="Baby Imprinting Stat Scale",     value="baby_imprinting_stat_scale"),
    app_commands.Choice(name="Taming Speed",                   value="taming_speed_mult"),
]


# ── Embed Builders ────────────────────────────────────────────────────────────

def _settings_embed(settings: ServerSettings) -> discord.Embed:
    """Build a full settings overview embed."""
    colour = config.EMBED_COLOR if not settings.is_default else config.EMBED_COLOR_INFO
    embed  = discord.Embed(
        title="⚙️ Server Multiplier Settings",
        description=(
            "These values affect displayed stat estimates and breeding timers. "
            "They do **not** change which stat points are inherited — "
            "that is always points-based.\n"
            + ("*Using vanilla (1×) defaults.*" if settings.is_default
               else "✅ **Custom settings active.**")
        ),
        colour=colour,
    )

    # Wild stat multipliers table
    wild_lines = []
    for i in range(NUM_STATS):
        val     = settings.wild_mults[i]
        default = DEFAULT_WILD_MULTS[i]
        marker  = "" if val == default else f"  ← **{val}×**"
        wild_lines.append(
            f"{STAT_EMOJI[i]} **{STAT_SHORT[i]:<6}** {val:.2f}×{marker}"
        )
    embed.add_field(
        name="🔬 Wild Stat Level Multipliers  *(PerLevelStatsMultiplier_DinoWild)*",
        value="\n".join(wild_lines),
        inline=False,
    )

    # Tamed add multipliers (compact)
    add_parts = [
        f"{STAT_SHORT[i]}: {settings.tamed_add[i]:.2f}×"
        for i in range(NUM_STATS)
    ]
    embed.add_field(
        name="🧪 Tamed Additive Mults  *(DinoTamed_Add)*",
        value="  |  ".join(add_parts),
        inline=False,
    )

    # Breeding timers
    timer_lines = [
        f"🥚 **Egg Hatch Speed:**        {settings.egg_hatch_speed_mult:.2f}×",
        f"🍼 **Baby Mature Speed:**       {settings.baby_mature_speed_mult:.2f}×",
        f"💞 **Mating Interval:**         {settings.mating_interval_mult:.2f}×",
        f"🤗 **Cuddle Interval:**         {settings.baby_cuddle_interval_mult:.2f}×",
        f"🎯 **Imprinting Stat Scale:**   {settings.baby_imprinting_stat_scale:.2f}×",
        f"🍖 **Baby Food Consumption:**   {settings.baby_food_consumption_speed:.2f}×",
        f"⚗️ **Taming Speed:**           {settings.taming_speed_mult:.2f}×",
    ]
    embed.add_field(
        name="⏱️ Breeding Timers",
        value="\n".join(timer_lines),
        inline=False,
    )

    # Approximate times for common species
    species_with_times = [s for s, t in SPECIES_BREEDING_TIMES.items() if t["hatch_h"]]
    if species_with_times:
        time_lines = []
        for sp in species_with_times[:6]:
            ht = settings.hatch_time(sp)
            mt = settings.mature_time(sp)
            time_lines.append(f"**{sp:<14}** Hatch: {ht:<10}  Mature: {mt}")
        embed.add_field(
            name="📅 Estimated Times (common species)",
            value="```\n" + "\n".join(time_lines) + "\n```",
            inline=False,
        )

    embed.set_footer(
        text="Use /server_config import_ini to auto-import from Game.ini  |  "
             "Manage Server permission required to edit."
    )
    return embed


# ── Modal ─────────────────────────────────────────────────────────────────────

class _IniImportModal(discord.ui.Modal, title="Import Game.ini Multipliers"):
    ini_text = discord.ui.TextInput(
        label="Paste your Game.ini lines below",
        style=discord.TextStyle.paragraph,
        placeholder=(
            "PerLevelStatsMultiplier_DinoWild[0]=2.0\n"
            "PerLevelStatsMultiplier_DinoWild[5]=3.0\n"
            "EggHatchSpeedMultiplier=10.0\n"
            "BabyMatureSpeedMultiplier=25.0\n"
            "MatingIntervalMultiplier=0.5\n"
            "... (only paste the lines you've changed)"
        ),
        required=True,
        max_length=4000,
    )

    def __init__(self, merge: bool = True):
        super().__init__()
        self._merge = merge   # If True, merge with existing; if False, start fresh.

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild_id = str(interaction.guild_id)

        base = (await load_guild_settings(guild_id)) if self._merge else None
        settings, warnings, found = parse_ini_text(self.ini_text.value, base=base)
        settings.guild_id = guild_id

        await save_guild_settings(settings, updated_by=str(interaction.user.id))

        embed = discord.Embed(
            title="✅ Server Settings Imported",
            colour=config.EMBED_COLOR,
        )

        if found:
            embed.add_field(
                name=f"📥 {len(found)} setting(s) applied",
                value="\n".join(f"`{f}`" for f in found[:20])
                      + ("\n…and more" if len(found) > 20 else ""),
                inline=False,
            )
        if warnings:
            embed.add_field(
                name="⚠️ Warnings",
                value="\n".join(warnings),
                inline=False,
            )

        embed.add_field(
            name="💡 Next Steps",
            value=(
                "Run `/server_config view` to review all active settings.\n"
                "Creature stat estimates will now reflect your server's multipliers."
            ),
            inline=False,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


# ── Confirm-Reset View ────────────────────────────────────────────────────────

class _ConfirmResetView(discord.ui.View):
    def __init__(self, owner: discord.User):
        super().__init__(timeout=30)
        self.owner = owner

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message(
                "Only the person who ran this command can confirm.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Yes, reset to vanilla", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, _: discord.ui.Button):
        await db.delete_server_settings(str(interaction.guild_id))
        await interaction.response.edit_message(
            content="✅ Server settings have been reset to ARK vanilla defaults.", view=None
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.edit_message(content="Reset cancelled.", view=None)


# ── Cog ───────────────────────────────────────────────────────────────────────

class ServerSettingsCog(commands.Cog, name="Server Settings"):
    """Configure per-guild ARK server rates."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _stat_choice_from_text(self, value: str) -> app_commands.Choice[int] | None:
        cleaned = value.strip().lower()
        for choice in ALL_STAT_CHOICES:
            if choice.name.lower() == cleaned:
                return app_commands.Choice(name=choice.name, value=choice.value)
        if cleaned.isdigit():
            idx = int(cleaned)
            for choice in ALL_STAT_CHOICES:
                if choice.value == idx:
                    return app_commands.Choice(name=choice.name, value=choice.value)
        return None

    def _breeding_choice_from_text(self, value: str) -> app_commands.Choice[str] | None:
        cleaned = value.strip().lower()
        for choice in BREEDING_SETTING_CHOICES:
            if choice.name.lower() == cleaned or choice.value.lower() == cleaned:
                return app_commands.Choice(name=choice.name, value=choice.value)
        return None

    @commands.group(name="server_config", invoke_without_command=True)
    async def server_config_prefix(self, ctx: commands.Context) -> None:
        await ctx.send(
            "Use >server_config view | import_ini | set_wild_mult | set_tamed_add | set_breeding | reset"
        )

    @server_config_prefix.command(name="view")
    async def server_config_view_prefix(self, ctx: commands.Context) -> None:
        adapter = as_interaction(ctx)
        await ServerSettingsCog.view.callback(self, adapter)

    @server_config_prefix.command(name="import_ini")
    @commands.has_permissions(manage_guild=True)
    async def server_config_import_ini_prefix(self, ctx: commands.Context, replace: bool = False) -> None:
        await ctx.send(
            "Paste your ini lines with: >server_config import_ini_text <replace:true|false> <ini lines>."
        )

    @server_config_prefix.command(name="import_ini_text")
    @commands.has_permissions(manage_guild=True)
    async def server_config_import_ini_text_prefix(
        self,
        ctx: commands.Context,
        replace: bool = False,
        *,
        ini_text: str,
    ) -> None:
        guild_id = str(ctx.guild.id)
        base = None if replace else (await load_guild_settings(guild_id))
        settings, warnings, found = parse_ini_text(ini_text, base=base)
        settings.guild_id = guild_id
        await save_guild_settings(settings, updated_by=str(ctx.author.id))

        embed = discord.Embed(title="Server settings imported", colour=config.EMBED_COLOR)
        if found:
            embed.add_field(name="Applied", value="\n".join(found[:20]), inline=False)
        if warnings:
            embed.add_field(name="Warnings", value="\n".join(warnings), inline=False)
        await ctx.send(embed=embed)

    @server_config_prefix.command(name="set_wild_mult")
    @commands.has_permissions(manage_guild=True)
    async def server_config_set_wild_mult_prefix(
        self,
        ctx: commands.Context,
        stat: str,
        value: float,
    ) -> None:
        stat_choice = self._stat_choice_from_text(stat)
        if stat_choice is None:
            await ctx.send("Unknown stat. Use a stat name or index 0-7.")
            return
        adapter = as_interaction(ctx)
        await ServerSettingsCog.set_wild_mult.callback(
            self,
            adapter,
            stat=stat_choice,
            value=value,
        )

    @server_config_prefix.command(name="set_tamed_add")
    @commands.has_permissions(manage_guild=True)
    async def server_config_set_tamed_add_prefix(
        self,
        ctx: commands.Context,
        stat: str,
        value: float,
    ) -> None:
        stat_choice = self._stat_choice_from_text(stat)
        if stat_choice is None:
            await ctx.send("Unknown stat. Use a stat name or index 0-7.")
            return
        adapter = as_interaction(ctx)
        await ServerSettingsCog.set_tamed_add.callback(
            self,
            adapter,
            stat=stat_choice,
            value=value,
        )

    @server_config_prefix.command(name="set_breeding")
    @commands.has_permissions(manage_guild=True)
    async def server_config_set_breeding_prefix(
        self,
        ctx: commands.Context,
        setting: str,
        value: float,
    ) -> None:
        setting_choice = self._breeding_choice_from_text(setting)
        if setting_choice is None:
            await ctx.send("Unknown setting. Use >help server for valid setting names.")
            return
        adapter = as_interaction(ctx)
        await ServerSettingsCog.set_breeding.callback(
            self,
            adapter,
            setting=setting_choice,
            value=value,
        )

    @server_config_prefix.command(name="reset")
    @commands.has_permissions(manage_guild=True)
    async def server_config_reset_prefix(self, ctx: commands.Context) -> None:
        adapter = as_interaction(ctx)
        await ServerSettingsCog.reset.callback(self, adapter)

    # Build the command group with manage_guild permission requirement.
    server_config = app_commands.Group(
        name="server_config",
        description="Configure ARK server multipliers for this Discord server.",
    )

    # ── /server_config view ───────────────────────────────────────────────────

    @server_config.command(
        name="view",
        description="Display all active server multiplier settings.",
    )
    async def view(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        settings = await load_guild_settings(str(interaction.guild_id))
        await interaction.followup.send(embed=_settings_embed(settings))

    # ── /server_config import_ini ─────────────────────────────────────────────

    @server_config.command(
        name="import_ini",
        description="[Admin] Import multipliers by pasting lines from Game.ini.",
    )
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(
        replace="Replace ALL existing settings (default: merge / overwrite only found keys)"
    )
    async def import_ini(
        self,
        interaction: discord.Interaction,
        replace: bool = False,
    ):
        modal = _IniImportModal(merge=not replace)
        await interaction.response.send_modal(modal)

    # ── /server_config set_wild_mult ──────────────────────────────────────────

    @server_config.command(
        name="set_wild_mult",
        description="[Admin] Manually set the per-level wild stat multiplier for one stat.",
    )
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(
        stat  = "Which stat to configure",
        value = "Multiplier value (e.g. 2.0 for double wild levels, 1.0 = vanilla)",
    )
    @app_commands.choices(stat=ALL_STAT_CHOICES)
    async def set_wild_mult(
        self,
        interaction: discord.Interaction,
        stat: app_commands.Choice[int],
        value: float,
    ):
        await interaction.response.defer(ephemeral=True)
        if value < 0:
            await interaction.followup.send(
                "Multiplier cannot be negative.", ephemeral=True
            )
            return

        guild_id = str(interaction.guild_id)
        settings = await load_guild_settings(guild_id)
        settings.wild_mults[stat.value] = value
        await save_guild_settings(settings, updated_by=str(interaction.user.id))

        await interaction.followup.send(
            f"✅ **{STAT_NAMES[stat.value]}** wild level multiplier set to **{value:.2f}×**.",
            ephemeral=True,
        )

    # ── /server_config set_tamed_add ──────────────────────────────────────────

    @server_config.command(
        name="set_tamed_add",
        description="[Admin] Set the tamed additive stat multiplier for one stat.",
    )
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(
        stat  = "Which stat to configure",
        value = "Multiplier value (vanilla default: 0.14)",
    )
    @app_commands.choices(stat=ALL_STAT_CHOICES)
    async def set_tamed_add(
        self,
        interaction: discord.Interaction,
        stat: app_commands.Choice[int],
        value: float,
    ):
        await interaction.response.defer(ephemeral=True)
        guild_id = str(interaction.guild_id)
        settings = await load_guild_settings(guild_id)
        settings.tamed_add[stat.value] = value
        await save_guild_settings(settings, updated_by=str(interaction.user.id))
        await interaction.followup.send(
            f"✅ **{STAT_NAMES[stat.value]}** tamed-additive multiplier set to **{value:.4f}**.",
            ephemeral=True,
        )

    # ── /server_config set_breeding ───────────────────────────────────────────

    @server_config.command(
        name="set_breeding",
        description="[Admin] Set a breeding / taming timer multiplier.",
    )
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(
        setting = "Which breeding multiplier to set",
        value   = "Multiplier value (e.g. 10.0 = 10× speed, 1.0 = vanilla)",
    )
    @app_commands.choices(setting=BREEDING_SETTING_CHOICES)
    async def set_breeding(
        self,
        interaction: discord.Interaction,
        setting: app_commands.Choice[str],
        value: float,
    ):
        await interaction.response.defer(ephemeral=True)
        if value <= 0:
            await interaction.followup.send(
                "Multiplier must be greater than 0.", ephemeral=True
            )
            return

        guild_id = str(interaction.guild_id)
        settings = await load_guild_settings(guild_id)
        setattr(settings, setting.value, value)
        await save_guild_settings(settings, updated_by=str(interaction.user.id))

        await interaction.followup.send(
            f"✅ **{setting.name}** set to **{value:.2f}×**.",
            ephemeral=True,
        )

    # ── /server_config reset ──────────────────────────────────────────────────

    @server_config.command(
        name="reset",
        description="[Admin] Reset all server settings back to ARK vanilla defaults.",
    )
    @app_commands.default_permissions(manage_guild=True)
    async def reset(self, interaction: discord.Interaction):
        view = _ConfirmResetView(interaction.user)
        await interaction.response.send_message(
            "⚠️ This will erase **all** custom server multipliers and revert to "
            "vanilla ARK defaults.  Are you sure?",
            view=view,
            ephemeral=True,
        )


# ── Setup ─────────────────────────────────────────────────────────────────────

async def setup(bot: commands.Bot):
    await bot.add_cog(ServerSettingsCog(bot))
