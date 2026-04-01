"""
cogs/broadcast.py – Bot-wide announcement & terminal broadcast system.

Features
--------
- /announce <message>            (bot owner only) – post to every server
- /set_broadcast_channel         (manage_guild)   – designate a per-server channel
- Terminal stdin listener        – type in the console to broadcast to all servers

Channel resolution order per guild
-----------------------------------
1. Stored broadcast channel (set via /set_broadcast_channel)
2. Guild's system channel
3. First text channel the bot can write to
"""
from __future__ import annotations

import asyncio
import logging
import sys
import threading
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils.database import get_broadcast_channel, set_broadcast_channel

logger = logging.getLogger("ark_bot.broadcast")


# ── Owner check ───────────────────────────────────────────────────────────────

async def _is_owner(interaction: discord.Interaction) -> bool:
    return await interaction.client.is_owner(interaction.user)


# ── Cog ───────────────────────────────────────────────────────────────────────

class BroadcastCog(commands.Cog, name="Broadcast"):
    """Send announcements to all servers the bot is in."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._start_stdin_thread()

    # ── Terminal stdin ────────────────────────────────────────────────────────

    def _start_stdin_thread(self) -> None:
        """Launch a daemon thread to watch stdin for broadcast messages."""
        if not sys.stdin or not sys.stdin.isatty():
            logger.info("[Broadcast] stdin is not a TTY – terminal broadcast disabled.")
            return
        thread = threading.Thread(
            target=self._stdin_loop,
            daemon=True,
            name="stdin-broadcast",
        )
        thread.start()

    def _stdin_loop(self) -> None:
        """
        Blocking stdin reader that runs in a background thread.

        Lines prefixed with  !  are ignored (handy for local notes / debug).
        Any other non-empty line is broadcast to all guilds.
        """
        loop = self.bot.loop
        print(
            "\n[Broadcast] Terminal broadcast ready.\n"
            "[Broadcast]  • Type a message and press Enter to send to ALL servers.\n"
            "[Broadcast]  • Prefix a line with  !  to skip it (e.g. !test).\n"
        )
        while True:
            try:
                line = sys.stdin.readline()
            except Exception:
                break
            if not line:           # EOF – stdin closed
                break
            text = line.rstrip("\n")
            if not text.strip() or text.lstrip().startswith("!"):
                continue
            asyncio.run_coroutine_threadsafe(
                self._do_broadcast(text.strip(), source="terminal"),
                loop,
            )

    # ── Broadcast logic ───────────────────────────────────────────────────────

    async def _find_channel(
        self, guild: discord.Guild
    ) -> Optional[discord.TextChannel]:
        """Return the best channel to post announcements in for *guild*."""
        stored_id = await get_broadcast_channel(str(guild.id))
        if stored_id:
            ch = guild.get_channel(int(stored_id))
            if (
                isinstance(ch, discord.TextChannel)
                and ch.permissions_for(guild.me).send_messages
            ):
                return ch

        # Fall back to the guild's system / community updates channel.
        if (
            guild.system_channel
            and guild.system_channel.permissions_for(guild.me).send_messages
        ):
            return guild.system_channel

        # Last resort: first text channel the bot can write to.
        for ch in guild.text_channels:
            if ch.permissions_for(guild.me).send_messages:
                return ch

        return None

    async def _do_broadcast(
        self,
        message: str,
        *,
        source: str = "unknown",
        sender: Optional[discord.User | discord.Member] = None,
    ) -> tuple[int, int]:
        """
        Send *message* as an embed to every guild the bot is in.

        Returns ``(success_count, fail_count)``.
        """
        embed = discord.Embed(
            title="📢 Announcement",
            description=message,
            color=config.EMBED_COLOR_INFO,
        )
        if sender:
            embed.set_footer(
                text=f"Sent by {sender.display_name}",
                icon_url=sender.display_avatar.url,
            )
        else:
            embed.set_footer(text="Sent by the bot owner via terminal")

        success = fail = 0
        for guild in self.bot.guilds:
            ch = await self._find_channel(guild)
            if ch is None:
                logger.warning(
                    "[Broadcast] No suitable channel in %s (%d) – skipped.",
                    guild.name, guild.id,
                )
                fail += 1
                continue
            try:
                await ch.send(embed=embed)
                success += 1
            except discord.HTTPException as exc:
                logger.warning(
                    "[Broadcast] Failed to send to %s (%d): %s",
                    guild.name, guild.id, exc,
                )
                fail += 1

        logger.info(
            "[Broadcast] source=%s  success=%d  fail=%d  message=%r",
            source, success, fail, message[:100],
        )
        return success, fail

    # ── Slash commands ────────────────────────────────────────────────────────

    @app_commands.command(
        name="announce",
        description="(Owner only) Broadcast a message to every server the bot is in.",
    )
    @app_commands.check(_is_owner)
    @app_commands.describe(message="The announcement text to send to every server.")
    async def announce(
        self, interaction: discord.Interaction, message: str
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        success, fail = await self._do_broadcast(
            message, source="slash", sender=interaction.user
        )
        total = success + fail
        await interaction.followup.send(
            f"✅ Broadcast sent to **{success}/{total}** server(s)."
            + (f" ({fail} failed — no writable channel found)" if fail else ""),
            ephemeral=True,
        )

    @announce.error
    async def _announce_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.CheckFailure):
            msg = "❌ Only the bot owner can use this command."
        else:
            msg = f"❌ {error}"
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except Exception:
            pass

    @app_commands.command(
        name="set_broadcast_channel",
        description="Set (or clear) the channel where bot-wide announcements appear in this server.",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(
        channel="Text channel for announcements. Leave blank to clear the setting."
    )
    async def set_broadcast_channel(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None,
    ) -> None:
        guild_id = str(interaction.guild_id)
        if channel is None:
            await set_broadcast_channel(guild_id, "", str(interaction.user.id))
            await interaction.response.send_message(
                "✅ Broadcast channel cleared. "
                "Will fall back to the system channel (or first writable channel).",
                ephemeral=True,
            )
        else:
            await set_broadcast_channel(
                guild_id, str(channel.id), str(interaction.user.id)
            )
            await interaction.response.send_message(
                f"✅ Broadcast channel set to {channel.mention}.",
                ephemeral=True,
            )

    @set_broadcast_channel.error
    async def _set_channel_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            msg = "❌ You need the **Manage Server** permission to change this setting."
        else:
            msg = f"❌ {error}"
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except Exception:
            pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BroadcastCog(bot))
