"""
cogs/help.py - Unified help commands for slash and prefix users.

Commands
--------
/help           - Detailed command guide with optional category filter.
'help, >help    - Prefix alias to the same guide.
"""

from __future__ import annotations

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

import config


HELP_TOPICS: dict[str, dict[str, str]] = {
    "roster": {
        "title": "Roster Commands",
        "content": (
            "• /add_creature\n"
            "Purpose: Add one creature with all wild stat points and mutation counters.\n"
            "Use when: You want a dino available for breeding analysis commands.\n"
            "Key options: name, species, gender, level, hp/stamina/oxygen/food/weight/melee/speed/torpidity, mut_mat, mut_pat, notes.\n\n"
            "• /list_creatures\n"
            "Purpose: Browse the full roster with optional filters.\n"
            "Use when: You want IDs for other commands or a quick species/gender view.\n"
            "Key options: species, gender, mine.\n\n"
            "• /view_creature\n"
            "Purpose: Open one creature card with full detail.\n"
            "Use when: You need to verify exact stats and mutation lineage.\n"
            "Key options: creature_id.\n\n"
            "• /edit_creature\n"
            "Purpose: Update an existing creature without deleting it.\n"
            "Use when: You entered a wrong stat, level, mutation count, or notes.\n"
            "Key options: creature_id plus any fields you want to change.\n\n"
            "• /remove_creature\n"
            "Purpose: Delete a creature from the database.\n"
            "Use when: You need cleanup for duplicates or mistakes.\n"
            "Key options: creature_id.\n\n"
            "• /search\n"
            "Purpose: Find creatures by text match.\n"
            "Use when: You only remember part of a name/species.\n"
            "Key options: query."
        ),
    },
    "breeding": {
        "title": "Breeding Commands",
        "content": (
            "• /breed\n"
            "Purpose: Analyze one specific parent pairing.\n"
            "Use when: You want inheritance odds and mutation chance for two IDs.\n"
            "Key options: parent_a_id, parent_b_id.\n\n"
            "• /best_pair\n"
            "Purpose: Rank the top pairings for a species automatically.\n"
            "Use when: You want the best candidates without testing all combos yourself.\n"
            "Key options: species, top, ignore_speed, ignore_oxy, ignore_torp.\n\n"
            "• /stat_check\n"
            "Purpose: Show top creatures for a selected stat.\n"
            "Use when: You are selecting breeders for one target line.\n"
            "Key options: species, stat, top."
        ),
    },
    "mutations": {
        "title": "Mutation Commands",
        "content": (
            "• /mutation_status\n"
            "Purpose: Show mutation counters for one creature or a species roster.\n"
            "Use when: You need to track soft-cap risk and clean breeders.\n"
            "Key options: species or creature_id.\n\n"
            "• /stacking_guide\n"
            "Purpose: Generate a step-by-step mutation stacking plan.\n"
            "Use when: You are advancing a target stat over many generations.\n"
            "Key options: mutation_male_id, clean_female_id, target_stat, current_stack, desired_stack.\n\n"
            "• /mutation_calc\n"
            "Purpose: Estimate how many attempts are needed for target mutations.\n"
            "Use when: You want probability/time planning before a long breeding grind.\n"
            "Key options: desired_mutations, target_stat, confidence."
        ),
    },
    "export": {
        "title": "Export Commands",
        "content": (
            "• /setup or >setup\n"
            "Purpose: Create and save a default webhook for the server/channel.\n"
            "Use when: You want /export_webhook to work without pasting URL each time.\n"
            "Requirements: Manage Webhooks permission in target channel.\n\n"
            "• /export_webhook\n"
            "Purpose: Send creature cards to a Discord webhook.\n"
            "Use when: You want roster snapshots in another channel/server.\n"
            "Key options: species, webhook_url override.\n\n"
            "• /export_sheet\n"
            "Purpose: Export your creatures to Google Sheets.\n"
            "Use when: You want spreadsheet workflows and sharing.\n"
            "Key options: species (optional user-only filter remains enforced).\n"
            "Notes: If Drive quota blocks new files, set GOOGLE_SHARED_SPREADSHEET_ID for shared-sheet tab mode.\n\n"
            "• /export_csv\n"
            "Purpose: Download your roster as a CSV attachment.\n"
            "Use when: You want offline backup or import into external tools.\n"
            "Key options: species, mine."
        ),
    },
    "server": {
        "title": "Server Config Commands",
        "content": (
            "• /server_config view\n"
            "Purpose: Display active multipliers and derived timing values.\n\n"
            "• /server_config import_ini\n"
            "Purpose: Import settings from pasted Game.ini lines.\n"
            "Requires: Manage Server permission.\n\n"
            "• /server_config set_wild_mult\n"
            "Purpose: Set a wild stat multiplier per stat index.\n"
            "Requires: Manage Server permission.\n\n"
            "• /server_config set_tamed_add\n"
            "Purpose: Set tamed additive multiplier values.\n"
            "Requires: Manage Server permission.\n\n"
            "• /server_config set_breeding\n"
            "Purpose: Set breeding/taming speed multipliers.\n"
            "Requires: Manage Server permission.\n\n"
            "• /server_config reset\n"
            "Purpose: Reset all server-specific settings back to vanilla defaults.\n"
            "Requires: Manage Server permission."
        ),
    },
}


def _topic_embed(topic: str) -> discord.Embed:
    section = HELP_TOPICS[topic]
    embed = discord.Embed(
        title=f"Help - {section['title']}",
        description=section["content"],
        colour=config.EMBED_COLOR_INFO,
    )
    embed.set_footer(
        text=(
            "Tip: Use /help with a topic, or use 'help / >help with a topic name. "
            "Topics: roster, breeding, mutations, export, server"
        )
    )
    return embed


def _overview_embed() -> discord.Embed:
    embed = discord.Embed(
        title="ARK Bot Help",
        description=(
            "Detailed command guide by category.\n\n"
            "Available topics:\n"
            "• roster\n"
            "• breeding\n"
            "• mutations\n"
            "• export\n"
            "• server\n\n"
            "Use /help topic:<name> or run 'help <name> / >help <name>."
        ),
        colour=config.EMBED_COLOR_INFO,
    )

    embed.add_field(
        name="Quick Examples",
        value=(
            "/help topic:export\n"
            "'help breeding\n"
            ">help server"
        ),
        inline=False,
    )
    return embed


class HelpCog(commands.Cog, name="Help"):
    """Unified detailed help for slash and prefix commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="help",
        description="Detailed command guide with category filtering.",
    )
    @app_commands.describe(
        topic="Optional category: roster, breeding, mutations, export, or server",
    )
    @app_commands.choices(
        topic=[
            app_commands.Choice(name="Roster", value="roster"),
            app_commands.Choice(name="Breeding", value="breeding"),
            app_commands.Choice(name="Mutations", value="mutations"),
            app_commands.Choice(name="Export", value="export"),
            app_commands.Choice(name="Server Config", value="server"),
        ]
    )
    async def slash_help(
        self,
        interaction: discord.Interaction,
        topic: Optional[app_commands.Choice[str]] = None,
    ) -> None:
        if topic is None:
            await interaction.response.send_message(embed=_overview_embed(), ephemeral=True)
            return
        await interaction.response.send_message(embed=_topic_embed(topic.value), ephemeral=True)

    @commands.command(name="help", aliases=["h"])
    async def prefix_help(self, ctx: commands.Context, topic: Optional[str] = None) -> None:
        if topic is None:
            await ctx.send(embed=_overview_embed())
            return

        key = topic.lower().strip()
        if key not in HELP_TOPICS:
            await ctx.send(
                "Unknown help topic. Use one of: roster, breeding, mutations, export, server"
            )
            return

        await ctx.send(embed=_topic_embed(key))


async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))
