"""
cogs/export.py – Export breeding data to Google Sheets or a Discord webhook.

Commands
--------
/export_webhook – POST creature data as formatted Discord embeds to a webhook.
/export_sheet   – Write creature data to a Google Spreadsheet (requires setup).
/export_csv     – DM the user a CSV file of their creatures.
"""

from __future__ import annotations

import io
import csv
import json
import datetime
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

import config
from utils import database as db
from utils.database import row_to_stats, STAT_COLUMNS
from utils.ark_stats import STAT_NAMES, STAT_SHORT, STAT_EMOJI
from cogs.creatures import species_autocomplete


# ── CSV Builder ───────────────────────────────────────────────────────────────

def rows_to_csv(rows: list[dict]) -> str:
    """Serialise database rows to a CSV string."""
    if not rows:
        return ""
    output   = io.StringIO()
    headers  = [
        "id", "name", "species", "gender", "level",
        "HP", "Stamina", "Oxygen", "Food", "Weight",
        "Melee", "Speed", "Torpidity",
        "mut_maternal", "mut_paternal", "notes", "created_at",
    ]
    writer = csv.writer(output)
    writer.writerow(headers)
    for r in rows:
        stats = row_to_stats(r)
        writer.writerow([
            r["id"], r["name"], r["species"], r["gender"], r["level"],
            *stats,
            r["mut_maternal"], r["mut_paternal"],
            r.get("notes", ""), r.get("created_at", ""),
        ])
    return output.getvalue()


# ── Webhook Payload Builder ───────────────────────────────────────────────────

def build_webhook_embeds(rows: list[dict], species_filter: Optional[str]) -> list[dict]:
    """
    Build up to 10 Discord embed dicts (raw JSON) for a webhook POST.
    Discord allows max 10 embeds per message.
    """
    embeds = []
    title_done = False

    for r in rows[:10]:
        stats  = row_to_stats(r)
        total_mut = r["mut_maternal"] + r["mut_paternal"]
        g = {"Male": "♂️", "Female": "♀️"}.get(r["gender"], "❓")

        stat_text = "\n".join(
            f"{STAT_EMOJI[i]} **{STAT_SHORT[i]:<6}** {v} pts"
            for i, v in enumerate(stats)
        )

        colour = (
            0xE74C3C if total_mut >= config.MUTATION_SOFT_CAP
            else 0x2ECC71
        )

        embed = {
            "title": f"{g} {r['name']}  [{r['species']}]  #{r['id']}",
            "color": colour,
            "fields": [
                {"name": "Level",     "value": str(r["level"]),              "inline": True},
                {"name": "Gender",    "value": r["gender"],                  "inline": True},
                {"name": "Mutations", "value": f"{r['mut_maternal']}/{r['mut_paternal']} (total {total_mut})", "inline": True},
                {"name": "Wild Stats", "value": stat_text,                   "inline": False},
            ],
            "footer": {"text": f"ARK Breeding Bot  •  {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC"},
        }
        if r.get("notes"):
            embed["fields"].append({"name": "Notes", "value": r["notes"], "inline": False})
        embeds.append(embed)

    return embeds


# ── Google Sheets Helper ──────────────────────────────────────────────────────

async def write_to_google_sheet(rows: list[dict]) -> str:
    """
    Write rows to the configured Google Sheet.
    Returns a status string.  Requires gspread + google-auth to be installed
    and GOOGLE_CREDENTIALS_FILE / GOOGLE_SHEET_ID to be set in .env.
    """
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        return "Google Sheets libraries not installed (run: pip install gspread google-auth)."

    if not config.GOOGLE_CREDENTIALS_FILE or not config.GOOGLE_SHEET_ID:
        return "GOOGLE_CREDENTIALS_FILE or GOOGLE_SHEET_ID is not set in .env."

    try:
        scopes = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ]
        creds  = Credentials.from_service_account_file(
            config.GOOGLE_CREDENTIALS_FILE, scopes=scopes
        )
        client = gspread.authorize(creds)
        sheet  = client.open_by_key(config.GOOGLE_SHEET_ID).sheet1
    except FileNotFoundError:
        return f"Credentials file not found: `{config.GOOGLE_CREDENTIALS_FILE}`."
    except Exception as exc:
        return f"Failed to connect to Google Sheets: {exc}"

    headers = [
        "ID", "Name", "Species", "Gender", "Level",
        "HP", "Stamina", "Oxygen", "Food", "Weight",
        "Melee", "Speed", "Torpidity",
        "Mut Maternal", "Mut Paternal", "Notes", "Created At",
    ]

    data = [headers]
    for r in rows:
        stats = row_to_stats(r)
        data.append([
            r["id"], r["name"], r["species"], r["gender"], r["level"],
            *stats,
            r["mut_maternal"], r["mut_paternal"],
            r.get("notes", ""), r.get("created_at", ""),
        ])

    try:
        sheet.clear()
        sheet.update(data)
        return f"✅ Exported {len(rows)} row(s) to Google Sheet (ID: `{config.GOOGLE_SHEET_ID}`)."
    except Exception as exc:
        return f"Failed to write to sheet: {exc}"


# ── Cog ───────────────────────────────────────────────────────────────────────

class ExportCog(commands.Cog, name="Export"):
    """Export breeding data to external services."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /export_webhook ───────────────────────────────────────────────────────

    @app_commands.command(
        name="export_webhook",
        description="Send creature data to a Discord webhook (up to 10 at once).",
    )
    @app_commands.describe(
        species      = "Filter to a specific species",
        webhook_url  = "Override the webhook URL from .env for this export",
    )
    @app_commands.autocomplete(species=species_autocomplete)
    async def export_webhook(
        self,
        interaction: discord.Interaction,
        species: Optional[str] = None,
        webhook_url: Optional[str] = None,
    ):
        await interaction.response.defer(ephemeral=True)
        guild_id = str(interaction.guild_id)

        url = webhook_url or config.EXPORT_WEBHOOK_URL
        if not url:
            await interaction.followup.send(
                "No webhook URL configured. Set `EXPORT_WEBHOOK_URL` in `.env` "
                "or pass one via the `webhook_url` parameter.",
                ephemeral=True,
            )
            return

        rows = await db.list_creatures(guild_id=guild_id, species=species)
        if not rows:
            await interaction.followup.send("No creatures found to export.", ephemeral=True)
            return

        embeds = build_webhook_embeds(rows, species)
        payload = {
            "username": "ARK Breeding Bot",
            "embeds":   embeds,
        }

        async with aiohttp.ClientSession() as session:
            resp = await session.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            if resp.status in (200, 204):
                await interaction.followup.send(
                    f"✅ Sent {len(embeds)} creature(s) to webhook "
                    f"(showing first 10 of {len(rows)}).",
                    ephemeral=True,
                )
            else:
                body = await resp.text()
                await interaction.followup.send(
                    f"❌ Webhook returned HTTP {resp.status}: {body[:200]}",
                    ephemeral=True,
                )

    # ── /export_sheet ─────────────────────────────────────────────────────────

    @app_commands.command(
        name="export_sheet",
        description="Write all creatures to the configured Google Sheet.",
    )
    @app_commands.describe(species="Only export a specific species")
    @app_commands.autocomplete(species=species_autocomplete)
    async def export_sheet(
        self,
        interaction: discord.Interaction,
        species: Optional[str] = None,
    ):
        await interaction.response.defer(ephemeral=True)
        guild_id = str(interaction.guild_id)

        rows = await db.list_creatures(guild_id=guild_id, species=species)
        if not rows:
            await interaction.followup.send("No creatures found to export.", ephemeral=True)
            return

        status = await write_to_google_sheet(rows)
        await interaction.followup.send(status, ephemeral=True)

    # ── /export_csv ───────────────────────────────────────────────────────────

    @app_commands.command(
        name="export_csv",
        description="Download a CSV file of your creatures.",
    )
    @app_commands.describe(
        species = "Only export a specific species",
        mine    = "Export only creatures you added",
    )
    @app_commands.autocomplete(species=species_autocomplete)
    async def export_csv(
        self,
        interaction: discord.Interaction,
        species: Optional[str] = None,
        mine: bool = False,
    ):
        await interaction.response.defer(ephemeral=True)
        guild_id = str(interaction.guild_id)

        rows = await db.list_creatures(
            guild_id = guild_id,
            species  = species,
            user_id  = str(interaction.user.id) if mine else None,
        )
        if not rows:
            await interaction.followup.send("No creatures found to export.", ephemeral=True)
            return

        csv_content = rows_to_csv(rows)
        timestamp   = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename    = f"ark_roster_{timestamp}.csv"

        file = discord.File(
            fp=io.BytesIO(csv_content.encode("utf-8")),
            filename=filename,
        )
        await interaction.followup.send(
            f"📂 Exported **{len(rows)}** creature(s) to CSV.",
            file=file,
            ephemeral=True,
        )


# ── Setup ─────────────────────────────────────────────────────────────────────

async def setup(bot: commands.Bot):
    await bot.add_cog(ExportCog(bot))
