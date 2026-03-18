"""
config.py – Centralised settings loaded from environment variables.
A .env file in the project root is loaded automatically on startup.
"""

import os
from pathlib import Path


def _load_dotenv() -> None:
	"""Parse a .env file and populate os.environ for any keys not already set."""
	dotenv_path = Path(__file__).resolve().parent / ".env"
	if not dotenv_path.is_file():
		return
	try:
		with dotenv_path.open(encoding="utf-8") as fh:
			for raw_line in fh:
				line = raw_line.strip()
				if not line or line.startswith("#") or "=" not in line:
					continue
				key, _, val = line.partition("=")
				key = key.strip()
				val = val.strip().strip('"').strip("'")
				if key and key not in os.environ:
					os.environ[key] = val
	except Exception:
		pass


_load_dotenv()


def _get_env(name: str, default: str) -> str:
	"""Resolve env var from process env (includes .env values), then default."""
	value = os.getenv(name)
	if value is not None and str(value).strip():
		return str(value)
	return default

# ── Database ──────────────────────────────────────────────────────────────────
DATABASE_PATH: str = _get_env("DATABASE_PATH", "ark_breeding.db")

# ── Google Sheets ─────────────────────────────────────────────────────────────
GOOGLE_CREDENTIALS_FILE: str = _get_env("GOOGLE_CREDENTIALS_FILE", "credentials.json")
GOOGLE_SHARED_SPREADSHEET_ID: str = _get_env("GOOGLE_SHARED_SPREADSHEET_ID", "")

# ── Webhook ───────────────────────────────────────────────────────────────────
EXPORT_WEBHOOK_URL: str = _get_env("EXPORT_WEBHOOK_URL", "")

# ── Discord Sync ──────────────────────────────────────────────────────────────
# Optional comma-separated guild IDs for immediate slash-command sync, e.g.:
# DISCORD_GUILD_IDS=123456789012345678,234567890123456789
DISCORD_GUILD_IDS: str = _get_env("DISCORD_GUILD_IDS", "")

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
