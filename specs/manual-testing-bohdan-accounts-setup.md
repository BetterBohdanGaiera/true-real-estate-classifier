# Plan: Manual Testing Setup with Bohdan Accounts

## Task Description
Configure the system so that when manual tests are requested, Claude correctly identifies and uses the Bohdan-related accounts:
- **Center account** (sender): The Telegram account that runs the daemon and sends messages as "Мария" (the agent)
- **Receiver account** (prospect): @bohdanpytaichuk (Bohdan) who receives messages and responds during testing

The system must always send the starting (initial) message first when a test is initiated, allowing the user to respond and test the full conversation flow.

## Objective
Create a streamlined manual testing workflow where:
1. Claude can identify test accounts automatically
2. The daemon sends the initial message to the Bohdan prospect
3. The user can respond via Telegram to test the full system
4. The workflow supports future multi-account expansion

## Problem Statement
Currently, manual testing requires:
1. Understanding the current account setup
2. Resetting the prospect status to "new" to trigger initial message
3. Running the daemon manually
4. No clear documentation or automation for test setup

The user needs a reliable, repeatable process where Claude can correctly pick up both accounts and initiate the test conversation.

## Solution Approach
1. Create a test configuration file that explicitly defines test accounts (center/receiver)
2. Add a CLI command or script to reset and initiate manual tests
3. Document the testing workflow clearly
4. Ensure the daemon always sends the starting message when a prospect is in "new" status

## Relevant Files
Use these files to complete the task:

### Configuration Files
- `src/sales_agent/config/prospects.json` - Main prospects database where Bohdan is configured
- `src/sales_agent/config/agent_config.json` - Agent settings (Мария identity)
- `~/.telegram_dl/config.json` - Telegram API credentials for the center account
- `~/.telegram_dl/user.session` - Authenticated session for sending messages

### Daemon Files
- `src/sales_agent/daemon.py` - Main daemon that processes prospects and sends messages
- `src/sales_agent/crm/prospect_manager.py` - Handles prospect status and conversation history

### Telegram Files
- `.claude/skills/telegram/scripts/telegram_fetch.py` - Telegram client setup and authentication
- `.claude/skills/telegram/scripts/telegram_service.py` - Message sending service (add delete_messages)
- `src/sales_agent/telegram/telegram_service.py` - Main telegram service (add delete_messages)

### New Files
- `src/sales_agent/testing/manual_test.py` - New script for initiating manual tests

## Implementation Phases

### Phase 1: Configuration
Create a test accounts configuration file that defines:
- Center account identifier (the logged-in session)
- Test prospect accounts (Bohdan and future test accounts)
- Test mode flags

### Phase 2: Telegram Message Deletion
Add capability to delete previous agent messages from Telegram chat:
- Add `delete_messages()` method to TelegramService
- Delete all agent-sent messages from conversation history
- **Note**: Can only delete messages sent by the center account, not prospect's replies

### Phase 3: Test Initialization Script
Create a script that:
- Resets the test prospect to "new" status
- Clears conversation history (local JSON)
- Deletes previous agent messages from Telegram chat (optional, with --clean-chat flag)
- Clears any pending scheduled actions
- Starts the daemon
- Waits for the initial message to be sent

### Phase 4: Documentation
Document the testing workflow for future reference

## Step by Step Tasks

### 1. Create Test Accounts Configuration
- Create `src/sales_agent/config/test_accounts.json` with test account definitions
- Define center account info (from ~/.telegram_dl session)
- Define test prospects list with Bohdan as the primary test account
- Add flags for test mode behavior

### 2. Add Message Deletion to TelegramService
- Add `delete_messages(chat_id, message_ids, revoke=True)` method to `src/sales_agent/telegram/telegram_service.py`
- Also add to `.claude/skills/telegram/scripts/telegram_service.py` for consistency
- Use Telethon's `client.delete_messages(chat, message_ids, revoke=True)`
- Add `delete_conversation_messages(telegram_id, message_ids)` helper that:
  - Accepts a prospect's telegram_id
  - Deletes specified messages (agent-sent only)
  - Returns count of deleted messages
- **Limitation**: Can only delete messages sent by the authenticated account (center), not the prospect's replies

### 3. Add Manual Test Script
- Create `src/sales_agent/testing/manual_test.py`
- Implement `reset_test_prospect(clean_chat=False)` function to:
  - Set prospect status to "new"
  - Clear conversation history (local JSON)
  - If `clean_chat=True`: delete agent messages from Telegram chat
  - Clear any pending scheduled actions
- Implement `start_test_session()` function to:
  - Reset the test prospect
  - Start the daemon
  - Wait for initial message to be sent
  - Output clear instructions for the user
- Add CLI flags:
  - `--reset-only`: Reset without starting daemon
  - `--clean-chat`: Also delete agent messages from Telegram

### 4. Update ProspectManager with Reset Method
- Add `reset_prospect(telegram_id)` method to `src/sales_agent/crm/prospect_manager.py`
- Reset all fields: status, message_count, conversation_history, timestamps
- Keep telegram_id, name, context, and notes
- Return list of agent message IDs (for optional Telegram deletion)

### 5. Add CLI Entry Point
- Update `pyproject.toml` to add a `test-agent` CLI command
- Entry point: `sales_agent.testing.manual_test:main`

### 6. Validate the Workflow
- Run the test script to reset Bohdan prospect
- Start daemon and verify initial message is sent
- Respond in Telegram and verify the system handles the response
- Check conversation history is recorded correctly

## Testing Strategy

### Manual Test Workflow
1. Run `uv run python -m sales_agent.testing.manual_test --clean-chat`
2. Script resets @bohdanpytaichuk to "new" status
3. Previous agent messages are deleted from Telegram chat
4. Daemon starts and sends initial message
5. User responds via Telegram app
6. Verify response handling in daemon logs
7. Repeat for different conversation scenarios

### Verification Points
- Initial message is always sent to test prospect
- `--clean-chat` deletes agent messages from Telegram (check chat visually)
- Responses are correctly attributed to the prospect
- Conversation history is properly recorded
- Rate limits don't block test messages
- Working hours don't block tests (optional override)

## Acceptance Criteria
1. Test accounts are defined in configuration file
2. `manual_test.py` script can reset and initiate a test session
3. `--clean-chat` flag deletes agent messages from Telegram chat
4. Initial message is always sent when test is started
5. User can respond via Telegram and see the agent's responses
6. Conversation history is recorded for analysis
7. Process is documented and repeatable

## Validation Commands
Execute these commands to validate the task is complete:

- `uv run python -c "from sales_agent.testing.manual_test import reset_test_prospect; print('Import OK')"` - Verify module is importable
- `uv run python -m sales_agent.testing.manual_test --reset-only` - Reset prospect without starting daemon
- `uv run python -m sales_agent.testing.manual_test --reset-only --clean-chat` - Reset + delete agent messages from Telegram
- `uv run python -m sales_agent.testing.manual_test` - Full test (reset + start daemon + send initial message)
- `uv run python -m sales_agent.testing.manual_test --clean-chat` - Full test with Telegram chat cleanup
- `cat src/sales_agent/config/prospects.json | jq '.prospects[0].status'` - Verify prospect status is reset

## Notes

### Account Architecture
- **Center account**: The Telegram user account running the daemon (authenticated via `~/.telegram_dl/user.session`). This is the account that sends messages as "Мария".
- **Receiver/Prospect account**: @bohdanpytaichuk - The test account that receives messages. The user (Bohdan) will respond to these messages to test the system.

### Multi-Account Future Support
The test configuration is designed to support multiple test accounts:
```json
{
  "test_accounts": [
    {
      "telegram_id": "@bohdanpytaichuk",
      "name": "Богдан",
      "role": "primary_test"
    }
  ]
}
```

### Telegram Chat Cleanup
The `--clean-chat` flag uses Telethon's `client.delete_messages()` to delete agent messages:
```python
await client.delete_messages(chat_id, message_ids, revoke=True)
```

**Capabilities:**
- Deletes messages for both parties (`revoke=True`)
- Works on messages of any age in private conversations (since March 2019)
- Returns count of successfully deleted messages

**Limitations:**
- Can only delete messages **sent by the center account** (agent messages)
- Cannot delete the prospect's replies - those remain in the chat
- For a completely clean chat, the prospect would need to manually delete their own messages

**Practical implication:** After `--clean-chat`, the Telegram chat will show only Bohdan's previous replies (if any). The agent's messages will be gone from both sides.

### Environment Requirements
- `DATABASE_URL` in `.env` for scheduled actions (optional for basic testing)
- `ANTHROPIC_API_KEY` in `.env` for Claude agent responses
- Telegram session authenticated in `~/.telegram_dl/`
