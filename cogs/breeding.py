"""
cogs/breeding.py – Breeding analysis slash commands.

Commands
--------
/breed      – Analyse a specific male × female pairing.
/best_pair  – Find the top breeding pairs for a species from the roster.
/stat_check – Show which creatures hold the highest value for a given stat.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

import config
from utils import database as db
from utils.database import row_to_stats
from utils.ark_stats import (
    STAT_NAMES, STAT_SHORT, STAT_EMOJI, UNLEVELLED_STATS
)
from utils.breeding_calculator import (
    Creature,
    BreedingReport,
    analyse_pair,
    find_best_pairs,
    format_report_embed_fields,
    NUM_STATS,
)
from cogs.creatures import species_autocomplete
from utils.prefix_adapter import as_interaction


# ── Helpers ───────────────────────────────────────────────────────────────────

def db_row_to_creature(row: dict) -> Creature:
    return Creature(
        name         = row["name"],
        species      = row["species"],
        gender       = row["gender"],
        stats        = row_to_stats(row),
        mut_maternal = row["mut_maternal"],
        mut_paternal = row["mut_paternal"],
        creature_id  = row["id"],
    )


def build_breed_embed(report: BreedingReport) -> discord.Embed:
    pa = report.parent_a
    pb = report.parent_b
    gender_a = {"Male": "♂️", "Female": "♀️"}.get(pa.gender, "❓")
    gender_b = {"Male": "♂️", "Female": "♀️"}.get(pb.gender, "❓")

    embed = discord.Embed(
        title=(
            f"🧬 Breeding Analysis\n"
            f"{gender_a} {pa.name}  ×  {gender_b} {pb.name}"
        ),
        colour=config.EMBED_COLOR,
    )
    embed.add_field(
        name="Parent A",
        value=(
            f"**{pa.name}** ({pa.species})\n"
            f"Mut: {pa.mutation_label}  |  "
            f"Stat sum: {pa.stat_sum()}"
        ),
        inline=True,
    )
    embed.add_field(
        name="Parent B",
        value=(
            f"**{pb.name}** ({pb.species})\n"
            f"Mut: {pb.mutation_label}  |  "
            f"Stat sum: {pb.stat_sum()}"
        ),
        inline=True,
    )

    for field in format_report_embed_fields(report):
        embed.add_field(**field)

    # Tip on which stats still need improvement
    missing = []
    for sr in report.stat_results:
        if sr.stat_idx in UNLEVELLED_STATS:
            continue
        if not sr.both_equal:
            missing.append(
                f"{STAT_EMOJI[sr.stat_idx]} {STAT_SHORT[sr.stat_idx]} "
                f"({sr.worst_val} → {sr.best_val})"
            )
    if missing:
        embed.add_field(
            name="💡 Stats to improve",
            value="\n".join(missing),
            inline=False,
        )
    else:
        embed.add_field(
            name="💡 Stats",
            value="Both parents have matching values in all key stats. "
                  "Focus on mutation stacking!",
            inline=False,
        )

    return embed


# ── Stat selector for /best_pair ──────────────────────────────────────────────

STAT_CHOICES = [
    app_commands.Choice(name=STAT_NAMES[i], value=i)
    for i in range(NUM_STATS)
    if i not in UNLEVELLED_STATS
]


# ── Cog ───────────────────────────────────────────────────────────────────────

class BreedingCog(commands.Cog, name="Breeding"):
    """ARK breeding analysis and pair-finding."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _stat_choice_from_text(self, value: str) -> app_commands.Choice[int] | None:
        cleaned = value.strip().lower()
        for choice in STAT_CHOICES:
            if choice.name.lower() == cleaned:
                return app_commands.Choice(name=choice.name, value=choice.value)
        if cleaned.isdigit():
            idx = int(cleaned)
            for choice in STAT_CHOICES:
                if choice.value == idx:
                    return app_commands.Choice(name=choice.name, value=choice.value)
        return None

    @commands.command(name="breed")
    async def breed_prefix(
        self,
        ctx: commands.Context,
        parent_a_id: int,
        parent_b_id: int,
    ) -> None:
        adapter = as_interaction(ctx)
        await BreedingCog.breed.callback(
            self,
            adapter,
            parent_a_id=parent_a_id,
            parent_b_id=parent_b_id,
        )

    @commands.command(name="best_pair")
    async def best_pair_prefix(
        self,
        ctx: commands.Context,
        species: str,
        top: int = 5,
        ignore_speed: bool = True,
        ignore_oxy: bool = True,
        ignore_torp: bool = True,
    ) -> None:
        adapter = as_interaction(ctx)
        await BreedingCog.best_pair.callback(
            self,
            adapter,
            species=species,
            top=top,
            ignore_speed=ignore_speed,
            ignore_oxy=ignore_oxy,
            ignore_torp=ignore_torp,
        )

    @commands.command(name="stat_check")
    async def stat_check_prefix(
        self,
        ctx: commands.Context,
        stat: str,
        species: Optional[str] = None,
        top: int = 10,
    ) -> None:
        stat_choice = self._stat_choice_from_text(stat)
        if stat_choice is None:
            await ctx.send("Unknown stat. Use a stat name (for example: Health) or index.")
            return
        adapter = as_interaction(ctx)
        await BreedingCog.stat_check.callback(
            self,
            adapter,
            stat=stat_choice,
            species=species,
            top=top,
        )

    # ── /breed ────────────────────────────────────────────────────────────────

    @app_commands.command(
        name="breed",
        description="Analyse a breeding pair and see stat inheritance odds.",
    )
    @app_commands.describe(
        parent_a_id = "ID of the first parent (use /list_creatures)",
        parent_b_id = "ID of the second parent",
    )
    async def breed(
        self,
        interaction: discord.Interaction,
        parent_a_id: int,
        parent_b_id: int,
    ):
        await interaction.response.defer()
        guild_id = str(interaction.guild_id)

        row_a = await db.get_creature_by_id(parent_a_id, guild_id)
        row_b = await db.get_creature_by_id(parent_b_id, guild_id)

        if not row_a:
            await interaction.followup.send(
                f"Parent A (ID **#{parent_a_id}**) not found.", ephemeral=True
            )
            return
        if not row_b:
            await interaction.followup.send(
                f"Parent B (ID **#{parent_b_id}**) not found.", ephemeral=True
            )
            return
        if row_a["species"].lower() != row_b["species"].lower():
            await interaction.followup.send(
                f"⚠️ Species mismatch: **{row_a['species']}** vs **{row_b['species']}**. "
                "In ARK, only creatures of the same species can breed. Proceeding anyway…"
            )

        creature_a = db_row_to_creature(row_a)
        creature_b = db_row_to_creature(row_b)
        report     = analyse_pair(creature_a, creature_b)
        embed      = build_breed_embed(report)
        await interaction.followup.send(embed=embed)

    # ── /best_pair ────────────────────────────────────────────────────────────

    @app_commands.command(
        name="best_pair",
        description="Find the top breeding pairs for a species from your roster.",
    )
    @app_commands.describe(
        species      = "Species to evaluate",
        top          = "Number of top pairs to show (1-10, default 5)",
        ignore_speed = "Exclude Movement Speed from scoring (recommended for most dinos)",
        ignore_oxy   = "Exclude Oxygen from scoring",
        ignore_torp  = "Always excluded. Here for clarity.",
    )
    @app_commands.autocomplete(species=species_autocomplete)
    async def best_pair(
        self,
        interaction: discord.Interaction,
        species: str,
        top: int = 5,
        ignore_speed: bool = True,
        ignore_oxy:   bool = True,
        ignore_torp:  bool = True,
    ):
        await interaction.response.defer()
        guild_id = str(interaction.guild_id)

        top = max(1, min(10, top))

        rows = await db.list_creatures(guild_id=guild_id, species=species)
        if len(rows) < 2:
            await interaction.followup.send(
                f"Need at least **2** registered {species} to find pairs. "
                f"Currently have {len(rows)}.",
                ephemeral=True,
            )
            return

        # Build desired stat list
        excluded = {7}  # Torpidity always excluded
        if ignore_speed: excluded.add(6)
        if ignore_oxy:   excluded.add(2)
        desired = [i for i in range(NUM_STATS) if i not in excluded]

        creatures = [db_row_to_creature(r) for r in rows]
        best      = find_best_pairs(creatures, desired_stats=desired, top_n=top)

        embed = discord.Embed(
            title=f"🏆 Top {len(best)} Breeding Pair(s) — {species}",
            colour=config.EMBED_COLOR,
        )
        embed.set_footer(
            text=(
                f"Scored on stats: "
                + ", ".join(STAT_SHORT[i] for i in desired)
                + f"  |  From {len(rows)} registered {species}"
            )
        )

        for rank, (pa, pb, report) in enumerate(best, start=1):
            gender_a = {"Male": "♂️", "Female": "♀️"}.get(pa.gender, "❓")
            gender_b = {"Male": "♂️", "Female": "♀️"}.get(pb.gender, "❓")
            prob_pct = report.prob_all_max * 100
            mut_pct  = report.prob_any_mutation * 100

            # Per-stat line
            stat_parts = []
            for sr in report.stat_results:
                if sr.stat_idx in excluded:
                    continue
                em = STAT_EMOJI[sr.stat_idx]
                check = "✅" if sr.both_equal else "⚡"
                stat_parts.append(f"{em}{sr.best_val}{check}")

            warnings = "  ".join(report.warnings) if report.warnings else ""

            embed.add_field(
                name=f"#{rank}  {gender_a} {pa.name}  ×  {gender_b} {pb.name}",
                value=(
                    f"**Stats:** {' '.join(stat_parts)}\n"
                    f"Mut: {pa.mutation_label} × {pb.mutation_label}  |  "
                    f"Perf. baby: **{prob_pct:.2f}%**  |  "
                    f"Any mutation: **{mut_pct:.2f}%**\n"
                    + (f"{warnings}" if warnings else "")
                ),
                inline=False,
            )

        await interaction.followup.send(embed=embed)

    # ── /stat_check ───────────────────────────────────────────────────────────

    @app_commands.command(
        name="stat_check",
        description="See which creatures hold the highest value for a specific stat.",
    )
    @app_commands.describe(
        stat    = "The stat to rank by",
        species = "Filter by species (optional)",
        top     = "Number of creatures to show (default 10)",
    )
    @app_commands.choices(stat=STAT_CHOICES)
    @app_commands.autocomplete(species=species_autocomplete)
    async def stat_check(
        self,
        interaction: discord.Interaction,
        stat: app_commands.Choice[int],
        species: Optional[str] = None,
        top: int = 10,
    ):
        await interaction.response.defer()
        guild_id = str(interaction.guild_id)
        top      = max(1, min(25, top))

        rows = await db.list_creatures(guild_id=guild_id, species=species)
        if not rows:
            await interaction.followup.send(
                "No creatures found for those filters.", ephemeral=True
            )
            return

        stat_idx  = stat.value
        col       = db.STAT_COLUMNS[stat_idx]
        sorted_rows = sorted(rows, key=lambda r: r[col], reverse=True)[:top]

        embed = discord.Embed(
            title=(
                f"{STAT_EMOJI[stat_idx]} Top {len(sorted_rows)} "
                f"{stat.name} — {species or 'All Species'}"
            ),
            colour=config.EMBED_COLOR,
        )
        lines = []
        for i, r in enumerate(sorted_rows, start=1):
            g = {"Male": "♂️", "Female": "♀️"}.get(r["gender"], "❓")
            mut = f"{r['mut_maternal']}/{r['mut_paternal']}"
            lines.append(
                f"`{i:>2}.` {g} **{r['name']}** *{r['species']}*  "
                f"— **{r[col]} pts**  |  Mut: {mut}  `#{r['id']}`"
            )
        embed.description = "\n".join(lines)
        await interaction.followup.send(embed=embed)


# ── Setup ─────────────────────────────────────────────────────────────────────

async def setup(bot: commands.Bot):
    await bot.add_cog(BreedingCog(bot))
