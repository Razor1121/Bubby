"""
cogs/creatures.py – Slash commands for managing the breeding roster.

Commands
--------
/add_creature   – Register a new dino with its wild stat points & mutation counts.
/list_creatures – List all creatures in the guild (filterable by species / gender).
/view_creature  – View full details of a single creature.
/edit_creature  – Edit any field of an existing creature.
/remove_creature – Permanently delete a creature from the database.
/search         – Search creatures by name or species.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

import config
from utils import database as db
from utils.ark_stats import (
    STAT_NAMES, STAT_SHORT, STAT_EMOJI, KNOWN_SPECIES, format_stat_table
)
from utils.database import row_to_stats
from utils.server_settings import ServerSettings, load_guild_settings
from utils.prefix_adapter import as_interaction


# ── Helpers ───────────────────────────────────────────────────────────────────

GENDER_CHOICES = [
    app_commands.Choice(name="Male",    value="Male"),
    app_commands.Choice(name="Female",  value="Female"),
    app_commands.Choice(name="Unknown", value="Unknown"),
]


def creature_embed(
    row: dict,
    title: str = "",
    settings: ServerSettings = None,
) -> discord.Embed:
    """Build a Discord embed from a database creature row."""
    stats   = row_to_stats(row)
    species = row.get("species", "Unknown")
    name    = row.get("name",    "Unknown")
    gender  = row.get("gender",  "Unknown")
    gender_emoji = {"Male": "♂️", "Female": "♀️"}.get(gender, "❓")

    embed = discord.Embed(
        title=title or f"{gender_emoji} {name}  [{species}]  — ID #{row['id']}",
        colour=config.EMBED_COLOR,
    )

    mut_total = row["mut_maternal"] + row["mut_paternal"]
    mut_label = f"{row['mut_maternal']}/{row['mut_paternal']}  (total: {mut_total})"
    cap_warn  = "⚠️ At / above soft cap!" if mut_total >= config.MUTATION_SOFT_CAP else ""

    embed.add_field(name="Species",    value=species,               inline=True)
    embed.add_field(name="Gender",     value=f"{gender_emoji} {gender}", inline=True)
    embed.add_field(name="Level",      value=str(row.get("level", 0)), inline=True)
    embed.add_field(
        name="Mutations",
        value=f"**{mut_label}** {cap_warn}  *(maternal/paternal)*",
        inline=False,
    )
    wild_mults = settings.wild_mults if settings else None
    embed.add_field(
        name="Wild Stat Points",
        value=format_stat_table(stats, species, wild_mults=wild_mults),
        inline=False,
    )

    notes = row.get("notes", "").strip()
    if notes:
        embed.add_field(name="Notes", value=notes, inline=False)

    footer = f"Added by user {row['user_id']}"
    if settings and not settings.is_default:
        footer += "  |  ★ Custom server multipliers active"
    embed.set_footer(text=footer)
    return embed


async def species_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    """Autocomplete from species already registered in the guild."""
    guild_species = await db.get_species_list(str(interaction.guild_id))
    # Merge with built-in list
    all_species = sorted(set(guild_species) | set(KNOWN_SPECIES))
    filtered = [s for s in all_species if current.lower() in s.lower()]
    return [app_commands.Choice(name=s, value=s) for s in filtered[:25]]


async def creature_name_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    rows = await db.search_creatures(str(interaction.guild_id), current)
    return [
        app_commands.Choice(
            name=f"{r['name']} [{r['species']}] #{r['id']}",
            value=str(r["id"]),
        )
        for r in rows
    ]


# ── Cog ───────────────────────────────────────────────────────────────────────

class CreaturesCog(commands.Cog, name="Creatures"):
    """Manage your ARK breeding roster."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _gender_choice_from_text(
        self,
        value: Optional[str],
    ) -> Optional[app_commands.Choice[str]]:
        if value is None:
            return None
        cleaned = value.strip().lower()
        mapping = {
            "male": "Male",
            "female": "Female",
            "unknown": "Unknown",
        }
        normalized = mapping.get(cleaned)
        if not normalized:
            return None
        return app_commands.Choice(name=normalized, value=normalized)

    @commands.command(name="add_creature")
    async def add_creature_prefix(
        self,
        ctx: commands.Context,
        name: str,
        species: str,
        gender: str,
        level: int = 0,
        hp: int = 0,
        stamina: int = 0,
        oxygen: int = 0,
        food: int = 0,
        weight: int = 0,
        melee: int = 0,
        speed: int = 0,
        torpidity: int = 0,
        mut_mat: int = 0,
        mut_pat: int = 0,
        *,
        notes: str = "",
    ) -> None:
        gender_choice = self._gender_choice_from_text(gender)
        if gender_choice is None:
            await ctx.send("Gender must be one of: Male, Female, Unknown")
            return

        adapter = as_interaction(ctx)
        await CreaturesCog.add_creature.callback(
            self,
            adapter,
            name=name,
            species=species,
            gender=gender_choice,
            level=level,
            hp=hp,
            stamina=stamina,
            oxygen=oxygen,
            food=food,
            weight=weight,
            melee=melee,
            speed=speed,
            torpidity=torpidity,
            mut_mat=mut_mat,
            mut_pat=mut_pat,
            notes=notes,
        )

    @commands.command(name="list_creatures")
    async def list_creatures_prefix(
        self,
        ctx: commands.Context,
        species: Optional[str] = None,
        gender: Optional[str] = None,
        mine: bool = False,
    ) -> None:
        gender_choice = self._gender_choice_from_text(gender)
        if gender is not None and gender_choice is None:
            await ctx.send("Gender must be one of: Male, Female, Unknown")
            return
        adapter = as_interaction(ctx)
        await CreaturesCog.list_creatures.callback(
            self,
            adapter,
            species=species,
            gender=gender_choice,
            mine=mine,
        )

    @commands.command(name="view_creature")
    async def view_creature_prefix(self, ctx: commands.Context, creature_id: int) -> None:
        adapter = as_interaction(ctx)
        await CreaturesCog.view_creature.callback(self, adapter, creature_id=creature_id)

    @commands.command(name="edit_creature")
    async def edit_creature_prefix(
        self,
        ctx: commands.Context,
        creature_id: int,
        name: Optional[str] = None,
        species: Optional[str] = None,
        gender: Optional[str] = None,
        level: Optional[int] = None,
        hp: Optional[int] = None,
        stamina: Optional[int] = None,
        oxygen: Optional[int] = None,
        food: Optional[int] = None,
        weight: Optional[int] = None,
        melee: Optional[int] = None,
        speed: Optional[int] = None,
        torpidity: Optional[int] = None,
        mut_mat: Optional[int] = None,
        mut_pat: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> None:
        gender_choice = self._gender_choice_from_text(gender)
        if gender is not None and gender_choice is None:
            await ctx.send("Gender must be one of: Male, Female, Unknown")
            return

        adapter = as_interaction(ctx)
        await CreaturesCog.edit_creature.callback(
            self,
            adapter,
            creature_id=creature_id,
            name=name,
            species=species,
            gender=gender_choice,
            level=level,
            hp=hp,
            stamina=stamina,
            oxygen=oxygen,
            food=food,
            weight=weight,
            melee=melee,
            speed=speed,
            torpidity=torpidity,
            mut_mat=mut_mat,
            mut_pat=mut_pat,
            notes=notes,
        )

    @commands.command(name="remove_creature")
    async def remove_creature_prefix(self, ctx: commands.Context, creature_id: int) -> None:
        adapter = as_interaction(ctx)
        await CreaturesCog.remove_creature.callback(self, adapter, creature_id=creature_id)

    @commands.command(name="search")
    async def search_prefix(self, ctx: commands.Context, *, query: str) -> None:
        adapter = as_interaction(ctx)
        await CreaturesCog.search.callback(self, adapter, query=query)

    # ── /add_creature ─────────────────────────────────────────────────────────

    @app_commands.command(
        name="add_creature",
        description="Register a dino with its wild stat points and mutation counts.",
    )
    @app_commands.describe(
        name       = "Nickname / identifier for this creature",
        species    = "Species name (e.g. Rex, Arg, Giga)",
        gender     = "Male / Female / Unknown",
        level      = "Total in-game level (informational)",
        hp         = "Wild stat points – Health",
        stamina    = "Wild stat points – Stamina",
        oxygen     = "Wild stat points – Oxygen",
        food       = "Wild stat points – Food",
        weight     = "Wild stat points – Weight",
        melee      = "Wild stat points – Melee Damage",
        speed      = "Wild stat points – Movement Speed (usually 0 for land dinos)",
        torpidity  = "Wild stat points – Torpidity",
        mut_mat    = "Maternal mutation counter",
        mut_pat    = "Paternal mutation counter",
        notes      = "Optional free-text notes",
    )
    @app_commands.choices(gender=GENDER_CHOICES)
    @app_commands.autocomplete(species=species_autocomplete)
    async def add_creature(
        self,
        interaction: discord.Interaction,
        name: str,
        species: str,
        gender: app_commands.Choice[str],
        level: int = 0,
        hp: int = 0,
        stamina: int = 0,
        oxygen: int = 0,
        food: int = 0,
        weight: int = 0,
        melee: int = 0,
        speed: int = 0,
        torpidity: int = 0,
        mut_mat: int = 0,
        mut_pat: int = 0,
        notes: str = "",
    ):
        await interaction.response.defer(ephemeral=False)

        stats = [hp, stamina, oxygen, food, weight, melee, speed, torpidity]

        creature_id = await db.add_creature(
            user_id      = str(interaction.user.id),
            guild_id     = str(interaction.guild_id),
            name         = name,
            species      = species,
            gender       = gender.value,
            level        = level,
            stats        = stats,
            mut_maternal = mut_mat,
            mut_paternal = mut_pat,
            notes        = notes,
        )

        row      = await db.get_creature_by_id(creature_id, str(interaction.guild_id))
        srv      = await load_guild_settings(str(interaction.guild_id))
        embed    = creature_embed(row, title=f"✅ Creature Added — {name}", settings=srv)
        await interaction.followup.send(embed=embed)

    # ── /list_creatures ───────────────────────────────────────────────────────

    @app_commands.command(
        name="list_creatures",
        description="List all registered creatures. Filter by species or gender.",
    )
    @app_commands.describe(
        species = "Filter by species",
        gender  = "Filter by gender",
        mine    = "Show only creatures you added",
    )
    @app_commands.choices(gender=GENDER_CHOICES)
    @app_commands.autocomplete(species=species_autocomplete)
    async def list_creatures(
        self,
        interaction: discord.Interaction,
        species: Optional[str] = None,
        gender: Optional[app_commands.Choice[str]] = None,
        mine: bool = False,
    ):
        await interaction.response.defer()

        rows = await db.list_creatures(
            guild_id = str(interaction.guild_id),
            species  = species,
            gender   = gender.value if gender else None,
            user_id  = str(interaction.user.id) if mine else None,
        )

        if not rows:
            await interaction.followup.send(
                "No creatures found matching those filters.", ephemeral=True
            )
            return

        # Split into pages of 10 creatures.
        pages = [rows[i : i + 10] for i in range(0, len(rows), 10)]

        def make_page(page_rows: list[dict], page_num: int) -> discord.Embed:
            embed = discord.Embed(
                title=f"🦕 Breeding Roster  (page {page_num}/{len(pages)})",
                colour=config.EMBED_COLOR,
            )
            lines = []
            for r in page_rows:
                gender_sym = {"Male": "♂️", "Female": "♀️"}.get(r["gender"], "❓")
                mut = f"{r['mut_maternal']}/{r['mut_paternal']}"
                stat_sum = sum(row_to_stats(r))
                lines.append(
                    f"`#{r['id']:>4}` {gender_sym} **{r['name']}**  "
                    f"*{r['species']}*  |  Mut: {mut}  |  "
                    f"Total pts: {stat_sum}  |  Lvl {r['level']}"
                )
            embed.description = "\n".join(lines)
            embed.set_footer(text=f"Total: {len(rows)} creature(s)")
            return embed

        if len(pages) == 1:
            await interaction.followup.send(embed=make_page(pages[0], 1))
        else:
            view    = _PaginatorView(pages, make_page, interaction.user)
            message = await interaction.followup.send(
                embed=make_page(pages[0], 1), view=view
            )
            view.message = message

    # ── /view_creature ────────────────────────────────────────────────────────

    @app_commands.command(
        name="view_creature",
        description="View detailed stats for a specific creature.",
    )
    @app_commands.describe(
        creature_id = "Creature ID number (use /list_creatures to find it)",
    )
    async def view_creature(
        self,
        interaction: discord.Interaction,
        creature_id: int,
    ):
        await interaction.response.defer()
        row = await db.get_creature_by_id(creature_id, str(interaction.guild_id))
        if not row:
            await interaction.followup.send(
                f"No creature found with ID **#{creature_id}** in this server.",
                ephemeral=True,
            )
            return
        srv = await load_guild_settings(str(interaction.guild_id))
        await interaction.followup.send(embed=creature_embed(row, settings=srv))

    # ── /edit_creature ────────────────────────────────────────────────────────

    @app_commands.command(
        name="edit_creature",
        description="Update a creature's stats, mutation counts, or info.",
    )
    @app_commands.describe(
        creature_id = "ID of the creature to edit",
        name        = "New nickname",
        species     = "New species",
        gender      = "New gender",
        level       = "New level",
        hp          = "New HP wild pts",
        stamina     = "New Stamina wild pts",
        oxygen      = "New Oxygen wild pts",
        food        = "New Food wild pts",
        weight      = "New Weight wild pts",
        melee       = "New Melee wild pts",
        speed       = "New Speed wild pts",
        torpidity   = "New Torpidity wild pts",
        mut_mat     = "New maternal mutation counter",
        mut_pat     = "New paternal mutation counter",
        notes       = "New notes",
    )
    @app_commands.choices(gender=GENDER_CHOICES)
    async def edit_creature(
        self,
        interaction: discord.Interaction,
        creature_id: int,
        name: Optional[str] = None,
        species: Optional[str] = None,
        gender: Optional[app_commands.Choice[str]] = None,
        level: Optional[int] = None,
        hp: Optional[int] = None,
        stamina: Optional[int] = None,
        oxygen: Optional[int] = None,
        food: Optional[int] = None,
        weight: Optional[int] = None,
        melee: Optional[int] = None,
        speed: Optional[int] = None,
        torpidity: Optional[int] = None,
        mut_mat: Optional[int] = None,
        mut_pat: Optional[int] = None,
        notes: Optional[str] = None,
    ):
        await interaction.response.defer()

        row = await db.get_creature_by_id(creature_id, str(interaction.guild_id))
        if not row:
            await interaction.followup.send(
                f"No creature found with ID **#{creature_id}**.", ephemeral=True
            )
            return

        updates: dict = {}
        if name     is not None: updates["name"]         = name
        if species  is not None: updates["species"]      = species
        if gender   is not None: updates["gender"]       = gender.value
        if level    is not None: updates["level"]        = level
        if hp       is not None: updates["stat_hp"]      = hp
        if stamina  is not None: updates["stat_stamina"] = stamina
        if oxygen   is not None: updates["stat_oxygen"]  = oxygen
        if food     is not None: updates["stat_food"]    = food
        if weight   is not None: updates["stat_weight"]  = weight
        if melee    is not None: updates["stat_melee"]   = melee
        if speed    is not None: updates["stat_speed"]   = speed
        if torpidity is not None: updates["stat_torpidity"] = torpidity
        if mut_mat  is not None: updates["mut_maternal"] = mut_mat
        if mut_pat  is not None: updates["mut_paternal"] = mut_pat
        if notes    is not None: updates["notes"]        = notes

        if not updates:
            await interaction.followup.send(
                "No changes provided — specify at least one field to update.",
                ephemeral=True,
            )
            return

        await db.update_creature(creature_id, str(interaction.guild_id), **updates)
        updated_row = await db.get_creature_by_id(creature_id, str(interaction.guild_id))
        srv   = await load_guild_settings(str(interaction.guild_id))
        embed = creature_embed(updated_row, title=f"✏️ Updated — {updated_row['name']}", settings=srv)
        await interaction.followup.send(embed=embed)

    # ── /remove_creature ──────────────────────────────────────────────────────

    @app_commands.command(
        name="remove_creature",
        description="Permanently delete a creature from the roster.",
    )
    @app_commands.describe(creature_id="ID of the creature to remove")
    async def remove_creature(
        self,
        interaction: discord.Interaction,
        creature_id: int,
    ):
        row = await db.get_creature_by_id(creature_id, str(interaction.guild_id))
        if not row:
            await interaction.response.send_message(
                f"No creature found with ID **#{creature_id}**.", ephemeral=True
            )
            return

        view = _ConfirmDeleteView(row, interaction.user)
        await interaction.response.send_message(
            f"⚠️ Are you sure you want to delete **{row['name']}** (#{creature_id})?",
            view=view,
            ephemeral=True,
        )

    # ── /search ───────────────────────────────────────────────────────────────

    @app_commands.command(
        name="search",
        description="Search creatures by name or species.",
    )
    @app_commands.describe(query="Name or species to search for")
    async def search(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        rows = await db.search_creatures(str(interaction.guild_id), query)
        if not rows:
            await interaction.followup.send(
                f"No creatures matched `{query}`.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"🔍 Search results for '{query}'",
            colour=config.EMBED_COLOR,
        )
        lines = []
        for r in rows:
            gender_sym = {"Male": "♂️", "Female": "♀️"}.get(r["gender"], "❓")
            mut = f"{r['mut_maternal']}/{r['mut_paternal']}"
            lines.append(
                f"`#{r['id']:>4}` {gender_sym} **{r['name']}** *{r['species']}*  "
                f"Mut: {mut}  Lvl {r['level']}"
            )
        embed.description = "\n".join(lines)
        await interaction.followup.send(embed=embed)


# ── UI Components ─────────────────────────────────────────────────────────────

class _ConfirmDeleteView(discord.ui.View):
    def __init__(self, row: dict, owner: discord.User):
        super().__init__(timeout=30)
        self.row   = row
        self.owner = owner

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message(
                "Only the person who ran this command can confirm.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Yes, delete", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, _: discord.ui.Button):
        deleted = await db.delete_creature(self.row["id"], self.row["guild_id"])
        if deleted:
            await interaction.response.edit_message(
                content=f"🗑️ **{self.row['name']}** (#{self.row['id']}) has been removed.",
                view=None,
            )
        else:
            await interaction.response.edit_message(
                content="Could not delete — it may have already been removed.",
                view=None,
            )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.edit_message(content="Deletion cancelled.", view=None)


class _PaginatorView(discord.ui.View):
    def __init__(self, pages, make_page_fn, owner: discord.User):
        super().__init__(timeout=120)
        self.pages        = pages
        self.make_page    = make_page_fn
        self.owner        = owner
        self.current_page = 0
        self.message: discord.Message = None  # type: ignore[assignment]
        self._update_buttons()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.owner.id

    def _update_buttons(self):
        self.prev_btn.disabled = self.current_page == 0
        self.next_btn.disabled = self.current_page == len(self.pages) - 1

    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.current_page -= 1
        self._update_buttons()
        await interaction.response.edit_message(
            embed=self.make_page(self.pages[self.current_page], self.current_page + 1),
            view=self,
        )

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.current_page += 1
        self._update_buttons()
        await interaction.response.edit_message(
            embed=self.make_page(self.pages[self.current_page], self.current_page + 1),
            view=self,
        )


# ── Setup ─────────────────────────────────────────────────────────────────────

async def setup(bot: commands.Bot):
    await bot.add_cog(CreaturesCog(bot))
