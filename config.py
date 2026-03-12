"""
config.py – Centralised settings loaded from environment variables.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Bot ───────────────────────────────────────────────────────────────────────
DISCORD_TOKEN: str = os.getenv("DISCORD_TOKEN", "")

# ── Database ──────────────────────────────────────────────────────────────────
DATABASE_PATH: str = os.getenv("DATABASE_PATH", "ark_breeding.db")

# ── Google Sheets ─────────────────────────────────────────────────────────────
GOOGLE_CREDENTIALS_FILE: str = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
GOOGLE_SHEET_ID: str = os.getenv("GOOGLE_SHEET_ID", "")

# ── Webhook ───────────────────────────────────────────────────────────────────
EXPORT_WEBHOOK_URL: str = os.getenv("EXPORT_WEBHOOK_URL", "")

# ── ARK Breeding Constants ────────────────────────────────────────────────────
# Probability (0-1) that a single parent contributes a mutation to the baby.
MUTATION_CHANCE_PER_PARENT: float = 0.0731

# Maximum mutation counter value before the game heavily suppresses new
# mutations coming from that parent's lineage.
MUTATION_SOFT_CAP: int = 20

# Embed colour used throughout the bot.
EMBED_COLOR: int = 0x2ECC71   # ARK-green
EMBED_COLOR_WARN: int = 0xE67E22
EMBED_COLOR_ERROR: int = 0xE74C3C
EMBED_COLOR_INFO: int = 0x3498DB
