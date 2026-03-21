"""
ark_stats.py – ARK Survival Evolved / Ascended game constants.

All references to in-game stats use the following stat indices:
  0 = Health          4 = Weight
  1 = Stamina         5 = Melee Damage
  2 = Oxygen          6 = Movement Speed
  3 = Food            7 = Torpidity
"""

from typing import Dict, Any

# ── Stat Metadata ─────────────────────────────────────────────────────────────

STAT_INDEX: Dict[str, int] = {
    "hp":       0,
    "health":   0,
    "stamina":  1,
    "stam":     1,
    "oxygen":   2,
    "oxy":      2,
    "food":     3,
    "weight":   4,
    "wt":       4,
    "melee":    5,
    "speed":    6,
    "torpidity":7,
    "torp":     7,
}

STAT_NAMES: Dict[int, str] = {
    0: "Health",
    1: "Stamina",
    2: "Oxygen",
    3: "Food",
    4: "Weight",
    5: "Melee Damage",
    6: "Movement Speed",
    7: "Torpidity",
}

STAT_SHORT: Dict[int, str] = {
    0: "HP",
    1: "Stam",
    2: "Oxy",
    3: "Food",
    4: "Wt",
    5: "Melee",
    6: "Speed",
    7: "Torp",
}

STAT_EMOJI: Dict[int, str] = {
    0: "❤️",
    1: "⚡",
    2: "💨",
    3: "🍗",
    4: "⚖️",
    5: "⚔️",
    6: "🏃",
    7: "😴",
}

# Stats that cannot be levelled in the wild (or are irrelevant for breeding
# optimisation goals).  They are still displayed but excluded from "best pair"
# scoring unless the user explicitly requests them.
UNLEVELLED_STATS: set = {2, 6, 7}  # Oxygen*, Speed, Torpidity
# * Oxygen is levelled on aquatic creatures but commonly ignored on land dinos.

# ── Common Species ────────────────────────────────────────────────────────────
# Base stat values and per-wild-level increases.
# Format per species:
#   "base"          – base stat at level 1 (before any wild levels)
#   "inc_wild"      – increase per wild level (additive)
#   "inc_tamed"     – increase per tamed/player level (multiplicative %)
#
# Sources: ARK wiki / ARK Smart Breeding tool.
# Only the most commonly bred species are listed here; arbitrary species can
# still be added as creatures using their raw wild-stat-point counts.

SPECIES_STATS: Dict[str, Dict[str, list]] = {
    "Rex": {
        "base":      [300.0, 150.0, 150.0, 3000.0, 400.0,  100.0, 100.0, 250.0],
        "inc_wild":  [ 60.0,  15.0,  15.0,  300.0,  40.0,    5.0,   1.0,   6.0],
        "inc_tamed": [  0.2,   0.1,   0.1,    0.1,   0.1,   0.17,   0.0,   0.0],
    },
    "Argentavis": {
        "base":      [1175.0, 420.0, 150.0, 3000.0, 350.0,  100.0, 100.0, 650.0],
        "inc_wild":  [ 235.0,  42.0,  15.0,  300.0,  35.0,    5.0,   1.0,  19.5],
        "inc_tamed": [   0.2,   0.1,   0.1,    0.1,   0.1,   0.17,   0.0,   0.0],
    },
    "Thylacoleo": {
        "base":      [700.0, 420.0, 150.0, 3000.0, 300.0,  100.0, 100.0, 400.0],
        "inc_wild":  [140.0,  42.0,  15.0,  300.0,  30.0,    5.0,   1.0,  12.0],
        "inc_tamed": [  0.2,   0.1,   0.1,    0.1,   0.1,   0.17,   0.0,   0.0],
    },
    "Giga": {
        "base":      [80000.0, 420.0, 150.0, 24000.0, 2000.0,  100.0, 100.0, 10000.0],
        "inc_wild":  [16000.0,   0.0,   0.0,   2400.0,   200.0,    4.0,   1.0,   1000.0],
        "inc_tamed": [    0.2,   0.1,   0.1,      0.1,     0.1,   0.17,   0.0,      0.0],
    },
    "Wyvern": {
        "base":      [1200.0, 250.0, 150.0, 3000.0, 350.0,  100.0, 100.0, 600.0],
        "inc_wild":  [ 240.0,  25.0,  15.0,  300.0,  35.0,    5.0,   1.0,  18.0],
        "inc_tamed": [   0.2,   0.1,   0.1,    0.1,   0.1,   0.17,   0.0,   0.0],
    },
    "Ankylosaurus": {
        "base":      [700.0, 210.0, 150.0, 3000.0, 400.0,  100.0, 100.0, 400.0],
        "inc_wild":  [140.0,  21.0,  15.0,  300.0,  40.0,    5.0,   1.0,  12.0],
        "inc_tamed": [  0.2,   0.1,   0.1,    0.1,   0.1,   0.17,   0.0,   0.0],
    },
    "Doedicurus": {
        "base":      [700.0, 200.0, 150.0, 3000.0, 400.0,  100.0, 100.0, 500.0],
        "inc_wild":  [140.0,  20.0,  15.0,  300.0,  40.0,    5.0,   1.0,  15.0],
        "inc_tamed": [  0.2,   0.1,   0.1,    0.1,   0.1,   0.17,   0.0,   0.0],
    },
    "Quetzal": {
        "base":      [1200.0, 420.0, 150.0, 4000.0, 800.0,  100.0, 100.0, 650.0],
        "inc_wild":  [ 240.0,  42.0,  15.0,  400.0,  80.0,    5.0,   1.0,  19.5],
        "inc_tamed": [   0.2,   0.1,   0.1,    0.1,   0.1,   0.17,   0.0,   0.0],
    },
    "Spino": {
        "base":      [700.0, 300.0, 150.0, 3000.0, 400.0,  100.0, 100.0, 500.0],
        "inc_wild":  [140.0,  30.0,  15.0,  300.0,  40.0,    5.0,   1.0,  15.0],
        "inc_tamed": [  0.2,   0.1,   0.1,    0.1,   0.1,   0.17,   0.0,   0.0],
    },
    "Shadowmane": {
        "base":      [975.0, 250.0, 150.0, 3000.0, 250.0,  100.0, 100.0, 550.0],
        "inc_wild":  [195.0,  25.0,  15.0,  300.0,  25.0,    5.0,   1.0,  16.5],
        "inc_tamed": [  0.2,   0.1,   0.1,    0.1,   0.1,   0.17,   0.0,   0.0],
    },
    "Stryder": {
        "base":      [730.0, 200.0, 150.0, 2000.0, 1200.0, 100.0, 100.0, 400.0],
        "inc_wild":  [146.0,  20.0,  15.0,  200.0,  120.0,   5.0,   1.0,  12.0],
        "inc_tamed": [  0.2,   0.1,   0.1,    0.1,    0.1,  0.17,   0.0,   0.0],
    },
}

# Sorted list of known species names (for autocomplete).
KNOWN_SPECIES: list = sorted(SPECIES_STATS.keys())


def get_stat_value(
    species: str,
    stat_idx: int,
    wild_points: int,
    wild_mult: float = 1.0,
) -> float:
    """
    Return the approximate in-game stat value for a creature with the given
    number of wild stat points.

    wild_mult is the server's PerLevelStatsMultiplier_DinoWild[stat_idx].
    Returns 0.0 if the species is not in the built-in table.
    """
    if species not in SPECIES_STATS:
        return 0.0
    data = SPECIES_STATS[species]
    base = data["base"][stat_idx]
    inc  = data["inc_wild"][stat_idx]
    return base + inc * wild_mult * wild_points


def estimate_wild_points(
    species: str,
    stat_idx: int,
    observed_value: float,
    wild_mult: float = 1.0,
) -> int:
    """
    Estimate wild stat points from an observed in-game value.

    This inverts get_stat_value() using the species base + per-level increment.
    The returned value is rounded to the nearest whole number and clamped at 0.
    """
    if species not in SPECIES_STATS:
        raise ValueError(f"Unknown species '{species}' for value-to-points conversion.")
    if stat_idx < 0 or stat_idx >= 8:
        raise ValueError(f"Invalid stat index {stat_idx}.")
    if wild_mult <= 0:
        raise ValueError("Wild multiplier must be greater than 0.")

    data = SPECIES_STATS[species]
    base = float(data["base"][stat_idx])
    inc = float(data["inc_wild"][stat_idx])

    # Some species/stats have no wild-level growth; only base is possible.
    if inc <= 0:
        if abs(float(observed_value) - base) <= 1e-6:
            return 0
        raise ValueError(
            f"{STAT_NAMES.get(stat_idx, f'stat {stat_idx}')} for {species} "
            "does not scale with wild points in the built-in table."
        )

    raw_points = (float(observed_value) - base) / (inc * wild_mult)
    return max(0, int(round(raw_points)))


def format_stat_table(
    stats: list[int],
    species: str = "",
    wild_mults: list[float] = None,
) -> str:
    """Return a compact text table of all 8 stats for display in Discord."""
    lines = []
    for idx, pts in enumerate(stats):
        emoji = STAT_EMOJI[idx]
        name  = STAT_SHORT[idx]
        val_str = ""
        if species:
            mult = wild_mults[idx] if (wild_mults and idx < len(wild_mults)) else 1.0
            val  = get_stat_value(species, idx, pts, wild_mult=mult)
            if val:
                val_str = f"  (~{val:,.0f})"
        lines.append(f"{emoji} **{name:<6}** {pts:>3} pts{val_str}")
    return "\n".join(lines)
