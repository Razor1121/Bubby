"""
utils/server_settings.py – Per-guild ARK server multiplier settings.

Stores and retrieves custom server rates (wild stat multipliers, breeding
timer multipliers, etc.) so that displayed stat values reflect the actual
in-game numbers on the user's server.

INI keys parsed from Game.ini
──────────────────────────────
  PerLevelStatsMultiplier_DinoWild[0-7]          – Per-stat wild level mult
  PerLevelStatsMultiplier_DinoTamed_Add[0-7]     – Tamed additive bonus mult
  PerLevelStatsMultiplier_DinoTamed_Affinity[0-7]– Imprint bonus mult
  MatingIntervalMultiplier
  EggHatchSpeedMultiplier
  BabyMatureSpeedMultiplier
  BabyCuddleIntervalMultiplier
  BabyFoodConsumptionSpeedMultiplier
  BabyImprintingStatScaleMultiplier
  TamingSpeedMultiplier
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from typing import Optional

from utils import database as db

# ── Vanilla Defaults ──────────────────────────────────────────────────────────

# Indices 0-7 match STAT_NAMES in ark_stats.py
DEFAULT_WILD_MULTS: list[float] = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
DEFAULT_TAMED_ADD:  list[float] = [0.14, 0.14, 0.14, 0.14, 0.14, 0.14, 0.14, 0.14]
DEFAULT_TAMED_AFF:  list[float] = [0.44, 0.44, 0.44, 0.44, 0.44, 0.44, 0.44, 0.44]

# ── Approximate vanilla base times (hours) ────────────────────────────────────
# These are divided by the respective speed multiplier to estimate actual times.
SPECIES_BREEDING_TIMES: dict[str, dict] = {
    "Rex":          {"hatch_h": 5.0,  "mature_h": 83.6},
    "Argentavis":   {"hatch_h": 2.6,  "mature_h": 58.3},
    "Thylacoleo":   {"hatch_h": 3.5,  "mature_h": 83.6},
    "Giga":         {"hatch_h": 5.0,  "mature_h": 171.9},
    "Wyvern":       {"hatch_h": 5.0,  "mature_h": 83.6},
    "Ankylosaurus": {"hatch_h": 1.75, "mature_h": 42.0},
    "Doedicurus":   {"hatch_h": 1.75, "mature_h": 42.0},
    "Quetzal":      {"hatch_h": 5.0,  "mature_h": 83.6},
    "Spino":        {"hatch_h": 5.0,  "mature_h": 83.6},
    "Shadowmane":   {"hatch_h": 3.5,  "mature_h": 58.3},
    "Stryder":      {"hatch_h": None, "mature_h": None},  # Spawned, not hatched
}


def _fmt_hours(h: Optional[float]) -> str:
    """Convert hours to a readable d/h/m string."""
    if h is None:
        return "N/A"
    if h < 1:
        return f"{h * 60:.0f} min"
    if h < 24:
        return f"{h:.1f} h"
    days = int(h // 24)
    rem  = h % 24
    return f"{days}d {rem:.1f}h"


# ── Settings Dataclass ────────────────────────────────────────────────────────

@dataclass
class ServerSettings:
    guild_id: str = ""

    # Per-stat wild level multipliers (affects displayed stat values)
    wild_mults: list[float] = field(
        default_factory=lambda: list(DEFAULT_WILD_MULTS)
    )

    # Per-stat tamed additive multipliers (taming effectiveness bonus)
    tamed_add: list[float] = field(
        default_factory=lambda: list(DEFAULT_TAMED_ADD)
    )

    # Per-stat tamed affinity multipliers (imprint bonus)
    tamed_aff: list[float] = field(
        default_factory=lambda: list(DEFAULT_TAMED_AFF)
    )

    # Breeding timer multipliers
    mating_interval_mult:           float = 1.0
    egg_hatch_speed_mult:           float = 1.0
    baby_mature_speed_mult:         float = 1.0
    baby_cuddle_interval_mult:      float = 1.0
    baby_food_consumption_speed:    float = 1.0
    baby_imprinting_stat_scale:     float = 1.0

    # Other common server rates
    taming_speed_mult:              float = 1.0

    @property
    def is_default(self) -> bool:
        return (
            self.wild_mults == DEFAULT_WILD_MULTS
            and self.tamed_add == DEFAULT_TAMED_ADD
            and self.tamed_aff == DEFAULT_TAMED_AFF
            and self.mating_interval_mult == 1.0
            and self.egg_hatch_speed_mult == 1.0
            and self.baby_mature_speed_mult == 1.0
            and self.baby_cuddle_interval_mult == 1.0
            and self.taming_speed_mult == 1.0
        )

    def to_json(self) -> str:
        d = asdict(self)
        d.pop("guild_id", None)
        return json.dumps(d)

    @classmethod
    def from_json(cls, guild_id: str, json_str: str) -> "ServerSettings":
        s = cls(guild_id=guild_id)
        if not json_str or json_str == "{}":
            return s
        try:
            data = json.loads(json_str)
            for key, val in data.items():
                if hasattr(s, key):
                    setattr(s, key, val)
        except (json.JSONDecodeError, TypeError):
            pass
        return s

    def hatch_time(self, species: str) -> str:
        base = SPECIES_BREEDING_TIMES.get(species, {}).get("hatch_h")
        if base is None:
            return "Unknown"
        mult = self.egg_hatch_speed_mult
        return _fmt_hours(base / mult if mult > 0 else base)

    def mature_time(self, species: str) -> str:
        base = SPECIES_BREEDING_TIMES.get(species, {}).get("mature_h")
        if base is None:
            return "Unknown"
        mult = self.baby_mature_speed_mult
        return _fmt_hours(base / mult if mult > 0 else base)

    def mating_interval(self) -> str:
        base_h = 18.0  # vanilla mating interval ~18 h
        mult   = self.mating_interval_mult
        return _fmt_hours(base_h * mult if mult > 0 else base_h)

    def cuddle_interval(self) -> str:
        base_h = 8.0   # vanilla cuddle ~8 h
        mult   = self.baby_cuddle_interval_mult
        return _fmt_hours(base_h * mult if mult > 0 else base_h)


# ── DB Helpers ────────────────────────────────────────────────────────────────

async def load_guild_settings(guild_id: str) -> ServerSettings:
    """
    Load server settings for a guild from the database.
    Returns vanilla defaults if no custom settings have been saved.
    """
    raw = await db.get_raw_server_settings(guild_id)
    return ServerSettings.from_json(guild_id, raw)


async def save_guild_settings(
    settings: ServerSettings,
    updated_by: str = "",
) -> None:
    await db.save_server_settings(
        settings.guild_id, settings.to_json(), updated_by
    )


# ── INI Parser ────────────────────────────────────────────────────────────────

# Maps scalar INI key names → ServerSettings field names
_SCALAR_MAP: dict[str, str] = {
    "MatingIntervalMultiplier":           "mating_interval_mult",
    "EggHatchSpeedMultiplier":            "egg_hatch_speed_mult",
    "BabyMatureSpeedMultiplier":          "baby_mature_speed_mult",
    "BabyCuddleIntervalMultiplier":       "baby_cuddle_interval_mult",
    "BabyFoodConsumptionSpeedMultiplier": "baby_food_consumption_speed",
    "BabyImprintingStatScaleMultiplier":  "baby_imprinting_stat_scale",
    "TamingSpeedMultiplier":              "taming_speed_mult",
}

# Compiled regex patterns
_RE_WILD  = re.compile(
    r"PerLevelStatsMultiplier_DinoWild\[(\d+)\]\s*=\s*([0-9]*\.?[0-9]+)",
    re.IGNORECASE,
)
_RE_T_ADD = re.compile(
    r"PerLevelStatsMultiplier_DinoTamed_Add\[(\d+)\]\s*=\s*([0-9]*\.?[0-9]+)",
    re.IGNORECASE,
)
_RE_T_AFF = re.compile(
    r"PerLevelStatsMultiplier_DinoTamed_Affinity\[(\d+)\]\s*=\s*([0-9]*\.?[0-9]+)",
    re.IGNORECASE,
)
_RE_SCALAR = {
    key: re.compile(rf"(?<![A-Za-z]){re.escape(key)}\s*=\s*([0-9]*\.?[0-9]+)", re.IGNORECASE)
    for key in _SCALAR_MAP
}


def parse_ini_text(
    text: str,
    base: Optional[ServerSettings] = None,
) -> tuple[ServerSettings, list[str]]:
    """
    Parse pasted Game.ini lines and return (updated_settings, warnings).

    Parameters
    ----------
    text:   Raw text pasted by the user (can include the full .ini or just
            the relevant lines).
    base:   Existing settings to start from (optional).  If None, vanilla
            defaults are used.  Only keys found in the text are overwritten,
            so multiple partial pastes can be merged.
    """
    settings = ServerSettings() if base is None else ServerSettings(
        guild_id             = base.guild_id,
        wild_mults           = list(base.wild_mults),
        tamed_add            = list(base.tamed_add),
        tamed_aff            = list(base.tamed_aff),
        mating_interval_mult = base.mating_interval_mult,
        egg_hatch_speed_mult = base.egg_hatch_speed_mult,
        baby_mature_speed_mult      = base.baby_mature_speed_mult,
        baby_cuddle_interval_mult   = base.baby_cuddle_interval_mult,
        baby_food_consumption_speed = base.baby_food_consumption_speed,
        baby_imprinting_stat_scale  = base.baby_imprinting_stat_scale,
        taming_speed_mult           = base.taming_speed_mult,
    )

    warnings: list[str] = []
    found: list[str]    = []

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", ";", "[")):
            continue

        # Wild per-level multipliers
        m = _RE_WILD.search(stripped)
        if m:
            idx, val = int(m.group(1)), float(m.group(2))
            if 0 <= idx <= 7:
                settings.wild_mults[idx] = val
                found.append(f"WildMult[{idx}]={val}")
            else:
                warnings.append(f"Stat index {idx} is out of range (0-7), skipped.")
            continue

        # Tamed additive multipliers
        m = _RE_T_ADD.search(stripped)
        if m:
            idx, val = int(m.group(1)), float(m.group(2))
            if 0 <= idx <= 7:
                settings.tamed_add[idx] = val
                found.append(f"TamedAdd[{idx}]={val}")
            else:
                warnings.append(f"Tamed_Add stat index {idx} out of range, skipped.")
            continue

        # Tamed affinity multipliers
        m = _RE_T_AFF.search(stripped)
        if m:
            idx, val = int(m.group(1)), float(m.group(2))
            if 0 <= idx <= 7:
                settings.tamed_aff[idx] = val
                found.append(f"TamedAff[{idx}]={val}")
            else:
                warnings.append(f"Tamed_Affinity stat index {idx} out of range, skipped.")
            continue

        # Scalar keys
        for ini_key, field_name in _SCALAR_MAP.items():
            m = _RE_SCALAR[ini_key].search(stripped)
            if m:
                val = float(m.group(1))
                setattr(settings, field_name, val)
                found.append(f"{ini_key}={val}")
                break

    if not found:
        warnings.append(
            "No recognised ARK multiplier keys were found in the pasted text. "
            "Make sure to paste lines from Game.ini (not GameUserSettings.ini)."
        )

    return settings, warnings, found
