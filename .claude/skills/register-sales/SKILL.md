---
name: register-sales
description: Registers a new sales representative with Telegram session, Google Calendar, and Zoom. Use when user wants to "register sales rep", "add new agent", "register-sales", or "set up a new Telegram account for sales".
---

# Register Sales Representative

This skill manages sales rep registration with full multi-account Telegram support, Google Calendar OAuth, and Zoom verification — all in a single end-to-end script.

## Sub-commands

### 1. Register a new rep (all-in-one)

Run the interactive registration script:

```bash
PYTHONPATH=src uv run python .claude/skills/register-sales/scripts/register_rep.py
```

This will walk through all 5 required steps:
1. Prompt for name, email, telegram_username, phone, agent_display_name
2. Create a Telethon session (interactive phone auth - code sent via Telegram)
3. Google Calendar OAuth (generate URL, user authorizes, paste code)
4. Zoom integration verification (check credentials file and service)
5. Save the rep to the database with `calendar_connected=True`

A rep is **only saved to the database after all steps pass**. If any step fails, registration stops with clear instructions to fix the issue and re-run.

### 2. Re-run Google Calendar setup (for debugging / token refresh)

```bash
PYTHONPATH=src uv run python .claude/skills/register-sales/scripts/setup_calendar.py --telegram-id <TELEGRAM_ID>
```

Use this standalone script to reconnect an expired calendar token or debug OAuth issues for an already-registered rep.

### 3. Re-run Zoom verification (for debugging)

```bash
PYTHONPATH=src uv run python .claude/skills/register-sales/scripts/verify_zoom.py
```

Use this standalone script to check if Zoom Server-to-Server OAuth is configured (shared across all reps).

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

## IMPORTANT: Calendar Sharing After Registration

After registering a new rep, they **must** share their Google Calendar with `bohdan.p@trueagency.online` so the sales agent can check their availability. This is a manual step the rep needs to do.

**Tell the new rep to do the following:**
1. Open Google Calendar (calendar.google.com)
2. Click the gear icon (Settings)
3. Under "Settings for my calendars", click on their calendar
4. Scroll to "Share with specific people"
5. Click "Add people" and enter: `bohdan.p@trueagency.online`
6. Set permission to: "See all event details"
7. Click Send

Without this step, the agent cannot view the rep's calendar to check availability for booking calls.

## Architecture Notes

- All rep sessions share the same `api_id`/`api_hash` from `~/.telegram_dl/config.json`
- Per-rep sessions are stored at `~/.telegram_dl/sessions/{session_name}.session`
- The default `user.session` at `~/.telegram_dl/user.session` is unchanged
- Zoom uses shared Server-to-Server OAuth - all reps share one Zoom account
- Google Calendar uses per-rep OAuth tokens stored at `~/.sales_registry/calendar_tokens/{telegram_id}.json`
- Calendar access uses OAuth authorized as `bohdan.p@trueagency.online` - reps must share their calendars with this account
