---
name: register-sales
description: Registers a new sales representative with Telegram session, Google Calendar, and Zoom. Use when user wants to "register sales rep", "add new agent", "register-sales", or "set up a new Telegram account for sales".
---

# Register Sales Representative

This skill manages sales rep registration with full multi-account Telegram support.

## Sub-commands

### 1. Register a new rep

Run the interactive registration script:

```bash
PYTHONPATH=src uv run python .claude/skills/register-sales/scripts/register_rep.py
```

This will:
- Prompt for name, email, telegram_username, phone, agent_display_name
- Create a Telethon session (interactive phone auth - code sent via Telegram)
- Verify the session works
- Save the rep to the database

### 2. Set up Google Calendar

```bash
PYTHONPATH=src uv run python .claude/skills/register-sales/scripts/setup_calendar.py --telegram-id <TELEGRAM_ID>
```

This will:
- Generate an OAuth URL for the rep
- User opens URL, authorizes, pastes the code back
- Complete the OAuth flow and update the database

### 3. Verify Zoom integration

```bash
PYTHONPATH=src uv run python .claude/skills/register-sales/scripts/verify_zoom.py
```

Checks if Zoom Server-to-Server OAuth is configured (shared across all reps).

### 4. List all registered reps

```bash
PYTHONPATH=src uv run python .claude/skills/register-sales/scripts/list_reps.py
```

Shows a Rich table with all registered reps, their session status, and calendar connection.

### 5. Run daemon as a specific rep

After registration, the daemon can run as any registered rep:

```bash
PYTHONPATH=src uv run python src/sales_agent/daemon.py --rep-telegram-id <TELEGRAM_ID>
```

Without `--rep-telegram-id`, the daemon runs as the default account (@BetterBohdan using `user.session`).

## Architecture Notes

- All rep sessions share the same `api_id`/`api_hash` from `~/.telegram_dl/config.json`
- Per-rep sessions are stored at `~/.telegram_dl/sessions/{session_name}.session`
- The default `user.session` at `~/.telegram_dl/user.session` is unchanged
- Zoom uses shared Server-to-Server OAuth - all reps share one Zoom account
- Google Calendar uses per-rep OAuth tokens stored at `~/.sales_registry/calendar_tokens/{telegram_id}.json`
