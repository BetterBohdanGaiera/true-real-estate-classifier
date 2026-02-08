---
name: testing
description: Conversation testing and simulation framework. Use for stress tests, conversation simulation, manual testing, and quality evaluation. Invoked for "run tests", "stress test", "simulate conversation", "evaluate agent", or "test the agent".
---

# Testing Framework

Comprehensive testing utilities for the Telegram sales agent. Includes conversation simulation with AI-powered personas, stress testing with real Telegram integration, conversation quality evaluation, and test result persistence.

## Test Accounts

| Role | Account | Telegram ID | Purpose |
|------|---------|-------------|---------|
| Sales Agent | @BetterBohdan | - | Runs the sales agent, sends outreach messages |
| Test Prospect | @bohdanpytaichuk | 7836623698 | Receives messages from agent, plays client role |

**Important:** Only use ONE test prospect (@bohdanpytaichuk) for all testing scenarios.

## Test Types Overview

| Test Type | Script | Real Telegram | Use Case |
|-----------|--------|---------------|----------|
| Stress Tests | `run_stress_tests.py` | Yes | E2E timing/batching validation |
| Conversation Simulation | `conversation_simulator.py` | No | Mock persona conversations |
| Manual Testing | `manual_test.py` | Yes | Quick agent testing |
| Mock Daemon | `mock_telegram_daemon.py` | No | Business logic testing |

---

## Stress Testing (E2E)

End-to-end stress tests with real Telegram communication, stress timing, and call scheduling validation.

### Run Single Stress Test

```bash
PYTHONPATH=src uv run python src/sales_agent/testing/run_stress_tests.py --scenario "Rapid Fire Burst" --verbose
```

### Run All Stress Tests

```bash
PYTHONPATH=src uv run python src/sales_agent/testing/run_stress_tests.py --all-stress
```

### List Available Scenarios

```bash
PYTHONPATH=src uv run python src/sales_agent/testing/run_stress_tests.py --list
```

### With Timing Report and JSON Export

```bash
PYTHONPATH=src uv run python src/sales_agent/testing/run_stress_tests.py --all-stress --timing-report --output results.json
```

### Stress Scenarios

Seven predefined stress scenarios test agent behavior under challenging conditions:

| Scenario | Stress Type | Description |
|----------|-------------|-------------|
| Rapid Fire Burst | Timing | 3-5 messages in quick succession (0.3-1.0s gaps) |
| Slow Responder | Timing | Long delays (30-120s) between messages |
| Urgency Demand | Content | Phrases like "need answer NOW", "urgent" |
| Long Messages | Content | 300+ character detailed messages |
| Mixed Timing | Pattern | Alternating fast/slow message cadence |
| Interruption Pattern | Pattern | Messages while agent is typing |
| Realistic Multi-Message | Pattern | Natural conversation bursts |

### Stress Test CLI Options

```bash
Options:
  --scenario NAME    Run specific scenario by name
  --all-stress       Run all 7 stress scenarios
  --verbose          Show detailed conversation flow
  --timing-report    Print timing analysis
  --output FILE      Export results to JSON file
  --list             List available scenarios
```

---

## Conversation Simulation (Mock)

Simulates multi-turn conversations with AI-powered personas without real Telegram integration.

### Run Conversation Simulation

```bash
PYTHONPATH=src uv run python src/sales_agent/testing/run_conversation_tests.py
```

### Test Scenarios

Ten challenging persona scenarios in `test_scenarios.py`:

| Scenario | Difficulty | Description |
|----------|------------|-------------|
| Skeptical Financist | Hard | Professional investor demanding ROI data |
| Catalog Requester | Hard | Wants PDF only, refuses all calls |
| After the War Deferred | Medium | Postpones decisions citing geopolitical situation |
| Competitor Comparison | Hard | Actively comparing with other agencies |
| Time Zone Challenged | Medium | International client with scheduling conflicts |
| Budget Unclear | Medium | Vague about financial capacity |
| Technical Deep Dive | Expert | Asks detailed construction/legal questions |
| Family Decision Maker | Hard | Needs spouse approval, won't commit alone |
| Previous Bad Experience | Hard | Burned by other agencies, very skeptical |
| Quick Qualifier | Easy | Ready to buy, tests basic escalation |

### Persona Components

- **PersonaDefinition**: Name, traits, objections, difficulty, language
- **ConversationScenario**: Persona + context + expected outcome
- **PersonaPlayer**: AI-powered persona roleplay using Claude

---

## Manual Testing

Quick reset-and-test workflow for interactive agent testing.

### Reset and Start Daemon

```bash
PYTHONPATH=src uv run python src/sales_agent/testing/manual_test.py
```

### Reset Only (No Daemon)

```bash
PYTHONPATH=src uv run python src/sales_agent/testing/manual_test.py --reset-only
```

### Reset with Chat Cleanup

```bash
PYTHONPATH=src uv run python src/sales_agent/testing/manual_test.py --clean-chat
```

### What Manual Test Does

1. Resets @bohdanpytaichuk to `"new"` status in prospects.json
2. Cancels any pending scheduled actions for the test prospect
3. Optionally clears Telegram chat history
4. Starts the daemon which sends initial outreach message

## Docker Testing

Run the agent in Docker containers (postgres + telegram-agent) for production-like testing.

### Start Docker Test Session

```bash
uv run python .claude/skills/testing/scripts/manual_test.py --docker
```

### Docker with Chat Cleanup

```bash
uv run python .claude/skills/testing/scripts/manual_test.py --docker --clean-chat
```

### What Docker Test Does

1. Resets @bohdanpytaichuk to `"new"` status in prospects.json (skips DB cleanup)
2. Optionally clears Telegram chat history
3. Tears down previous Docker state (`docker compose down -v`)
4. Builds and starts `postgres` + `telegram-agent` containers in foreground
5. Streams logs until Ctrl+C
6. Cleans up containers on exit (`docker compose down`)

**Note:** DB cleanup is skipped because `docker compose down -v` removes the postgres volume, giving a fresh database each run.

---

## Mock Telegram Daemon

Production-like simulation without network calls. Tests business logic with real MessageBuffer debouncing.

### Usage in Tests

```python
from sales_agent.testing.mock_telegram_daemon import MockTelegramDaemon

daemon = MockTelegramDaemon()
await daemon.initialize()

# Simulate rapid incoming messages
await daemon.simulate_incoming_message("Hello!")
await asyncio.sleep(0.5)
await daemon.simulate_incoming_message("I have questions")

# Wait for batch processing (real debounce timing)
await daemon.wait_for_response(timeout=30.0)
response = daemon.get_last_agent_response()
```

### What Mock Daemon Tests

- Real MessageBuffer debouncing behavior
- Real TelegramAgent response generation
- Real follow-up scheduling (writes to database)
- Real timing delays (reading, typing simulation)
- Mock network transport only

---

## Conversation Evaluation

AI-powered quality assessment against tone-of-voice and communication methodology.

### Evaluation Criteria

| Category | Metrics |
|----------|---------|
| Overall | Score (0-100), what went well, areas for improvement |
| Personalization | Used client name (0-10) |
| Questions | Ended with open questions (0-10) |
| Value First | Explained value before asking (0-10) |
| BANT | Budget, Authority, Need, Timeline coverage |
| Zmeyka | Easy question, Reflect, Show expertise, Ask next |
| Objection Handling | Addressed objections properly (0-10) |

### Binary Checks

- Zoom close attempt made
- Message length appropriate (2-5 sentences)
- Formal language used (Russian "Vy")
- No forbidden topics (freehold for foreigners)

### Usage

```python
from sales_agent.testing import ConversationEvaluator

evaluator = ConversationEvaluator()
assessment = await evaluator.evaluate(conversation_result)

print(f"Score: {assessment.overall_score}/100")
print(f"BANT: {assessment.bant_coverage}")
```

---

## Test Result Persistence

Database storage for test results and analytics in `test_results` and `test_assessments` tables.

### Save Test Result

```python
from sales_agent.testing.test_result_manager import save_test_result

await save_test_result(conversation_result, assessment)
```

### Query Analytics

```python
from sales_agent.testing.test_result_manager import (
    get_score_trends,
    get_scenario_analytics,
)

# Daily score trends
trends = await get_score_trends(days=7)

# Per-scenario analytics
analytics = await get_scenario_analytics("Rapid Fire Burst")
print(f"Pass rate: {analytics.pass_rate}%")
```

### Analytics Data

- **DailyScoreSummary**: avg/min/max scores, test count, pass rate
- **ScenarioAnalytics**: per-scenario success rates and trends

---

## Message Splitter

Utility for splitting long responses into natural message chunks for realistic multi-message simulation.

### Usage

```python
from sales_agent.testing import split_response_naturally

messages = split_response_naturally(
    "Long text here. Multiple sentences. More content."
)
# Returns: ["Long text here.", "Multiple sentences. More content."]
```

### Features

- Respects sentence boundaries
- Handles Russian abbreviations (т.е., т.к., и т.д.)
- Preserves natural message groupings

---

## E2E Telegram Player

Real Telegram integration for stress tests. Sends messages AS the test prospect.

### Usage

```python
from sales_agent.testing.e2e_telegram_player import E2ETelegramPlayer

player = E2ETelegramPlayer(session_name="test_prospect")
await player.connect()

# Send single message
msg_id = await player.send_message("@BetterBohdan", "Hello!")

# Wait for agent response
response = await player.wait_for_response("@BetterBohdan", timeout=60.0)

# Send batch (stress test)
msg_ids = await player.send_batch(
    "@BetterBohdan",
    ["Question 1?", "Question 2?", "Question 3?"],
    delays=[0.3, 0.3, 0.0]
)

await player.disconnect()
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | All tests passed (call_scheduled=True for all) |
| 1 | One or more tests failed or error occurred |

## Module Imports

```python
# Main testing components
from sales_agent.testing import (
    ConversationSimulator,
    ConversationEvaluator,
    test_scenarios,
    split_response_naturally,
    TestPatternIterator,
)

# Stress testing
from sales_agent.testing.stress_test_runner import StressTestRunner
from sales_agent.testing.stress_scenarios import (
    STRESS_SCENARIOS,
    get_stress_scenario_by_name,
)

# Result management
from sales_agent.testing.test_result_manager import (
    save_test_result,
    get_score_trends,
    get_scenario_analytics,
)
```

## Dependencies

Required packages (installed via uv):
- `asyncpg>=0.29.0` - Database operations
- `python-dotenv>=1.0.0` - Environment variables
- `pydantic>=2.0.0` - Data models
- `telethon>=1.28.0` - Telegram integration (E2E tests)
- `rich>=13.0.0` - Console output

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "database is locked" | Run `pkill -f "daemon.py"` first |
| No message sent | Check prospect status is `"new"` in prospects.json |
| Test prospect not found | Verify @bohdanpytaichuk in test_accounts.json |
| Telegram auth failed | Run setup for test_prospect session |
| Score trends empty | Run some tests first to populate database |
