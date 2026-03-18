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

## Usage

- Use `/help` to view available command categories and command details.
- Primary workflows are creature tracking, breeding analysis, mutation planning, and exports.

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
