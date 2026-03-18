"""
bot.py – ARK Survival Evolved / Ascended Breeding Assistant Bot
Primary entry point: loads all cogs, initialises the database, and syncs slash commands.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# ── Dependency bootstrap ──────────────────────────────────────────────────────
# Install any missing packages before the rest of the imports run.
# This lets the bot self-heal in container environments that wipe site-packages
# between restarts, without needing a manual `pip install -r requirements.txt`.

def _install_requirements() -> None:
    req_file = Path(__file__).resolve().parent / "requirements.txt"
    if not req_file.is_file():
        print("[startup] requirements.txt not found — skipping auto-install.")
        return

    print(f"[startup] Installing dependencies from {req_file} ...")
    for extra_flags in ([], ["--user"]):
        cmd = [sys.executable, "-m", "pip", "install", "-r", str(req_file)] + extra_flags
        try:
            subprocess.check_call(cmd)
            print("[startup] Dependencies installed successfully.")
            return
        except subprocess.CalledProcessError as exc:
            print(f"[startup] pip install {' '.join(extra_flags or ['(default)'])} failed (exit {exc.returncode}), retrying...")

    print("[startup] All pip install attempts failed. Bot may crash on missing imports.")

_install_requirements()

# ── Standard imports (after packages are guaranteed installed) ────────────────

import asyncio
import logging
from typing import Iterable

import discord
from discord.ext import commands
import config


def _is_project_root(path: Path) -> bool:
    return (path / "utils" / "database.py").is_file() and (path / "cogs").is_dir()


def _candidate_roots() -> Iterable[Path]:
    here = Path(__file__).resolve().parent
    cwd = Path.cwd().resolve()

    bases = [here, cwd, *here.parents, *cwd.parents]
    seen = set()
    for base in bases:
        key = str(base)
        if key in seen:
            continue
        seen.add(key)
        yield base

    # Also inspect first-level subfolders for hosts that extract projects into
    # a nested directory, e.g. /home/container/Ark Bot.
    for base in (here, cwd):
        try:
            for child in base.iterdir():
                if child.is_dir():
                    key = str(child)
                    if key not in seen:
                        seen.add(key)
                        yield child
        except Exception:
            continue


def _prepare_import_path() -> Path:
    """Ensure this project's root folder is importable in container hosts."""
    for candidate in _candidate_roots():
        if _is_project_root(candidate):
            if str(candidate) not in sys.path:
                sys.path.insert(0, str(candidate))
            return candidate

    # Fall back to script directory if discovery fails.
    fallback = Path(__file__).resolve().parent
    if str(fallback) not in sys.path:
        sys.path.insert(0, str(fallback))
    return fallback


PROJECT_ROOT = _prepare_import_path()

try:
    from utils.database import init_db
except ModuleNotFoundError as exc:
    print("[startup] Failed to import utils.database")
    print(f"[startup] __file__ directory: {PROJECT_ROOT}")
    print(f"[startup] current working directory: {Path.cwd().resolve()}")
    print(f"[startup] sys.path[0:5]: {sys.path[:5]}")
    try:
        top_level_dirs = sorted(
            [p.name for p in Path.cwd().iterdir() if p.is_dir()]
        )
        print(f"[startup] top-level dirs in cwd: {top_level_dirs}")
    except Exception:
        pass
    print(
        "[startup] Ensure your deploy includes the 'utils' and 'cogs' folders next to bot.py."
    )
    raise exc

# Put your Discord bot token here.
BOT_TOKEN = "PASTE_YOUR_DISCORD_BOT_TOKEN_HERE"

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("ark_bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("ark_bot")


def _parse_guild_ids(raw: str) -> list[int]:
    """Parse comma-separated guild IDs from env/config text."""
    if not raw:
        return []

    guild_ids: list[int] = []
    for part in raw.replace(";", ",").split(","):
        token = part.strip()
        if not token:
            continue
        try:
            guild_ids.append(int(token))
        except ValueError:
            logger.warning("Ignoring invalid guild id in DISCORD_GUILD_IDS: %r", token)

    # Keep order, remove duplicates.
    seen: set[int] = set()
    unique: list[int] = []
    for gid in guild_ids:
        if gid in seen:
            continue
        seen.add(gid)
        unique.append(gid)
    return unique


# ── Bot Subclass ──────────────────────────────────────────────────────────────

class ArkBot(commands.Bot):
    COGS = [
        "cogs.creatures",
        "cogs.breeding",
        "cogs.mutations",
        "cogs.export",
        "cogs.server_settings",
        "cogs.help",
    ]

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(
            command_prefix=commands.when_mentioned_or("'", ">"),
            intents=intents,
            description="ARK Survival Evolved / Ascended Breeding Assistant",
            help_command=None,
        )

    async def setup_hook(self) -> None:
        # Initialise the SQLite database (creates tables if missing).
        await init_db()
        logger.info("Database initialised.")

        # Load all cogs.
        for cog in self.COGS:
            try:
                await self.load_extension(cog)
                logger.info("Loaded cog: %s", cog)
            except Exception as exc:
                logger.error("Failed to load cog %s: %s", cog, exc)

        # Sync global commands and optionally fast-sync to test guild(s).
        try:
            synced = await self.tree.sync()
            logger.info("Synced %d global slash command(s).", len(synced))
        except Exception as exc:
            logger.error("Global slash-command sync failed: %s", exc)

        guild_ids = _parse_guild_ids(getattr(config, "DISCORD_GUILD_IDS", ""))
        for guild_id in guild_ids:
            try:
                guild = discord.Object(id=guild_id)
                self.tree.copy_global_to(guild=guild)
                synced_guild = await self.tree.sync(guild=guild)
                logger.info(
                    "Synced %d slash command(s) to guild %d.",
                    len(synced_guild),
                    guild_id,
                )
            except Exception as exc:
                logger.error("Guild sync failed for %d: %s", guild_id, exc)

    async def on_ready(self) -> None:
        logger.info("Logged in as %s (ID: %s)", self.user, self.user.id)
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="ARK Dino Breeding 🦕",
            )
        )

    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: discord.app_commands.AppCommandError,
    ) -> None:
        """Global slash-command error handler."""
        msg = f"An error occurred: {error}"
        logger.error("Command error in '%s': %s", interaction.command, error)
        try:
            if interaction.response.is_done():
                await interaction.followup.send(f"❌ {msg}", ephemeral=True)
            else:
                await interaction.response.send_message(f"❌ {msg}", ephemeral=True)
        except Exception:
            pass  # Nothing we can do if the interaction has expired.


# ── Entry Point ───────────────────────────────────────────────────────────────

def main() -> None:
    if not BOT_TOKEN or BOT_TOKEN == "PASTE_YOUR_DISCORD_BOT_TOKEN_HERE":
        logger.critical(
            "BOT_TOKEN is not set in bot.py. Add your token to BOT_TOKEN and try again."
        )
        sys.exit(1)

    bot = ArkBot()
    bot.run(BOT_TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
