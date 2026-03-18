"""
cogs/mutations.py – Mutation tracking, advice, and stacking guidance.

Commands
--------
/mutation_status  – Show mutation counter summary for a species or creature.
/stacking_guide   – Step-by-step mutation stacking plan for a target stat.
/mutation_calc    – Calculate how many attempts are needed for N mutations
                    in a specific stat.
"""

from __future__ import annotations

import math
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

import config
from utils import database as db
from utils.database import row_to_stats
from utils.ark_stats import STAT_NAMES, STAT_SHORT, STAT_EMOJI, UNLEVELLED_STATS
from utils.breeding_calculator import (
    Creature,
    mutation_stacking_advice,
    prob_at_least_one_mutation,
    prob_desired_mutation,
    NUM_STATS,
)
from cogs.creatures import species_autocomplete
from cogs.breeding import db_row_to_creature, STAT_CHOICES
from utils.prefix_adapter import as_interaction


# ── Helpers ───────────────────────────────────────────────────────────────────

def mutation_bar(current: int, cap: int = config.MUTATION_SOFT_CAP) -> str:
    """
    Returns a visual bar like: ▓▓▓▓▓▓░░░░░░░░░░░░░░ 10/20
    """
    filled = min(current, cap)
    bar    = "▓" * filled + "░" * max(0, cap - filled)
    over   = f" +{current - cap}" if current > cap else ""
    return f"`{bar}` {current}/{cap}{over}"


def colour_for_mut(total: int) -> int:
    if total >= config.MUTATION_SOFT_CAP:
        return config.EMBED_COLOR_ERROR
    if total >= config.MUTATION_SOFT_CAP - 5:
        return config.EMBED_COLOR_WARN
    return config.EMBED_COLOR


# ── Cog ───────────────────────────────────────────────────────────────────────

class MutationsCog(commands.Cog, name="Mutations"):
    """ARK mutation tracking and stacking guidance."""

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

    @commands.command(name="mutation_status")
    async def mutation_status_prefix(
        self,
        ctx: commands.Context,
        species: Optional[str] = None,
        creature_id: Optional[int] = None,
    ) -> None:
        adapter = as_interaction(ctx)
        await MutationsCog.mutation_status.callback(
            self,
            adapter,
            species=species,
            creature_id=creature_id,
        )

    @commands.command(name="stacking_guide")
    async def stacking_guide_prefix(
        self,
        ctx: commands.Context,
        mutation_male_id: int,
        clean_female_id: int,
        target_stat: str,
        current_stack: int = 0,
        desired_stack: int = 1,
    ) -> None:
        target_choice = self._stat_choice_from_text(target_stat)
        if target_choice is None:
            await ctx.send("Unknown target_stat. Use a stat name (for example: Melee Damage) or index.")
            return
        adapter = as_interaction(ctx)
        await MutationsCog.stacking_guide.callback(
            self,
            adapter,
            mutation_male_id=mutation_male_id,
            clean_female_id=clean_female_id,
            target_stat=target_choice,
            current_stack=current_stack,
            desired_stack=desired_stack,
        )

    @commands.command(name="mutation_calc")
    async def mutation_calc_prefix(
        self,
        ctx: commands.Context,
        father_mutations: int = 0,
        mother_mutations: int = 0,
        desired_stat: Optional[str] = None,
        desired_count: int = 1,
    ) -> None:
        desired_stat_choice: Optional[app_commands.Choice[int]] = None
        if desired_stat is not None:
            desired_stat_choice = self._stat_choice_from_text(desired_stat)
            if desired_stat_choice is None:
                await ctx.send("Unknown desired_stat. Use a stat name (for example: Health) or index.")
                return

        adapter = as_interaction(ctx)
        await MutationsCog.mutation_calc.callback(
            self,
            adapter,
            father_mutations=father_mutations,
            mother_mutations=mother_mutations,
            desired_stat=desired_stat_choice,
            desired_count=desired_count,
        )

    # ── /mutation_status ──────────────────────────────────────────────────────

    @app_commands.command(
        name="mutation_status",
        description="Show mutation counters for all creatures of a species.",
    )
    @app_commands.describe(
        species     = "Species to check",
        creature_id = "Or check a single creature by ID",
    )
    @app_commands.autocomplete(species=species_autocomplete)
    async def mutation_status(
        self,
        interaction: discord.Interaction,
        species: Optional[str] = None,
        creature_id: Optional[int] = None,
    ):
        await interaction.response.defer()
        guild_id = str(interaction.guild_id)

        # ── Single creature ───────────────────────────────────────────────────
        if creature_id is not None:
            row = await db.get_creature_by_id(creature_id, guild_id)
            if not row:
                await interaction.followup.send(
                    f"No creature with ID **#{creature_id}** found.", ephemeral=True
                )
                return

            total  = row["mut_maternal"] + row["mut_paternal"]
            colour = colour_for_mut(total)
            g      = {"Male": "♂️", "Female": "♀️"}.get(row["gender"], "❓")
            embed  = discord.Embed(
                title=f"🧬 Mutation Status — {g} {row['name']}",
                colour=colour,
            )
            embed.add_field(
                name="Maternal",
                value=mutation_bar(row["mut_maternal"]),
                inline=False,
            )
            embed.add_field(
                name="Paternal",
                value=mutation_bar(row["mut_paternal"]),
                inline=False,
            )
            embed.add_field(
                name="Total",
                value=f"**{total}** mutation(s)  {mutation_bar(total)}",
                inline=False,
            )
            if total >= config.MUTATION_SOFT_CAP:
                embed.add_field(
                    name="⚠️ Soft Cap Reached",
                    value=(
                        "This creature has hit the soft cap. New mutations from "
                        "this parent's lineage are suppressed. Consider breeding "
                        "to a clean (0/0) partner to continue mutation stacking."
                    ),
                    inline=False,
                )
            await interaction.followup.send(embed=embed)
            return

        # ── All creatures of a species ─────────────────────────────────────────
        if not species:
            await interaction.followup.send(
                "Please specify a species or a creature ID.", ephemeral=True
            )
            return

        rows = await db.list_creatures(guild_id=guild_id, species=species)
        if not rows:
            await interaction.followup.send(
                f"No {species} found in the roster.", ephemeral=True
            )
            return

        rows_sorted = sorted(
            rows, key=lambda r: r["mut_maternal"] + r["mut_paternal"]
        )

        embed = discord.Embed(
            title=f"🧬 Mutation Status — {species}  ({len(rows)} total)",
            colour=config.EMBED_COLOR,
        )

        lines   = []
        at_cap  = []
        cleanest: Optional[dict] = None

        for r in rows_sorted:
            total = r["mut_maternal"] + r["mut_paternal"]
            g     = {"Male": "♂️", "Female": "♀️"}.get(r["gender"], "❓")
            warn  = "  ⚠️" if total >= config.MUTATION_SOFT_CAP else ""
            lines.append(
                f"`#{r['id']:>4}` {g} **{r['name']}**  "
                f"{r['mut_maternal']}/{r['mut_paternal']} (total {total}){warn}"
            )
            if total >= config.MUTATION_SOFT_CAP:
                at_cap.append(r["name"])
            if cleanest is None or total < (
                cleanest["mut_maternal"] + cleanest["mut_paternal"]
            ):
                cleanest = r

        embed.description = "\n".join(lines)

        if cleanest:
            c_total = cleanest["mut_maternal"] + cleanest["mut_paternal"]
            embed.add_field(
                name="🌿 Cleanest",
                value=f"**{cleanest['name']}** — {c_total} total mutations",
                inline=True,
            )
        if at_cap:
            embed.add_field(
                name="⚠️ At Soft Cap",
                value=", ".join(at_cap),
                inline=True,
            )

        await interaction.followup.send(embed=embed)

    # ── /stacking_guide ───────────────────────────────────────────────────────

    @app_commands.command(
        name="stacking_guide",
        description="Get a step-by-step mutation stacking plan for a target stat.",
    )
    @app_commands.describe(
        mutation_male_id   = "ID of your current mutation-accumulating male",
        clean_female_id    = "ID of the clean female (ideally 0/0 mutations)",
        target_stat        = "The stat you want to stack mutations in",
        current_stack      = "How many mutations you already have in that stat",
        desired_stack      = "How many total mutations you want in that stat",
    )
    @app_commands.choices(target_stat=STAT_CHOICES)
    async def stacking_guide(
        self,
        interaction: discord.Interaction,
        mutation_male_id: int,
        clean_female_id: int,
        target_stat: app_commands.Choice[int],
        current_stack: int = 0,
        desired_stack: int = 1,
    ):
        await interaction.response.defer()
        guild_id = str(interaction.guild_id)

        row_m = await db.get_creature_by_id(mutation_male_id,  guild_id)
        row_f = await db.get_creature_by_id(clean_female_id,   guild_id)

        if not row_m:
            await interaction.followup.send(
                f"Mutation male ID **#{mutation_male_id}** not found.", ephemeral=True
            )
            return
        if not row_f:
            await interaction.followup.send(
                f"Clean female ID **#{clean_female_id}** not found.", ephemeral=True
            )
            return

        mutated_parent = db_row_to_creature(row_m)
        clean_parent   = db_row_to_creature(row_f)

        advice = mutation_stacking_advice(
            mutated_parent            = mutated_parent,
            clean_parent              = clean_parent,
            target_stat_idx           = target_stat.value,
            current_mutations_in_stat = current_stack,
            desired_mutations_in_stat = desired_stack,
        )

        embed = discord.Embed(
            title=(
                f"🎯 Mutation Stacking Guide\n"
                f"{STAT_EMOJI[target_stat.value]} {target_stat.name}  |  "
                f"{current_stack} → {desired_stack} mutation(s)"
            ),
            colour=colour_for_mut(mutated_parent.total_mutations),
        )

        embed.add_field(
            name="Parents",
            value=(
                f"♂️ **{mutated_parent.name}**  Mut: {mutated_parent.mutation_label}\n"
                f"♀️ **{clean_parent.name}**  Mut: {clean_parent.mutation_label}"
            ),
            inline=False,
        )
        embed.add_field(
            name="📋 Stacking Plan",
            value="\n".join(advice.advice_lines) or "No advice generated.",
            inline=False,
        )

        # Stat snapshot for both parents
        stat_lines = []
        for idx in range(NUM_STATS):
            if idx in UNLEVELLED_STATS:
                continue
            em    = STAT_EMOJI[idx]
            short = STAT_SHORT[idx]
            m_val = mutated_parent.stats[idx]
            f_val = clean_parent.stats[idx]
            best  = max(m_val, f_val)
            stat_lines.append(f"{em} **{short:<6}** ♂️{m_val} / ♀️{f_val}  → best {best}")
        embed.add_field(
            name="📊 Stat Comparison",
            value="\n".join(stat_lines),
            inline=False,
        )

        await interaction.followup.send(embed=embed)

    # ── /mutation_calc ────────────────────────────────────────────────────────

    @app_commands.command(
        name="mutation_calc",
        description="Calculate expected attempts and odds for mutation stacking.",
    )
    @app_commands.describe(
        father_mutations = "Total mutations of the father (mat+pat)",
        mother_mutations = "Total mutations of the mother (mat+pat)",
        desired_stat     = "Target stat for the mutation (optional, for per-stat odds)",
        desired_count    = "How many mutations in that stat you want",
    )
    @app_commands.choices(desired_stat=STAT_CHOICES)
    async def mutation_calc(
        self,
        interaction: discord.Interaction,
        father_mutations: int = 0,
        mother_mutations: int = 0,
        desired_stat: Optional[app_commands.Choice[int]] = None,
        desired_count: int = 1,
    ):
        await interaction.response.defer(ephemeral=True)

        # Build dummy creatures for the calculator
        dummy_father = Creature(
            name="Father", species="?", gender="Male",
            stats=[0]*8, mut_maternal=0, mut_paternal=father_mutations,
        )
        dummy_mother = Creature(
            name="Mother", species="?", gender="Female",
            stats=[0]*8, mut_maternal=0, mut_paternal=mother_mutations,
        )

        p_any  = prob_at_least_one_mutation(dummy_father, dummy_mother)
        e_any  = 1 / p_any if p_any > 0 else float("inf")

        embed = discord.Embed(
            title="🎲 Mutation Probability Calculator",
            colour=config.EMBED_COLOR_INFO,
        )
        embed.add_field(
            name="Setup",
            value=(
                f"♂️ Father total mutations: **{father_mutations}**\n"
                f"♀️ Mother total mutations: **{mother_mutations}**"
            ),
            inline=False,
        )
        cap = config.MUTATION_SOFT_CAP
        f_note = f" ⚠️ At/above soft cap ({cap})" if father_mutations >= cap else ""
        m_note = f" ⚠️ At/above soft cap ({cap})" if mother_mutations >= cap else ""
        embed.add_field(
            name="Any Mutation",
            value=(
                f"Chance per baby: **{p_any*100:.2f}%**{f_note}{m_note}\n"
                f"Expected attempts for at least 1: **~{e_any:.0f}**"
            ),
            inline=False,
        )

        if desired_stat is not None:
            p_stat  = prob_desired_mutation(dummy_father, dummy_mother, desired_stat.value)
            e_stat  = 1 / p_stat if p_stat > 0 else float("inf")
            e_total = math.ceil(e_stat) * desired_count

            # Probability of getting N mutations in exactly E attempts (rough)
            prob_n_in_attempts = []
            checkpoints = [10, 25, 50, 100, 200, 500]
            for attempts in checkpoints:
                p_at_least_n = 0.0
                # Binomial: P(X >= desired_count) where X ~ Bin(attempts, p_stat)
                from math import comb
                p_at_least_n = sum(
                    comb(attempts, k) * (p_stat ** k) * ((1 - p_stat) ** (attempts - k))
                    for k in range(desired_count, attempts + 1)
                )
                prob_n_in_attempts.append((attempts, p_at_least_n))

            stat_lines = "\n".join(
                f"{att:>5} attempts → **{p*100:.1f}%** chance"
                for att, p in prob_n_in_attempts
            )

            embed.add_field(
                name=(
                    f"{STAT_EMOJI[desired_stat.value]} "
                    f"{desired_stat.name} — {desired_count} mutation(s)"
                ),
                value=(
                    f"Chance per baby: **{p_stat*100:.3f}%**\n"
                    f"Expected attempts: **~{e_stat:.0f}** per mutation\n"
                    f"Total expected for {desired_count} stack(s): **~{e_total}**\n\n"
                    f"**Cumulative success probability:**\n{stat_lines}"
                ),
                inline=False,
            )

        await interaction.followup.send(embed=embed)


# ── Setup ─────────────────────────────────────────────────────────────────────

async def setup(bot: commands.Bot):
    await bot.add_cog(MutationsCog(bot))
