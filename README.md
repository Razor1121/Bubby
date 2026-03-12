# ARK Breeding Bot

A Discord bot that assists with dinosaur breeding in **ARK: Survival Evolved** and **ARK: Survival Ascended**.

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
| Google Sheets | `/export_sheet` | Write the full roster to a Google Spreadsheet |
| CSV download | `/export_csv` | Get a CSV file of your roster via DM |

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

```bash
copy .env.example .env
```

Open `.env` and fill in at minimum:

```env
DISCORD_TOKEN=your_token_here
```

### 4. Run the Bot

```bash
python main.py
```

Slash commands sync automatically on first run (may take up to 1 hour to appear globally; use guild-specific sync for instant testing).

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DISCORD_TOKEN` | ✅ Yes | Your bot token from the Developer Portal |
| `DATABASE_PATH` | No | Path to SQLite file (default: `ark_breeding.db`) |
| `GOOGLE_CREDENTIALS_FILE` | No | Path to Google service account JSON file |
| `GOOGLE_SHEET_ID` | No | ID portion of your Google Sheet URL |
| `EXPORT_WEBHOOK_URL` | No | Default Discord webhook URL for `/export_webhook` |

---

## Google Sheets Setup (Optional)

1. Go to [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project → enable the **Google Sheets API** and **Google Drive API**.
3. Create a **Service Account** → download the JSON key file.
4. Place the JSON file in the bot directory and set `GOOGLE_CREDENTIALS_FILE=credentials.json` in `.env`.
5. **Share** your target Google Sheet with the service account email (found inside the JSON file under `client_email`).
6. Set `GOOGLE_SHEET_ID` to the sheet ID from its URL:
   `https://docs.google.com/spreadsheets/d/`**`THIS_PART`**`/edit`

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
├── main.py                  ← Bot entry point
├── config.py                ← Settings & constants
├── requirements.txt
├── .env.example             ← Copy to .env and fill in
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
