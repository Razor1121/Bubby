"""
database.py – Async SQLite helpers using aiosqlite.

Schema
------
creatures
    id              INTEGER PRIMARY KEY AUTOINCREMENT
    user_id         TEXT    NOT NULL   (Discord snowflake of the owner)
    guild_id        TEXT    NOT NULL   (Discord snowflake of the server)
    name            TEXT    NOT NULL
    species         TEXT    NOT NULL
    gender          TEXT    CHECK(gender IN ('Male','Female','Unknown'))
    level           INTEGER DEFAULT 0  (total in-game level, informational)
    stat_hp         INTEGER DEFAULT 0  (wild stat points)
    stat_stamina    INTEGER DEFAULT 0
    stat_oxygen     INTEGER DEFAULT 0
    stat_food       INTEGER DEFAULT 0
    stat_weight     INTEGER DEFAULT 0
    stat_melee      INTEGER DEFAULT 0
    stat_speed      INTEGER DEFAULT 0
    stat_torpidity  INTEGER DEFAULT 0
    mut_maternal    INTEGER DEFAULT 0
    mut_paternal    INTEGER DEFAULT 0
    notes           TEXT    DEFAULT ''
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
"""

from __future__ import annotations

import aiosqlite
from typing import Optional
from config import DATABASE_PATH

# Column order for the 8 stats (matches STAT_NAMES in ark_stats.py).
STAT_COLUMNS = [
    "stat_hp", "stat_stamina", "stat_oxygen", "stat_food",
    "stat_weight", "stat_melee", "stat_speed", "stat_torpidity",
]


# ── Initialisation ────────────────────────────────────────────────────────────

async def init_db() -> None:
    """Create tables if they do not already exist."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS creatures (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id        TEXT    NOT NULL,
                guild_id       TEXT    NOT NULL,
                name           TEXT    NOT NULL,
                species        TEXT    NOT NULL,
                gender         TEXT    DEFAULT 'Unknown',
                level          INTEGER DEFAULT 0,
                stat_hp        INTEGER DEFAULT 0,
                stat_stamina   INTEGER DEFAULT 0,
                stat_oxygen    INTEGER DEFAULT 0,
                stat_food      INTEGER DEFAULT 0,
                stat_weight    INTEGER DEFAULT 0,
                stat_melee     INTEGER DEFAULT 0,
                stat_speed     INTEGER DEFAULT 0,
                stat_torpidity INTEGER DEFAULT 0,
                mut_maternal   INTEGER DEFAULT 0,
                mut_paternal   INTEGER DEFAULT 0,
                notes          TEXT    DEFAULT '',
                created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS server_settings (
                guild_id      TEXT PRIMARY KEY,
                settings_json TEXT NOT NULL DEFAULT '{}',
                updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_by    TEXT DEFAULT ''
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS export_webhooks (
                guild_id      TEXT PRIMARY KEY,
                channel_id    TEXT NOT NULL DEFAULT '',
                webhook_url   TEXT NOT NULL DEFAULT '',
                updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_by    TEXT DEFAULT ''
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_sheets (
                guild_id         TEXT NOT NULL,
                user_id          TEXT NOT NULL,
                spreadsheet_id   TEXT NOT NULL DEFAULT '',
                spreadsheet_url  TEXT NOT NULL DEFAULT '',
                updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (guild_id, user_id)
            )
        """)
        await db.commit()


# ── Server Settings CRUD ──────────────────────────────────────────────────────

async def get_raw_server_settings(guild_id: str) -> str:
    """Return the raw JSON string for a guild's settings, or '{}' if not set."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute(
            "SELECT settings_json FROM server_settings WHERE guild_id = ?",
            (guild_id,),
        )
        row = await cur.fetchone()
        return row[0] if row else "{}"


async def save_server_settings(
    guild_id: str,
    settings_json: str,
    updated_by: str = "",
) -> None:
    """Insert or replace server settings for a guild."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO server_settings (guild_id, settings_json, updated_by, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(guild_id) DO UPDATE SET
                settings_json = excluded.settings_json,
                updated_by    = excluded.updated_by,
                updated_at    = CURRENT_TIMESTAMP
            """,
            (guild_id, settings_json, updated_by),
        )
        await db.commit()


async def delete_server_settings(guild_id: str) -> None:
    """Remove custom server settings for a guild (reverts to vanilla defaults)."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "DELETE FROM server_settings WHERE guild_id = ?", (guild_id,)
        )
        await db.commit()


async def get_export_webhook(guild_id: str) -> Optional[dict]:
    """Return the stored export webhook for a guild, if configured."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM export_webhooks WHERE guild_id = ?",
            (guild_id,),
        )
        row = await cur.fetchone()
        return _row_to_dict(row) if row else None


async def save_export_webhook(
    guild_id: str,
    channel_id: str,
    webhook_url: str,
    updated_by: str = "",
) -> None:
    """Insert or update the default export webhook for a guild."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO export_webhooks (guild_id, channel_id, webhook_url, updated_by, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(guild_id) DO UPDATE SET
                channel_id  = excluded.channel_id,
                webhook_url = excluded.webhook_url,
                updated_by  = excluded.updated_by,
                updated_at  = CURRENT_TIMESTAMP
            """,
            (guild_id, channel_id, webhook_url, updated_by),
        )
        await db.commit()


async def get_user_sheet(guild_id: str, user_id: str) -> Optional[dict]:
    """Return the stored spreadsheet info for a user in a guild, if configured."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM user_sheets WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )
        row = await cur.fetchone()
        return _row_to_dict(row) if row else None


async def save_user_sheet(
    guild_id: str,
    user_id: str,
    spreadsheet_id: str,
    spreadsheet_url: str,
) -> None:
    """Insert or update the spreadsheet info for a user in a guild."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO user_sheets (guild_id, user_id, spreadsheet_id, spreadsheet_url, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET
                spreadsheet_id  = excluded.spreadsheet_id,
                spreadsheet_url = excluded.spreadsheet_url,
                updated_at      = CURRENT_TIMESTAMP
            """,
            (guild_id, user_id, spreadsheet_id, spreadsheet_url),
        )
        await db.commit()


# ── Row → dict helper ─────────────────────────────────────────────────────────

def _row_to_dict(row: aiosqlite.Row) -> dict:
    return dict(zip(row.keys(), row))


def row_to_stats(row: dict) -> list[int]:
    """Extract the 8 wild stat point values from a database row dict."""
    return [row[col] for col in STAT_COLUMNS]


# ── CRUD ──────────────────────────────────────────────────────────────────────

async def add_creature(
    user_id: str,
    guild_id: str,
    name: str,
    species: str,
    gender: str,
    level: int,
    stats: list[int],          # [hp, stam, oxy, food, wt, melee, speed, torp]
    mut_maternal: int,
    mut_paternal: int,
    notes: str = "",
) -> int:
    """Insert a new creature and return its row id."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO creatures
                (user_id, guild_id, name, species, gender, level,
                 stat_hp, stat_stamina, stat_oxygen, stat_food,
                 stat_weight, stat_melee, stat_speed, stat_torpidity,
                 mut_maternal, mut_paternal, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                user_id, guild_id, name, species, gender, level,
                *stats,
                mut_maternal, mut_paternal, notes,
            ),
        )
        await db.commit()
        return cursor.lastrowid


async def get_creature_by_id(creature_id: int, guild_id: str) -> Optional[dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM creatures WHERE id = ? AND guild_id = ?",
            (creature_id, guild_id),
        )
        row = await cur.fetchone()
        return _row_to_dict(row) if row else None


async def get_creature_by_name(
    name: str,
    guild_id: str,
    species: Optional[str] = None,
) -> Optional[dict]:
    """Case-insensitive name lookup within a guild, optionally filtered by species."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        if species:
            cur = await db.execute(
                "SELECT * FROM creatures WHERE LOWER(name)=LOWER(?) AND guild_id=? AND LOWER(species)=LOWER(?) LIMIT 1",
                (name, guild_id, species),
            )
        else:
            cur = await db.execute(
                "SELECT * FROM creatures WHERE LOWER(name)=LOWER(?) AND guild_id=? LIMIT 1",
                (name, guild_id),
            )
        row = await cur.fetchone()
        return _row_to_dict(row) if row else None


async def list_creatures(
    guild_id: str,
    species: Optional[str] = None,
    gender: Optional[str] = None,
    user_id: Optional[str] = None,
) -> list[dict]:
    """Return all creatures in a guild, optionally filtered."""
    query  = "SELECT * FROM creatures WHERE guild_id = ?"
    params: list = [guild_id]
    if species:
        query  += " AND LOWER(species) = LOWER(?)"
        params.append(species)
    if gender:
        query  += " AND gender = ?"
        params.append(gender)
    if user_id:
        query  += " AND user_id = ?"
        params.append(user_id)
    query += " ORDER BY species, name"

    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur  = await db.execute(query, params)
        rows = await cur.fetchall()
        return [_row_to_dict(r) for r in rows]


async def update_creature(
    creature_id: int,
    guild_id: str,
    **fields,
) -> bool:
    """
    Update one or more columns of a creature row.
    Returns True if a row was actually updated.
    """
    if not fields:
        return False

    allowed = {
        "name", "species", "gender", "level", "notes",
        "mut_maternal", "mut_paternal",
        *STAT_COLUMNS,
    }
    safe = {k: v for k, v in fields.items() if k in allowed}
    if not safe:
        return False

    set_clause = ", ".join(f"{k} = ?" for k in safe)
    values     = list(safe.values()) + [creature_id, guild_id]

    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute(
            f"UPDATE creatures SET {set_clause} WHERE id = ? AND guild_id = ?",
            values,
        )
        await db.commit()
        return cur.rowcount > 0


async def delete_creature(creature_id: int, guild_id: str) -> bool:
    """Delete a creature. Returns True when a row was removed."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute(
            "DELETE FROM creatures WHERE id = ? AND guild_id = ?",
            (creature_id, guild_id),
        )
        await db.commit()
        return cur.rowcount > 0


async def search_creatures(guild_id: str, query: str) -> list[dict]:
    """Fuzzy-ish name/species search using SQL LIKE."""
    pattern = f"%{query}%"
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT * FROM creatures
               WHERE guild_id = ?
                 AND (name LIKE ? OR species LIKE ?)
               ORDER BY species, name
               LIMIT 25""",
            (guild_id, pattern, pattern),
        )
        rows = await cur.fetchall()
        return [_row_to_dict(r) for r in rows]


async def get_species_list(guild_id: str) -> list[str]:
    """Return distinct species names recorded in a guild (for autocomplete)."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute(
            "SELECT DISTINCT species FROM creatures WHERE guild_id = ? ORDER BY species",
            (guild_id,),
        )
        rows = await cur.fetchall()
        return [r[0] for r in rows]
