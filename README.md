# ARK Breeding Bot

A Discord bot that assists with dinosaur breeding in **ARK: Survival Evolved** and **ARK: Survival Ascended**.

All commands are available as slash commands and with the `>` prefix.

## Features

| Feature | Command | Description |
|---|---|---|
| Add a dino | `/add_creature` | Register a creature with all 8 wild stat points and mutation counts |
| List roster | `/list_creatures` | Browse registered creatures with pagination |
| View detail | `/view_creature` | Full stat breakdown for one creature |
| Edit stats | `/edit_creature` | Update any field on a creature |
| Remove | `/remove_creature` | Delete a creature (with confirmation) |
| Search | `/search` | Find creatures by name or species |
| Breed analysis | `/breed` | Stat inheritance odds and mutation probability for any two creatures |
| Best pairs | `/best_pair` | Automatically rank male × female pairs to find optimal breeding matches |
| Stat ranking | `/stat_check` | See which creatures hold the highest value for a specific stat |
| Mutation status | `/mutation_status` | Visual mutation counter bars for a species or single creature |
| Stacking guide | `/stacking_guide` | Step-by-step clean-female mutation stacking plan |
| Mutation calc | `/mutation_calc` | Probability tables for stacking N mutations in a target stat |
| Webhook export | `/export_webhook` | POST creature cards to any Discord webhook |
| Google Sheets | `/export_sheet` | Write your creatures to your own Google Spreadsheet |
| CSV download | `/export_csv` | Get a CSV file of your roster via DM |
| Help | `/help` or `'help` or `>help` | Detailed, category-based command guide |

---

## Quick Start

### 1. Prerequisites

- Python 3.11+
- A Discord bot token ([Discord Developer Portal](https://discord.com/developers/applications))

### 2. Install Dependencies

```bash
cd "Ark Bot"
pip install -r requirements.txt
```

### 3. Configure the Bot

Open `bot.py` and set your token in:

```python
BOT_TOKEN = "PASTE_YOUR_DISCORD_BOT_TOKEN_HERE"
```

### 4. Run the Bot

```bash
python bot.py
```

Slash commands sync automatically on first run (may take up to 1 hour to appear globally; use guild-specific sync for instant testing).

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DATABASE_PATH` | No | Path to SQLite file (default: `ark_breeding.db`) |
| `GOOGLE_CREDENTIALS_FILE` | No | Path to Google service account JSON file |
| `GOOGLE_SHARED_SPREADSHEET_ID` | No | Existing spreadsheet ID to use as shared export target (one worksheet tab per user) |
| `EXPORT_WEBHOOK_URL` | No | Default Discord webhook URL for `/export_webhook` |
| `DISCORD_GUILD_IDS` | No | Comma-separated guild IDs for immediate slash-command sync in specific servers |

---

## Google Sheets Setup (Optional)

1. Go to [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project → enable the **Google Sheets API** and **Google Drive API**.
3. Create a **Service Account** → download the JSON key file.
4. Place the JSON file in the bot directory. Optionally set `GOOGLE_CREDENTIALS_FILE` as a system environment variable (default is `credentials.json`).
5. The bot creates one spreadsheet per user the first time they run `/export_sheet`, then keeps updating that same sheet on later exports.
6. If your service account cannot create new Drive files (quota exceeded), create one spreadsheet manually in your own Drive, share it with the service account email as **Editor**, and set `GOOGLE_SHARED_SPREADSHEET_ID`. The bot will then write each user's export into a worksheet named `user-<discord_id>`.
7. Run `'setup` in a text channel if you want the bot to create and store a default export webhook for the server.

---

## Help Commands

- Run `/help` to see available help categories.
- Run `/help topic:export` (or any category) for detailed command usage.
- Prefix help supports both `'help` and `>help`.
- Prefix examples: `'help`, `'help breeding`, `>help export`.
- All slash command names can also be used with `>` (example: `>export_sheet`, `>breed`, `>server_config view`).

---

## Slash Command Sync Notes

- Global slash-command sync can take time to appear.
- Set `DISCORD_GUILD_IDS` with your server ID(s) for immediate guild sync on startup.
- Example: `DISCORD_GUILD_IDS=123456789012345678`

---

## ARK Breeding Mechanics (How the Bot Calculates)

### Stat Inheritance
Each of the 8 stats (Health, Stamina, Oxygen, Food, Weight, Melee, Speed, Torpidity) is independently inherited from either parent with a **50 % probability**. The bot shows the best possible value and the probability of getting it.

### Mutation System
- Each breeding attempt has a **7.31 %** chance of a mutation per parent (~14 % total).
- A mutation adds **+2 wild levels** to a randomly chosen stat.
- Each creature tracks **Maternal** and **Paternal** mutation counters.
- Once a parent's total mutation counter reaches **≥ 20** (soft cap), mutations from that lineage are suppressed.

### Mutation Stacking Strategy
The bot recommends the **Clean Female Method**:
1. Keep one female with **0/0 mutations** as the permanent mother.
2. Build up mutations on a male by keeping offspring that carry desired mutations.
3. Because the female is always clean, her mutation roll remains active even after the male accumulates many mutations.
4. When a male approaches the soft cap, clone the best mutations onto a new male by breeding and selecting.

---

## Wild Stat Points — How to Find Them

Open ARK → hold **H** while looking at a dino to see its stat breakdown, **or** use [ARK Smart Breeding](https://github.com/cadon/ARKStatsExtractor) to extract exact wild points. Enter those point counts (not in-game values) into `/add_creature`.

---

## Project Structure

```
Ark Bot/
├── bot.py                   ← Bot entry point
├── main.py                  ← Compatibility wrapper
├── config.py                ← Settings & constants
├── requirements.txt
├── ark_breeding.db          ← SQLite DB (auto-created)
├── cogs/
│   ├── creatures.py         ← /add_creature, /list, /view, /edit, /remove, /search
│   ├── breeding.py          ← /breed, /best_pair, /stat_check
│   ├── mutations.py         ← /mutation_status, /stacking_guide, /mutation_calc
│   └── export.py            ← /export_webhook, /export_sheet, /export_csv
└── utils/
    ├── ark_stats.py         ← ARK game constants & base stats
    ├── breeding_calculator.py ← Core probability maths
    └── database.py          ← Async SQLite helpers
```
