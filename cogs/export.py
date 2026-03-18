"""
cogs/export.py – Export breeding data to Google Sheets or a Discord webhook.

Commands
--------
/setup          – Create and store a default guild webhook for exports.
/export_webhook – POST creature data as formatted Discord embeds to a webhook.
/export_sheet   – Write creature data to your dedicated Google Spreadsheet.
/export_csv     – DM the user a CSV file of their creatures.
"""

from __future__ import annotations

import io
import csv
import datetime
import os
import warnings
from pathlib import Path
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

import config
from utils import database as db
from utils.database import row_to_stats
from utils.ark_stats import STAT_NAMES, STAT_SHORT, STAT_EMOJI
from utils.prefix_adapter import as_interaction
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

def build_sheet_rows(rows: list[dict]) -> list[list[str | int]]:
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
    return data


def resolve_credentials_path(config_value: str) -> tuple[Optional[str], list[str]]:
    """Resolve credentials path from common deployment locations."""
    if not config_value:
        return None, []

    # Defensive import: keeps this helper working even if an old deploy misses the module-level import.
    from pathlib import Path

    raw = Path(config_value)
    candidates: list[Path] = []

    if raw.is_absolute():
        candidates.append(raw)
    else:
        cwd = Path.cwd()
        project_root = Path(__file__).resolve().parents[1]
        candidates.extend([
            cwd / raw,
            project_root / raw,
            cwd / "Ark Bot" / raw,
            project_root / "Ark Bot" / raw,
        ])

    seen: set[str] = set()
    checked: list[str] = []
    for candidate in candidates:
        normalized = str(candidate.resolve()) if not candidate.is_absolute() else str(candidate)
        if normalized in seen:
            continue
        seen.add(normalized)
        checked.append(normalized)
        if candidate.is_file():
            return str(candidate), checked

    return None, checked


def resolve_shared_spreadsheet_id() -> str:
    """Resolve the shared spreadsheet ID using fresh runtime config lookups."""
    value = (getattr(config, "GOOGLE_SHARED_SPREADSHEET_ID", "") or "").strip()
    if value:
        return value

    # Prefer config helper when available so Windows persisted env can be read.
    get_env = getattr(config, "_get_env", None)
    if callable(get_env):
        try:
            value = (get_env("GOOGLE_SHARED_SPREADSHEET_ID", "") or "").strip()
            if value:
                return value
        except Exception:
            pass

    return (os.getenv("GOOGLE_SHARED_SPREADSHEET_ID", "") or "").strip()


async def write_to_google_sheet(
    rows: list[dict],
    guild_id: str,
    user: discord.abc.User,
) -> str:
    """
    Write rows to a dedicated Google Sheet for the given user.
    Reuses an existing stored sheet when possible, otherwise creates one.
    """
    try:
        # Narrow suppression: silence only google-auth's Python 3.9 EOL warning.
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message=r".*Python version 3\.9 past its end of life.*",
                category=FutureWarning,
                module=r"google\.(auth|oauth2)(\..*)?",
            )
            import gspread
            from google.oauth2.service_account import Credentials
            from gspread.exceptions import WorksheetNotFound
    except ImportError:
        return "Google Sheets libraries not installed (run: pip install gspread google-auth)."

    if not config.GOOGLE_CREDENTIALS_FILE:
        return "GOOGLE_CREDENTIALS_FILE is not configured."

    creds_path, checked_paths = resolve_credentials_path(config.GOOGLE_CREDENTIALS_FILE)
    if not creds_path:
        checked = "\n - ".join(checked_paths) if checked_paths else "(none)"
        return (
            "Credentials file not found. Paste your Google service-account JSON into `credentials.json`, "
            "or set GOOGLE_CREDENTIALS_FILE to the full path, "
            "or place the file in one of these locations:\n"
            f" - {checked}"
        )

    try:
        scopes = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ]
        creds  = Credentials.from_service_account_file(
            creds_path, scopes=scopes
        )
        client = gspread.authorize(creds)
    except Exception as exc:
        return f"Failed to connect to Google Sheets: {exc}"

    sheet_info = await db.get_user_sheet(guild_id, str(user.id))
    spreadsheet = None
    created_new_sheet = False
    using_shared_sheet = False
    shared_spreadsheet_id = resolve_shared_spreadsheet_id()

    if sheet_info and sheet_info.get("spreadsheet_id"):
        try:
            spreadsheet = client.open_by_key(sheet_info["spreadsheet_id"])
            if shared_spreadsheet_id and sheet_info["spreadsheet_id"] == shared_spreadsheet_id:
                using_shared_sheet = True
        except Exception:
            spreadsheet = None

    if spreadsheet is None:
        if shared_spreadsheet_id:
            try:
                spreadsheet = client.open_by_key(shared_spreadsheet_id)
                using_shared_sheet = True
            except Exception as exc:
                return f"Failed to open shared Google Sheet: {exc}"

    if spreadsheet is None:
        safe_name = "".join(
            ch for ch in user.display_name if ch.isalnum() or ch in " -_"
        ).strip()
        title = f"ARK Breeding - {safe_name or user.name} ({user.id})"
        try:
            spreadsheet = client.create(title)
            try:
                spreadsheet.sheet1.update_title("Roster")
            except Exception:
                pass
            await db.save_user_sheet(
                guild_id,
                str(user.id),
                spreadsheet.id,
                spreadsheet.url,
            )
            created_new_sheet = True
        except Exception as exc:
            exc_text = str(exc)
            exc_lower = exc_text.lower()
            if "quota" in exc_lower and "storage" in exc_lower:
                return (
                    "Google Drive quota exceeded for the service account while creating a new spreadsheet. "
                    "Set GOOGLE_SHARED_SPREADSHEET_ID to an existing sheet (shared with the service account as Editor) "
                    "so exports can use a per-user worksheet tab without creating new Drive files."
                )
            return f"Failed to create Google Sheet: {exc}"

    data = build_sheet_rows(rows)

    try:
        if using_shared_sheet:
            worksheet_title = f"user-{user.id}"
            try:
                worksheet = spreadsheet.worksheet(worksheet_title)
            except WorksheetNotFound:
                worksheet = spreadsheet.add_worksheet(
                    title=worksheet_title,
                    rows=max(100, len(data) + 20),
                    cols=max(17, len(data[0]) if data else 17),
                )
        else:
            worksheet = spreadsheet.sheet1

        worksheet.clear()
        worksheet.update(data)
        if sheet_info and not sheet_info.get("spreadsheet_url"):
            await db.save_user_sheet(
                guild_id,
                str(user.id),
                spreadsheet.id,
                spreadsheet.url,
            )
        elif created_new_sheet:
            await db.save_user_sheet(
                guild_id,
                str(user.id),
                spreadsheet.id,
                spreadsheet.url,
            )

        if using_shared_sheet:
            return (
                f"✅ Exported {len(rows)} row(s) to shared sheet tab '{worksheet.title}': "
                f"{spreadsheet.url}"
            )
        if created_new_sheet:
            return f"✅ Created your sheet and exported {len(rows)} row(s): {spreadsheet.url}"
        return f"✅ Exported {len(rows)} row(s) to your sheet: {spreadsheet.url}"
    except Exception as exc:
        return f"Failed to write to sheet: {exc}"


# ── Cog ───────────────────────────────────────────────────────────────────────

class ExportCog(commands.Cog, name="Export"):
    """Export breeding data to external services."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="setup",
        description="Create and save this channel as the default export webhook target.",
    )
    @app_commands.default_permissions(manage_webhooks=True)
    async def setup_slash(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used in a server channel.",
                ephemeral=True,
            )
            return

        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                "Run this in a text channel where the bot can create webhooks.",
                ephemeral=True,
            )
            return

        me = interaction.guild.me or interaction.guild.get_member(self.bot.user.id)
        if me is None or not interaction.channel.permissions_for(me).manage_webhooks:
            await interaction.response.send_message(
                "I need the Manage Webhooks permission in this channel.",
                ephemeral=True,
            )
            return

        webhook = await interaction.channel.create_webhook(name="Bot Logs")
        await db.save_export_webhook(
            str(interaction.guild.id),
            str(interaction.channel.id),
            webhook.url,
            str(interaction.user.id),
        )
        await interaction.response.send_message(
            f"Webhook created and saved for exports: {webhook.url}",
            ephemeral=True,
        )

    # ── Prefix: 'setup ────────────────────────────────────────────────────────

    @commands.command(name="setup")
    @commands.has_permissions(manage_webhooks=True)
    async def setup_command(self, ctx: commands.Context) -> None:
        adapter = as_interaction(ctx)
        await ExportCog.setup_slash.callback(self, adapter)

    @setup_command.error
    async def setup_command_error(
        self,
        ctx: commands.Context,
        error: commands.CommandError,
    ) -> None:
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("You need the Manage Webhooks permission to run this command.")
            return
        raise error

    @commands.command(name="export_sheet")
    async def export_sheet_prefix(self, ctx: commands.Context, species: Optional[str] = None) -> None:
        adapter = as_interaction(ctx)
        await ExportCog.export_sheet.callback(self, adapter, species=species)

    @commands.command(name="export_webhook")
    async def export_webhook_prefix(
        self,
        ctx: commands.Context,
        species: Optional[str] = None,
        webhook_url: Optional[str] = None,
    ) -> None:
        adapter = as_interaction(ctx)
        await ExportCog.export_webhook.callback(
            self,
            adapter,
            species=species,
            webhook_url=webhook_url,
        )

    @commands.command(name="export_csv")
    async def export_csv_prefix(
        self,
        ctx: commands.Context,
        species: Optional[str] = None,
        mine: bool = False,
    ) -> None:
        adapter = as_interaction(ctx)
        await ExportCog.export_csv.callback(self, adapter, species=species, mine=mine)

    # ── /export_webhook ───────────────────────────────────────────────────────

    @app_commands.command(
        name="export_webhook",
        description="Send creature data to a Discord webhook (up to 10 at once).",
    )
    @app_commands.describe(
        species      = "Filter to a specific species",
        webhook_url  = "Override the configured webhook URL for this export",
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

        stored_webhook = await db.get_export_webhook(guild_id)
        url = webhook_url or (stored_webhook or {}).get("webhook_url") or config.EXPORT_WEBHOOK_URL
        if not url:
            await interaction.followup.send(
                "No webhook URL configured. Run `'setup` in the target channel, set `EXPORT_WEBHOOK_URL`, "
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
        description="Write your creatures to your dedicated Google Sheet.",
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

        rows = await db.list_creatures(
            guild_id=guild_id,
            species=species,
            user_id=str(interaction.user.id),
        )
        if not rows:
            await interaction.followup.send(
                "You do not have any creatures to export.",
                ephemeral=True,
            )
            return

        status = await write_to_google_sheet(rows, guild_id, interaction.user)
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
