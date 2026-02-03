---
name: manual-testing
description: Starts test communication from @BetterBohdan (sales agent) to @bohdanpytaichuk (test prospect). Use when user asks to "test", "start test", "manual test", "send test message", or "test the agent".
---

# Manual Testing

Quickly start a test conversation where @BetterBohdan sends an initial sales message to @bohdanpytaichuk.

## Account Setup

| Role | Account | Purpose |
|------|---------|---------|
| Sales Agent | @BetterBohdan | Sends outreach messages |
| Test Prospect | @bohdanpytaichuk (ID: 7836623698) | Receives messages |

## Workflow

### 1. Reset the test prospect

Update `src/sales_agent/config/prospects.json` to reset @bohdanpytaichuk as a new prospect:

```json
{
  "prospects": [
    {
      "telegram_id": "@bohdanpytaichuk",
      "name": "Богдан",
      "context": "Ищу виллу в Чангу от 250к до 400к",
      "status": "new",
      "first_contact": null,
      "last_contact": null,
      "last_response": null,
      "message_count": 0,
      "conversation_history": [],
      "notes": "Primary test prospect",
      "email": null,
      "human_active": false
    }
  ]
}
```

### 2. Run the Telegram Agent Daemon

```bash
PYTHONPATH=src uv run python src/sales_agent/daemon.py
```

The daemon will:
- Log in as @BetterBohdan
- Find the "new" prospect (@bohdanpytaichuk)
- Generate and send an initial sales message
- Update the prospect status to "contacted"

### 3. Stop after message is sent

Once you see "→ Initial message sent to Богдан", stop the daemon (Ctrl+C or kill the process).

## Quick One-Liner

For rapid testing, run this after resetting prospects.json:

```bash
pkill -f "daemon.py" 2>/dev/null; sleep 1; PYTHONPATH=src uv run python src/sales_agent/daemon.py
```

## Custom Context

To test with different prospect context, modify the `context` field in prospects.json before running:

```json
"context": "Инвестор, ищу апартаменты для сдачи в Семиньяке, бюджет до 200к"
```

## Expected Result

@bohdanpytaichuk receives a message from @BetterBohdan like:

> "Добрый день, Богдан! Меня зовут Богдан, я инвестиционный консультант компании True Real Estate..."

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "database is locked" | Run `pkill -f "daemon.py"` first |
| No message sent | Check prospect status is `"new"` in prospects.json |
| Wrong account | Verify `telegram_account` is `@BetterBohdan` in `agent_config.json` |
