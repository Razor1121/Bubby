# Privacy Policy

Last updated: March 17, 2026

This Privacy Policy explains what data the ARK Helper Discord bot (the "Bot") collects, how it is used, where it is stored, and which third-party APIs/services are involved.

## 1. Scope

This policy applies to data processed by the Bot while operating in Discord servers where it is installed.

## 2. Data the Bot Collects and Stores

The Bot stores data in a local SQLite database (`ark_breeding.db`) for core functionality.

### 2.1 Discord Identifiers

- Guild ID (server ID)
- User ID (the user who owns creature entries or updates settings)
- Channel ID (for saved webhook configuration)
- Updated-by User ID (for server settings and webhook configuration history)

Purpose:
- Scope creature and settings data per server
- Associate data with the user who created/updated it
- Support export configuration and permissions workflows

### 2.2 Creature and Breeding Data

For each creature entry, the Bot stores:

- Creature record ID (database primary key)
- Owner user ID
- Guild ID
- Name
- Species
- Gender
- Level
- Wild stat points for 8 stats:
  - HP
  - Stamina
  - Oxygen
  - Food
  - Weight
  - Melee
  - Speed
  - Torpidity
- Mutation counters:
  - Maternal mutations
  - Paternal mutations
- Notes (free text provided by users)
- Created timestamp

Purpose:
- Power creature search/list/view/edit/remove
- Run breeding, mutation, and stat analysis commands
- Generate exports (webhook, Google Sheets, CSV)

### 2.3 Server Configuration Data

The Bot stores per-guild ARK multiplier settings as JSON, including:

- Wild stat multipliers (8 values)
- Tamed additive multipliers (8 values)
- Tamed affinity multipliers (8 values)
- Breeding/timer multipliers:
  - Mating interval
  - Egg hatch speed
  - Baby mature speed
  - Baby cuddle interval
  - Baby food consumption speed
  - Baby imprinting stat scale
- Taming speed multiplier
- Last-updated timestamp
- Updated-by user ID

Purpose:
- Apply server-specific multipliers to stat/breeding calculations

### 2.4 Export Configuration Data

The Bot stores webhook and sheet mapping details:

- Per-guild default export webhook:
  - Guild ID
  - Channel ID
  - Webhook URL
  - Last-updated timestamp
  - Updated-by user ID
- Per-user sheet mapping (scoped by guild):
  - Guild ID
  - User ID
  - Spreadsheet ID
  - Spreadsheet URL
  - Last-updated timestamp

Purpose:
- Reuse saved webhook destination for exports
- Reuse or map spreadsheet targets for Google Sheets export

## 3. Data Processed but Not Persisted by the Bot

The Bot may process command inputs and interaction payloads at runtime (for example, slash command options, modal text such as pasted `Game.ini` lines, and webhook URL overrides) in order to complete commands.

Not all runtime inputs are permanently stored. Only values required by features listed in Section 2 are saved.

## 4. Third-Party APIs and Services Used

### 4.1 Discord API (via discord.py)

Used for:
- Slash and prefix command handling
- Reading interaction context (guild/user/channel metadata)
- Sending replies, embeds, DMs, and files
- Creating webhooks (when setup command is used)

### 4.2 Discord Webhook Endpoints

Used for:
- Posting exported creature embeds to user-specified or saved webhook URLs

### 4.3 Google APIs (via gspread + google-auth)

Used for `/export_sheet` functionality:
- Google Sheets API
- Google Drive API (used by gspread for spreadsheet open/create operations)

Data sent to Google may include:
- Creature names/species/stats/mutation counters/notes/timestamps
- Spreadsheet identifiers and worksheet names (for routing writes)

### 4.4 Local Storage Engine

- SQLite (`aiosqlite`) for persistent local storage

## 5. Credentials and Secrets

The Bot may use the following sensitive configuration values:

- Discord bot token (configured in runtime code/environment)
- Google service account credentials JSON (for Google Sheets exports)
- Export webhook URLs

These are required for integrations to function. You are responsible for securing your deployment environment and credential files.

## 6. Data Sharing

The Bot does not sell data.

Data is shared only as needed to execute requested features:
- To Discord when sending bot messages/embeds/files
- To Discord webhook endpoints provided/configured by users/admins
- To Google services when running sheet export commands

## 7. Data Retention

Data remains stored until removed by one of the following:

- A user/admin deletes creature records via bot commands
- A server admin resets or changes server settings
- Webhook/sheet mappings are overwritten or the database is manually cleaned
- The bot owner removes database records or deletes the database file

No automatic time-based deletion is currently enforced by the Bot.

## 8. User Rights and Controls

Depending on your role in the server and the bot command permissions:

- You can view, edit, and delete creature data through bot commands
- Server admins (with required permissions) can modify/reset server config and webhook setup
- Bot owner/operator can remove data directly from local storage

To request deletion/correction beyond command-level controls, contact the bot operator.

## 9. Security Considerations

The Bot uses local storage and external APIs but does not claim guaranteed security. Deployers should:

- Protect host machine and filesystem access
- Restrict database file access
- Keep credential files private
- Rotate compromised tokens/keys/webhooks immediately
- Use least-privilege permissions in Discord and Google Cloud

## 10. Children's Privacy

The Bot is not directed at children under 13 (or higher age where required by local law).

## 11. Changes to This Policy

This Privacy Policy may be updated over time. Continued use of the Bot after updates means you accept the revised policy.

## 12. Contact

For privacy questions or data requests, contact the bot owner/operator through the project repository or support channel.
