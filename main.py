"""
main.py – ARK Survival Evolved / Ascended Breeding Assistant Bot
Entry point: loads all cogs, initialises the database, and syncs slash commands.
"""

from __future__ import annotations

import asyncio
import logging
import sys

import discord
from discord.ext import commands

import config
from utils.database import init_db

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


# ── Bot Subclass ──────────────────────────────────────────────────────────────

class ArkBot(commands.Bot):
    COGS = [
        "cogs.creatures",
        "cogs.breeding",
        "cogs.mutations",
        "cogs.export",
        "cogs.server_settings",
    ]

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(
            command_prefix="!ark ",
            intents=intents,
            description="ARK Survival Evolved / Ascended Breeding Assistant",
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

        # Sync application (slash) commands globally.
        synced = await self.tree.sync()
        logger.info("Synced %d slash command(s).", len(synced))

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
    if not config.DISCORD_TOKEN:
        logger.critical(
            "DISCORD_TOKEN is not set! Copy .env.example → .env and fill in your token."
        )
        sys.exit(1)

    bot = ArkBot()
    bot.run(config.DISCORD_TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
