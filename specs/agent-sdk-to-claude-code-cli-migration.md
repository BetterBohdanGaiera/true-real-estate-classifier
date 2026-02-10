# Plan: Migrate Agent SDK Behavior to Claude Code CLI Task Executor

## Task Description
Migrate all current Claude Agent SDK / raw Anthropic API behavior in the Telegram sales bot to use the Claude Code CLI task executor approach. The current `TelegramAgent` class uses `anthropic.Anthropic.messages.create()` directly with custom tool definitions and JSON action parsing. This needs to be refactored to leverage the Claude Code CLI (`claude -p`) via the existing `cli-task-executor` skill, enabling session management, structured output, permission control, and all Claude Code features.

## Objective
Replace the raw Anthropic API calls in `TelegramAgent` with Claude Code CLI subprocess invocations via the `ClaudeTaskExecutor` class. The agent should produce identical conversational behavior (replies, waits, scheduling, availability checks, follow-ups) but execute through `claude -p` instead of direct API calls. This unlocks Claude Code features like session persistence, MCP server integration, tool restrictions, budget control, and multi-turn context management.

## Problem Statement
The current agent architecture has several limitations:
1. **No session persistence** - Each API call is stateless; conversation history is manually stuffed into a single user prompt
2. **No native tool execution** - Only `schedule_followup` is a real Claude tool; `check_availability` and `schedule` are pseudo-tools via JSON-in-text
3. **No MCP integration** - Cannot leverage MCP servers for external tool access
4. **No budget control** - No way to limit per-conversation or per-day spend
5. **Manual context management** - Knowledge base, tone-of-voice, and methodology are manually injected into prompts
6. **Unused dependency** - `claude-agent-sdk>=0.1.19` in pyproject.toml is never imported
7. **Hardcoded model** - `claude-sonnet-4-20250514` appears in 3 places without configuration

## Solution Approach
Replace `Anthropic.messages.create()` calls with `ClaudeTaskExecutor.execute_with_config()` calls using structured JSON output. The system prompt and tools become Claude Code's native system prompt + skills. Conversation history leverages Claude Code session management instead of prompt stuffing.

**Architecture Change:**
```
BEFORE: TelegramAgent → Anthropic SDK → Claude API → Parse JSON/tool_use
AFTER:  TelegramAgent → ClaudeTaskExecutor → claude -p CLI → Parse structured output
```

## Relevant Files

### Core Files to Modify
- `src/telegram_sales_bot/core/agent.py` (819 lines) - Main agent class with 3 API call methods, system prompt builder, response parser. **This is the primary file to refactor.**
- `src/telegram_sales_bot/core/daemon.py` (1202 lines) - Orchestrator that initializes agent and dispatches actions. Needs updates to pass session IDs and handle new response format.
- `src/telegram_sales_bot/core/models.py` (345 lines) - Pydantic models including `AgentAction`, `AgentConfig`. May need new fields for session management and CLI config.
- `pyproject.toml` - Remove unused `claude-agent-sdk` dependency, potentially add subprocess-related utilities.

### CLI Task Executor (Reference)
- `.claude/skills/cli-task-executor/skill.md` (687 lines) - Complete CLI reference and migration guide. **Key reference for all CLI flags and patterns.**
- `.claude/skills/cli-task-executor/scripts/execute_task.py` (809 lines) - Python wrapper with `ClaudeTaskExecutor` class, `TaskConfig`, `TaskResult`. **This is the execution engine.**

### Knowledge & Skills (Context Sources)
- `.claude/skills/telegram/config/agent_config.json` - Agent behavior configuration
- `.claude/skills/tone-of-voice/SKILL.md` + `references/` - Communication style (loaded into system prompt)
- `.claude/skills/how-to-communicate/SKILL.md` + `references/` - Sales methodology (loaded into system prompt)
- `src/telegram_sales_bot/knowledge/base/` - 12 knowledge base topic files (00-11)
- `src/telegram_sales_bot/knowledge/loader.py` (349 lines) - KnowledgeLoader with keyword-based topic detection

### Scheduling & Integrations (Tool Targets)
- `src/telegram_sales_bot/scheduling/tool.py` (958 lines) - SchedulingTool for availability/booking
- `src/telegram_sales_bot/integrations/zoom.py` (337 lines) - Zoom meeting creation
- `src/telegram_sales_bot/integrations/google_calendar.py` (348 lines) - Calendar connector
- `src/telegram_sales_bot/integrations/elevenlabs.py` (279 lines) - Voice transcription
- `src/telegram_sales_bot/integrations/media_detector.py` (244 lines) - Media type detection

### Configuration & Infrastructure
- `.claude/skills/telegram/config/prospects.json` - Prospect state machine
- `src/telegram_sales_bot/config/agent_config.json` - Package-level config copy
- `deployment/docker/docker-compose.yml` - Docker orchestration
- `deployment/docker/Dockerfile` - Main daemon container

### New Files
- `src/telegram_sales_bot/core/cli_agent.py` - New agent implementation using ClaudeTaskExecutor
- `src/telegram_sales_bot/core/agent_schema.json` - JSON schema for structured agent output
- `.claude/skills/telegram/config/agent_system_prompt.md` - Extracted system prompt as a standalone file for Claude Code's `--system-prompt` flag

## Implementation Phases

### Phase 1: Foundation - CLI Executor Integration & Schema Definition
Prepare the execution infrastructure: fix bugs in `execute_task.py`, define the structured output JSON schema, extract the system prompt to a file, and create the new agent module.

### Phase 2: Core Implementation - Replace API Calls with CLI Execution
Implement the new `CLITelegramAgent` class that uses `ClaudeTaskExecutor` for all three generation methods (initial message, response, follow-up). Add session management for conversation continuity.

### Phase 3: Integration & Polish - Wire Daemon, Test, Clean Up
Update the daemon to use the new agent, add session tracking to prospect models, remove the unused `claude-agent-sdk` dependency, and validate end-to-end behavior.

## Step by Step Tasks

### 1. Fix Bugs in execute_task.py
- Fix the broken `execute_streaming()` method at line 588: change `await self._execute_streaming_config(config)` to `async for chunk in self._execute_streaming_config(config): yield chunk`
- Move `import re` from line 344 to module-level imports
- Add error handling for `json.loads(args.agents)` at line 789 (wrap in try-except)
- Extract duplicated result-parsing logic from `execute_with_config()` (lines 427-445) and `execute_with_config_async()` (lines 532-548) into a shared `_build_task_result()` method

### 2. Define Structured Output JSON Schema
- Create `src/telegram_sales_bot/core/agent_schema.json` with the following schema:
```json
{
  "type": "object",
  "properties": {
    "action": {
      "type": "string",
      "enum": ["reply", "wait", "check_availability", "schedule", "schedule_followup", "escalate"]
    },
    "message": { "type": "string", "description": "Message text to send to client" },
    "reason": { "type": "string", "description": "Brief explanation of decision" },
    "scheduling_data": {
      "type": "object",
      "properties": {
        "slot_id": { "type": "string" },
        "follow_up_time": { "type": "string" },
        "follow_up_intent": { "type": "string" }
      }
    }
  },
  "required": ["action", "reason"]
}
```
- This replaces the current hybrid tool_use + JSON-in-text parsing with a single, reliable structured output format

### 3. Extract System Prompt to Standalone File
- Extract the system prompt from `agent.py:_build_system_prompt()` (lines 186-420) into `.claude/skills/telegram/config/agent_system_prompt.md`
- Keep placeholder tokens (`<Ваше_имя>`, `<Руководитель_продаж>`, `<Имя_клиента>`) for runtime replacement
- The system prompt includes: identity/persona, tone-of-voice, communication methodology, knowledge base cheatsheet, scheduling instructions, media handling, response format (now referencing the JSON schema), wait/don't-reply rules
- Update the response format section to instruct the model to ALWAYS output the JSON schema format (removing the hybrid tool_use + text-JSON approach)

### 4. Create CLITelegramAgent Class
- Create `src/telegram_sales_bot/core/cli_agent.py` with `CLITelegramAgent` class
- Constructor accepts same parameters as current `TelegramAgent` (tone_of_voice_path, how_to_communicate_path, knowledge_base_path, config, agent_name)
- Initialize `ClaudeTaskExecutor` in constructor (import from cli-task-executor scripts)
- Add `sys.path` manipulation or copy `execute_task.py` into the package to make it importable
- Store a `sessions: dict[str, str]` mapping prospect_id → session_id for conversation continuity
- Implement `_build_system_prompt()` that reads the extracted `.md` file and performs placeholder replacements
- Implement `_build_task_config()` helper that creates a `TaskConfig` with:
  - `system_prompt`: The assembled system prompt
  - `output_format`: `OutputFormat.JSON`
  - `json_schema`: Path to `agent_schema.json`
  - `model`: From config (default `claude-sonnet-4-20250514`)
  - `max_turns`: 1 (single-turn for most operations)
  - `dangerously_skip_permissions`: True (bot context, no user interaction)
  - `session_id`: From `sessions[prospect_id]` if exists
  - `resume`: Previous session_id for conversation continuity
  - `timeout`: 60 seconds

### 5. Implement generate_initial_message() via CLI
- Build the user prompt (same content as current: prospect info, phase tracker phrases, conversation context)
- Inject relevant knowledge base context via `KnowledgeLoader.get_relevant_context()`
- Create `TaskConfig` with `prompt=user_prompt`, no session resume (new conversation)
- Execute via `executor.execute_with_config(config)`
- Parse `TaskResult.parsed_json` into `AgentAction` using the schema
- Store the returned `session_id` in `self.sessions[prospect_id]`
- Apply `_sanitize_output()` to the message text
- Return `AgentAction`

### 6. Implement generate_response() via CLI
- Build the user prompt (same content as current: prospect info, message batch detection, conversation history, knowledge context, gap context)
- Create `TaskConfig` with `prompt=user_prompt`, `resume=self.sessions.get(prospect_id)` for session continuity
- Execute via `executor.execute_with_config(config)`
- Parse `TaskResult.parsed_json` into `AgentAction`
- Update `self.sessions[prospect_id]` with new session_id
- Apply `_sanitize_output()` to the message text
- Return `AgentAction`

### 7. Implement generate_follow_up() via CLI
- Build the user prompt (same content as current: prospect info, follow-up context, intent)
- For scheduled follow-ups: do NOT include scheduling tools in the prompt (prevent recursive scheduling) - achieve this by adding instruction in the system prompt or using `--disallowedTools`
- Create `TaskConfig` with `prompt=user_prompt`, `resume=self.sessions.get(prospect_id)`
- Execute via `executor.execute_with_config(config)`
- Parse result, update session, sanitize, return `AgentAction`

### 8. Add Session Management to Models
- Add `session_id: Optional[str] = None` field to `Prospect` model in `models.py`
- Add `cli_model: str = "claude-sonnet-4-20250514"` field to `AgentConfig`
- Add `cli_timeout: int = 60` field to `AgentConfig`
- Add `cli_max_budget_usd: Optional[float] = None` field to `AgentConfig`
- Update prospects.json schema to persist session_id per prospect

### 9. Update Daemon to Use CLITelegramAgent
- In `daemon.py`, add import for `CLITelegramAgent`
- In `initialize()`, replace `TelegramAgent(...)` with `CLITelegramAgent(...)`
- Keep the same action dispatch logic in `_handle_action()` - the `AgentAction` model is unchanged
- Add session_id persistence: after each agent call, save `agent.sessions[prospect_id]` to prospect data
- On daemon startup, restore sessions from prospect data into `agent.sessions`

### 10. Remove Unused Dependencies and Clean Up
- Remove `claude-agent-sdk>=0.1.19` from `pyproject.toml` dependencies
- Remove `from anthropic import Anthropic` from `agent.py` (keep old file as `agent_legacy.py` for rollback)
- Add `cli-task-executor` scripts to Python path or copy `execute_task.py` into `src/telegram_sales_bot/core/`
- Remove `__pycache__` from `.claude/skills/cli-task-executor/scripts/` and add to `.gitignore`
- Update CLAUDE.md to document the new CLI-based agent architecture

### 11. Validate End-to-End Behavior
- Run `PYTHONPATH=src uv run python -c "from telegram_sales_bot.core.cli_agent import CLITelegramAgent; print('Import OK')"` to verify imports
- Test initial message generation: set @bohdanpytaichuk to "new" in prospects.json, run daemon, verify message sent
- Test response generation: send a test message from @bohdanpytaichuk, verify agent responds
- Test follow-up scheduling: trigger a follow-up via conversation, verify it's scheduled in database
- Test session continuity: verify subsequent messages resume the same Claude Code session
- Compare output quality between old (direct API) and new (CLI) approaches

## Testing Strategy

### Unit Tests
- Test `CLITelegramAgent._build_system_prompt()` produces valid prompt with all sections
- Test `CLITelegramAgent._build_task_config()` produces correct CLI flags
- Test JSON schema parsing with various valid and invalid responses
- Test session management (store, retrieve, update session IDs)

### Integration Tests
- Test `ClaudeTaskExecutor.execute_with_config()` returns valid JSON matching schema
- Test session resume produces contextually aware responses
- Test structured output parsing with real Claude responses
- Test error handling when CLI times out or returns non-zero exit code

### End-to-End Tests
- Full conversation flow: initial message → response → follow-up → scheduling
- Compare response quality between legacy agent and CLI agent
- Verify all action types work: reply, wait, check_availability, schedule, schedule_followup, escalate
- Test with real Telegram accounts (@BetterBohdan → @bohdanpytaichuk)

## Acceptance Criteria
1. All 3 generation methods (initial, response, follow-up) work via `claude -p` CLI
2. Structured JSON output is reliably parsed into `AgentAction` models
3. Session continuity works - subsequent messages in a conversation share context
4. All 6 action types (reply, wait, check_availability, schedule, schedule_followup, escalate) produce correct behavior
5. Response quality is equivalent to the direct API approach
6. `claude-agent-sdk` dependency is removed from `pyproject.toml`
7. The daemon starts, connects to Telegram, and handles messages end-to-end
8. Knowledge base context injection works per-message
9. System prompt includes all skills (tone-of-voice, methodology, knowledge base)
10. No regressions in existing behavior (message batching, typing simulation, media detection, voice transcription)

## Validation Commands
Execute these commands to validate the task is complete:

- `uv run python -m py_compile src/telegram_sales_bot/core/cli_agent.py` - Verify new agent compiles
- `uv run python -m py_compile src/telegram_sales_bot/core/daemon.py` - Verify daemon compiles
- `uv run python -c "from telegram_sales_bot.core.cli_agent import CLITelegramAgent; print('OK')"` - Verify import works
- `which claude` - Verify Claude Code CLI is installed
- `claude -p "respond with: hello" --output-format json --json-schema '{"type":"object","properties":{"greeting":{"type":"string"}},"required":["greeting"]}' --dangerously-skip-permissions` - Verify CLI structured output works
- `PYTHONPATH=src uv run python -m telegram_sales_bot.core.daemon` - Verify daemon starts (Ctrl+C to stop)
- `uv run pytest tests/ -v` - Run any existing tests

## Notes
- The `claude` CLI must be installed globally (`npm install -g @anthropic-ai/claude-code`) for the executor to work
- In Docker, the CLI needs to be installed in the container image - update Dockerfiles accordingly
- Session persistence across daemon restarts requires saving session IDs to prospects.json or database
- The structured output via `--json-schema` flag eliminates the fragile hybrid parsing (tool_use blocks + JSON-in-text)
- Budget control via `--max-budget-usd` is a new capability not available in the direct API approach
- Consider adding `--max-turns 3` for complex scheduling conversations that may need tool use loops
- The `execute_task.py` script has a broken streaming method (Issue #1 from scout report) - fix before relying on it
- Monitor CLI subprocess overhead vs direct API latency - the CLI adds startup time but gains session management
