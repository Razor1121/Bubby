"""
breeding_calculator.py – Core ARK breeding mathematics and recommendations.

Key ARK mechanics modelled here:
  • Each of the 8 stats is independently inherited from either parent (50 / 50).
  • Every breeding attempt has a ~7.31 % chance of a mutation per parent
    (≈ 14.07 % total chance of at least one mutation per baby).
  • A mutation adds +2 wild levels to a randomly chosen stat and changes one
    colour region.
  • Each creature tracks a maternal and paternal mutation counter.
  • Once a parent's total mutation counter reaches ≥ 20, mutations originating
    from that parent's side become heavily suppressed (the "soft cap").
  • Strategy: keep one parent at 0 / 0 mutations ("clean") while stacking
    mutations on the other; the clean parent's mutation roll remains active.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from utils.ark_stats import STAT_NAMES, STAT_SHORT, STAT_EMOJI, UNLEVELLED_STATS
from config import MUTATION_CHANCE_PER_PARENT, MUTATION_SOFT_CAP

NUM_STATS = 8


# ── Data Model ────────────────────────────────────────────────────────────────

@dataclass
class Creature:
    """Lightweight representation of a creature used by the calculator."""
    name: str
    species: str
    gender: str                          # "Male" | "Female" | "Unknown"
    stats: list[int]                     # 8 wild stat point counts
    mut_maternal: int = 0
    mut_paternal: int = 0
    creature_id: Optional[int] = None

    @property
    def total_mutations(self) -> int:
        return self.mut_maternal + self.mut_paternal

    @property
    def mutation_label(self) -> str:
        return f"{self.mut_maternal}/{self.mut_paternal}"

    def stat_sum(self, exclude: set[int] = UNLEVELLED_STATS) -> int:
        """Sum of relevant (levellable) wild stat points."""
        return sum(v for i, v in enumerate(self.stats) if i not in exclude)


# ── Core Probability Helpers ──────────────────────────────────────────────────

def prob_no_mutation_from_parent(total_mutations: int) -> float:
    """
    Probability that a single parent does NOT contribute a mutation.
    Once a parent passes the soft cap the chance of a NEW mutation from
    their lineage drops to near zero; we model this as 0 extra chance.
    """
    if total_mutations >= MUTATION_SOFT_CAP:
        return 1.0  # suppressed – effectively 0 % new mutations
    return 1.0 - MUTATION_CHANCE_PER_PARENT


def prob_at_least_one_mutation(father: Creature, mother: Creature) -> float:
    """Overall probability of at least one mutation in a baby from this pair."""
    p_no_mut = (
        prob_no_mutation_from_parent(father.total_mutations)
        * prob_no_mutation_from_parent(mother.total_mutations)
    )
    return 1.0 - p_no_mut


def expected_attempts_for_mutation(father: Creature, mother: Creature) -> float:
    """Expected number of breeding attempts to get at least one mutation."""
    p = prob_at_least_one_mutation(father, mother)
    if p <= 0:
        return float("inf")
    return 1.0 / p


def prob_desired_mutation(
    father: Creature,
    mother: Creature,
    desired_stat_idx: int,
    num_mutable_stats: int = NUM_STATS,
) -> float:
    """
    Probability that a baby gets a mutation specifically in the desired stat.
    Each mutation hits a uniformly random one of the mutable stats.
    """
    p_any = prob_at_least_one_mutation(father, mother)
    return p_any / num_mutable_stats


# ── Stat Inheritance ──────────────────────────────────────────────────────────

@dataclass
class StatResult:
    stat_idx: int
    parent_a_val: int
    parent_b_val: int
    best_val: int
    worst_val: int
    both_equal: bool
    prob_get_best: float   # probability of inheriting the higher value


def analyse_stat_pair(
    stat_idx: int,
    val_a: int,
    val_b: int,
) -> StatResult:
    best  = max(val_a, val_b)
    worst = min(val_a, val_b)
    equal = val_a == val_b
    prob  = 1.0 if equal else 0.5
    return StatResult(
        stat_idx=stat_idx,
        parent_a_val=val_a,
        parent_b_val=val_b,
        best_val=best,
        worst_val=worst,
        both_equal=equal,
        prob_get_best=prob,
    )


# ── Breeding Analysis ─────────────────────────────────────────────────────────

@dataclass
class BreedingReport:
    parent_a: Creature
    parent_b: Creature
    stat_results: list[StatResult] = field(default_factory=list)

    # Probability of getting ALL desired stats at max in one baby.
    prob_all_max: float = 0.0

    # Expected attempts to produce a "perfect" baby (all desired stats max).
    expected_attempts_perfect: float = 0.0

    # Mutation analysis.
    prob_any_mutation: float = 0.0
    expected_attempts_any_mutation: float = 0.0

    # Warnings.
    warnings: list[str] = field(default_factory=list)


def analyse_pair(
    parent_a: Creature,
    parent_b: Creature,
    desired_stats: Optional[list[int]] = None,
) -> BreedingReport:
    """
    Full breeding analysis for a pair of creatures.

    Parameters
    ----------
    parent_a, parent_b:
        The two parents.  Gender is handled by the caller; the calculator is
        gender-agnostic (the math is symmetric).
    desired_stats:
        List of stat indices the user cares about maximising.
        Defaults to all stats except UNLEVELLED_STATS (Oxygen, Speed, Torp).
    """
    if desired_stats is None:
        desired_stats = [i for i in range(NUM_STATS) if i not in UNLEVELLED_STATS]

    report = BreedingReport(parent_a=parent_a, parent_b=parent_b)

    prob_all = 1.0
    for idx in range(NUM_STATS):
        sr = analyse_stat_pair(idx, parent_a.stats[idx], parent_b.stats[idx])
        report.stat_results.append(sr)
        if idx in desired_stats:
            prob_all *= sr.prob_get_best

    report.prob_all_max = prob_all
    report.expected_attempts_perfect = (
        1.0 / prob_all if prob_all > 0 else float("inf")
    )

    # Determine which is father / mother for mutation calc.
    # If genders don't match the typical male/female pairing, just use both.
    father = parent_a if parent_a.gender == "Male" else parent_b
    mother = parent_b if parent_b.gender == "Female" else parent_a

    report.prob_any_mutation = prob_at_least_one_mutation(father, mother)
    report.expected_attempts_any_mutation = expected_attempts_for_mutation(
        father, mother
    )

    # Warnings
    for p in (parent_a, parent_b):
        if p.total_mutations >= MUTATION_SOFT_CAP:
            report.warnings.append(
                f"⚠️ **{p.name}** has {p.total_mutations} total mutations "
                f"({p.mutation_label}) — at or above the soft cap ({MUTATION_SOFT_CAP}). "
                f"New mutations from this parent's lineage are suppressed."
            )
        elif p.total_mutations >= MUTATION_SOFT_CAP - 3:
            report.warnings.append(
                f"⚠️ **{p.name}** is close to the mutation soft cap "
                f"({p.total_mutations}/{MUTATION_SOFT_CAP}). "
                f"Consider finding a cleaner replacement soon."
            )

    return report


# ── Best Pair Selection ───────────────────────────────────────────────────────

def score_pair(
    a: Creature,
    b: Creature,
    desired_stats: list[int],
) -> float:
    """
    Score a pair of creatures for breeding.

    Higher is better.  The score is the sum of the per-stat best values for
    the desired stats, multiplied by the probability of producing a baby with
    all of them.
    """
    stat_report = analyse_pair(a, b, desired_stats)
    base_score  = sum(
        stat_report.stat_results[i].best_val
        for i in desired_stats
    )
    return base_score * stat_report.prob_all_max


def find_best_pairs(
    creatures: list[Creature],
    desired_stats: Optional[list[int]] = None,
    top_n: int = 5,
) -> list[tuple[Creature, Creature, BreedingReport]]:
    """
    Evaluate all valid male × female pairs and return the top N by score.
    Falls back to any-gender pairs if there are no clearly-gendered pairs.
    """
    if desired_stats is None:
        desired_stats = [i for i in range(NUM_STATS) if i not in UNLEVELLED_STATS]

    males   = [c for c in creatures if c.gender == "Male"]
    females = [c for c in creatures if c.gender == "Female"]

    # If no clear male/female split, try all unique unordered pairs.
    if not males or not females:
        candidates = [
            (creatures[i], creatures[j])
            for i in range(len(creatures))
            for j in range(i + 1, len(creatures))
        ]
    else:
        candidates = [(m, f) for m in males for f in females]

    scored: list[tuple[float, Creature, Creature, BreedingReport]] = []
    for a, b in candidates:
        report = analyse_pair(a, b, desired_stats)
        s      = score_pair(a, b, desired_stats)
        scored.append((s, a, b, report))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [(a, b, r) for _, a, b, r in scored[:top_n]]


# ── Mutation Stacking Advice ──────────────────────────────────────────────────

@dataclass
class MutationAdvice:
    target_stat_idx: int
    stacking_parent: Creature       # parent accumulating mutations
    clean_parent_desc: str          # description of what the "clean" parent should be
    prob_per_attempt: float
    expected_attempts: float
    generation_estimate: int        # rough estimate of breeding generations needed
    advice_lines: list[str] = field(default_factory=list)


def mutation_stacking_advice(
    mutated_parent: Creature,
    clean_parent: Creature,
    target_stat_idx: int,
    current_mutations_in_stat: int = 0,
    desired_mutations_in_stat: int = 1,
) -> MutationAdvice:
    """
    Generate human-readable step-by-step mutation stacking advice.
    """
    father = mutated_parent if mutated_parent.gender == "Male" else clean_parent
    mother = clean_parent   if clean_parent.gender   == "Female" else mutated_parent

    p_any   = prob_at_least_one_mutation(father, mother)
    p_stat  = p_any / NUM_STATS
    needed  = max(0, desired_mutations_in_stat - current_mutations_in_stat)
    exp_att = math.ceil(1.0 / p_stat) if p_stat > 0 else 999_999
    gen_est = needed * exp_att

    stat_name = STAT_NAMES[target_stat_idx]

    lines = [
        f"**Goal:** +{needed} mutation(s) in **{stat_name}** "
        f"(need {desired_mutations_in_stat}, have {current_mutations_in_stat}).",
        "",
        "**Strategy – Clean Female Method:**",
        f"1. Keep **{clean_parent.name}** (or a fresh clean female with 0 mutations) "
        f"as the mother each generation.",
        f"2. Breed her with **{mutated_parent.name}** (the mutation male).",
        f"3. Each attempt has a **{p_any*100:.1f}%** chance of any mutation "
        f"and a **{p_stat*100:.2f}%** chance of hitting **{stat_name}**.",
        f"4. Expected attempts per desired mutation: **~{exp_att}**.",
        f"5. When a baby is born with the wanted mutation:",
        f"   • If male → replace the current mutation male with the new one.",
        f"   • If female → breed back to the mutation male to clone the mutation onto a male.",
        f"6. Repeat until you have {desired_mutations_in_stat} stack(s) in {stat_name}.",
        "",
    ]

    # Warn if mutation stacking parent is near the soft cap
    if mutated_parent.total_mutations >= MUTATION_SOFT_CAP:
        lines.append(
            f"⚠️ **{mutated_parent.name}** is at/above the soft cap "
            f"({mutated_parent.total_mutations} mutations). "
            "Mutations from this side are suppressed — find a cleaner stacking male."
        )
    elif mutated_parent.total_mutations >= MUTATION_SOFT_CAP - 5:
        lines.append(
            f"⚠️ **{mutated_parent.name}** has {mutated_parent.total_mutations} mutations "
            f"— approaching soft cap. Plan to swap stacking males soon."
        )

    if clean_parent.total_mutations > 0:
        lines.append(
            f"⚠️ **{clean_parent.name}** has {clean_parent.total_mutations} mutation(s). "
            "For optimal stacking, use a 0/0 clean female."
        )

    return MutationAdvice(
        target_stat_idx=target_stat_idx,
        stacking_parent=mutated_parent,
        clean_parent_desc=clean_parent.name,
        prob_per_attempt=p_stat,
        expected_attempts=exp_att,
        generation_estimate=gen_est,
        advice_lines=lines,
    )


# ── Formatting Helpers ────────────────────────────────────────────────────────

def format_report_embed_fields(report: BreedingReport) -> list[dict]:
    """
    Convert a BreedingReport into a list of Discord embed field dicts.
    Returns fields that can be iterated over and added to a discord.Embed.
    """
    fields = []

    # Per-stat breakdown
    stat_lines = []
    for sr in report.stat_results:
        em    = STAT_EMOJI[sr.stat_idx]
        name  = STAT_SHORT[sr.stat_idx]
        if sr.both_equal:
            line = f"{em} **{name:<6}** {sr.best_val:>3} pts  (both equal ✅)"
        else:
            better_parent = (
                report.parent_a.name
                if report.parent_a.stats[sr.stat_idx] == sr.best_val
                else report.parent_b.name
            )
            line = (
                f"{em} **{name:<6}** {sr.best_val:>3} pts  "
                f"(50% — from {better_parent})"
            )
        stat_lines.append(line)

    fields.append({
        "name": "📊 Stat Inheritance",
        "value": "\n".join(stat_lines),
        "inline": False,
    })

    # Summary probabilities
    prob_pct = report.prob_all_max * 100
    exp      = report.expected_attempts_perfect
    exp_str  = f"~{exp:,.0f}" if exp < 1_000_000 else "∞"
    mut_pct  = report.prob_any_mutation * 100

    fields.append({
        "name": "🎲 Odds",
        "value": (
            f"Chance of all-max stat baby: **{prob_pct:.2f}%** "
            f"(~1 in {exp_str} attempts)\n"
            f"Chance of mutation per baby: **{mut_pct:.2f}%** "
            f"(~1 in {report.expected_attempts_any_mutation:.0f} attempts)"
        ),
        "inline": False,
    })

    # Warnings
    if report.warnings:
        fields.append({
            "name": "⚠️ Warnings",
            "value": "\n".join(report.warnings),
            "inline": False,
        })

    return fields
