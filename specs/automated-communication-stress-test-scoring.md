# Plan: Automated Communication Stress Test with Scoring

## Task Description
Build an automated end-to-end testing system that simulates real client communication under stress conditions and scores the results. The system should test the sales agent (@BetterBohdan) by having it communicate with a test prospect (@bohdanpytaichuk) under various stress scenarios including different response timings, multiple messages at once, and urgency requests. The ultimate goal of each test conversation is to schedule a call/meeting.

## Objective
Create a comprehensive automated stress testing framework that:
1. Simulates realistic client behavior using AI personas via the existing test accounts (@BetterBohdan as agent, @bohdanpytaichuk as prospect)
2. Tests the agent under various stress conditions (rapid messages, delayed responses, urgency demands)
3. Scores each conversation based on sales methodology (BANT, Zmeyka, tone-of-voice principles)
4. Validates that the conversation successfully ends with a scheduled call
5. Persists test results for trend analysis and quality assurance

## Problem Statement
The current testing infrastructure has:
- A conversation simulator that uses AI personas (conversation_simulator.py)
- A scoring system for evaluating conversations (conversation_evaluator.py)
- Manual testing scripts (manual_test.py)
- Predefined test scenarios (test_scenarios.py)

However, it lacks:
- Real Telegram integration for stress testing (current simulator is mock-only)
- Stress test scenarios for timing variations and message batching
- Database persistence for test results and scores
- Automated validation that calls are actually scheduled
- Configurable stress parameters (timing, message frequency, urgency)

## Solution Approach
Build an "E2E Stress Test Runner" that:
1. Uses real Telegram accounts (@BetterBohdan → @bohdanpytaichuk) for authentic testing
2. Implements stress scenarios via a StressTestPersona that controls timing/batching
3. Integrates with existing ConversationEvaluator for scoring
4. Persists results to database for tracking
5. Validates call scheduling via scheduled_actions table check

## Relevant Files
Use these files to complete the task:

### Core Testing Infrastructure (Existing - Extend)
- `src/sales_agent/testing/conversation_simulator.py` - Contains PersonaPlayer, ConversationSimulator, and data models. Extend for real Telegram integration.
- `src/sales_agent/testing/conversation_evaluator.py` - Contains ConversationAssessment and ConversationEvaluator. Use for scoring.
- `src/sales_agent/testing/test_scenarios.py` - Contains 10 predefined scenarios. Add stress test scenarios.
- `src/sales_agent/testing/manual_test.py` - Contains reset_test_prospect function. Reuse for test setup.
- `src/sales_agent/testing/run_conversation_tests.py` - CLI runner for tests. Extend for stress tests.

### Telegram Integration (Existing - Use)
- `src/sales_agent/telegram/telegram_service.py` - TelegramService for sending/receiving messages
- `src/sales_agent/telegram/telegram_fetch.py` - Low-level Telethon client operations
- `src/sales_agent/daemon.py` - Main daemon that processes messages and generates responses

### Message Batching (Existing - Test Against)
- `src/sales_agent/messaging/message_buffer.py` - MessageBuffer for debounce batching (test target)

### Scheduling (Existing - Validate)
- `src/sales_agent/scheduling/scheduled_action_manager.py` - Database ops for scheduled actions. Check for ZOOM_SCHEDULED.
- `src/sales_agent/scheduling/scheduling_tool.py` - SchedulingTool for booking meetings

### CRM/Models (Existing - Use)
- `src/sales_agent/crm/models.py` - Prospect, AgentAction, ProspectStatus models
- `src/sales_agent/crm/prospect_manager.py` - ProspectManager for state management

### Configuration (Existing - Use)
- `src/sales_agent/config/test_accounts.json` - Test account configuration
- `src/sales_agent/config/prospects.json` - Prospect data
- `src/sales_agent/config/agent_config.json` - Agent configuration with timing settings

### Database (Existing - Extend)
- `src/sales_agent/database/init.py` - Database initialization and migrations
- `src/sales_agent/migrations/` - Existing migrations

### New Files
- `src/sales_agent/testing/stress_test_runner.py` - Main stress test orchestration
- `src/sales_agent/testing/stress_scenarios.py` - Stress test scenario definitions
- `src/sales_agent/testing/test_result_manager.py` - Database persistence for test results
- `src/sales_agent/testing/e2e_telegram_player.py` - Real Telegram persona player
- `src/sales_agent/migrations/006_test_results.sql` - Database schema for test results

## Implementation Phases

### Phase 1: Foundation (Database Schema & Models)
- Create database migration for test_results and test_assessments tables
- Create TestResultManager class for persisting results
- Extend ConversationAssessment model with result_id and timestamp fields

### Phase 2: Core Implementation (Stress Test Infrastructure)
- Create E2ETelegramPlayer that sends messages via real Telegram (as @bohdanpytaichuk responding to @BetterBohdan)
- Create StressTestRunner that orchestrates daemon + persona player
- Implement stress scenarios with configurable timing parameters

### Phase 3: Integration & Polish
- Integrate scoring with result persistence
- Add CLI interface for running stress tests
- Add validation for call scheduling outcome
- Create test reporting and analytics

## Step by Step Tasks

### 1. Create Database Migration for Test Results
- Create `src/sales_agent/migrations/006_test_results.sql`
- Define `test_results` table with fields: id (UUID), scenario_name, persona_id, outcome, overall_score, total_turns, duration_seconds, email_collected, call_scheduled, timestamp, created_at
- Define `test_assessments` table with all ConversationAssessment fields plus test_result_id foreign key
- Add indexes on scenario_name, timestamp, overall_score for efficient querying

### 2. Create TestResultManager Class
- Create `src/sales_agent/testing/test_result_manager.py`
- Implement `save_test_result(result: ConversationResult, assessment: ConversationAssessment) -> str` that returns result_id
- Implement `get_test_results(scenario_name: str = None, limit: int = 100) -> list[TestResult]`
- Implement `get_score_trends(days: int = 30) -> list[DailyScoreSummary]`
- Implement `get_scenario_analytics(scenario_name: str) -> ScenarioAnalytics`
- Use asyncpg connection pool pattern from scheduled_action_manager.py

### 3. Create Stress Test Scenarios
- Create `src/sales_agent/testing/stress_scenarios.py`
- Define StressConfig model with fields: message_delays (list of delay ranges), batch_sizes (how many messages to send at once), urgency_requests (specific urgency phrases), timeout_multiplier
- Create STRESS_SCENARIOS list with:
  - **Rapid Fire Burst**: Send 5 messages within 2 seconds, test batching
  - **Slow Responder**: Add 30-60 second delays between responses, test follow-up patience
  - **Urgency Demand**: Include "respond in 2 minutes" and similar phrases
  - **Mixed Timing**: Alternate between fast and slow responses
  - **Long Messages**: Send multi-paragraph messages testing reading delays
  - **Interruption Pattern**: Send message, wait for typing indicator, send another
- Each scenario should have persona traits, stress config, and expected outcome

### 4. Create E2E Telegram Persona Player
- Create `src/sales_agent/testing/e2e_telegram_player.py`
- Create E2ETelegramPlayer class that uses real Telegram client (as @bohdanpytaichuk)
- Initialize with session path from test_accounts.json (different session than agent)
- Implement `send_message(agent_telegram_id: str, message: str) -> int` returning message_id
- Implement `wait_for_response(agent_telegram_id: str, timeout: float) -> str | None` that polls for new messages
- Implement `send_batch(messages: list[str], delays: list[float])` for stress testing
- Use Telethon client similar to telegram_fetch.py but for the test prospect account
- Handle typing indicators and read receipts for realistic simulation

### 5. Create Stress Test Runner
- Create `src/sales_agent/testing/stress_test_runner.py`
- Create StressTestRunner class that:
  - Accepts scenario config with stress parameters
  - Initializes E2ETelegramPlayer for test prospect
  - Runs daemon in subprocess (like manual_test.py) or uses in-process agent
  - Orchestrates conversation flow with timing controls
  - Tracks turn-by-turn conversation state
  - Applies stress conditions (delays, batches) per scenario
- Implement `run_stress_test(scenario: StressScenario, verbose: bool = False) -> StressTestResult`
- Include timeout handling for agent responses (max wait before fail)
- Track timing metrics: response_times[], batch_detection_accuracy, etc.

### 6. Implement Stress Scenario Execution Logic
- In stress_test_runner.py, implement scenario execution:
  - **Pre-test**: Reset prospect via reset_test_prospect(), cancel scheduled actions
  - **Execution**: Loop through persona turns with stress timing applied
  - **Timing**: Use StressConfig to determine delays between messages
  - **Batching**: For batch scenarios, send multiple messages before waiting for response
  - **Urgency**: Inject urgency phrases at configured conversation points
  - **Monitoring**: Watch for typing indicators, read receipts
  - **Post-test**: Check scheduled_actions table for ZOOM_SCHEDULED status
- Return StressTestResult with timing metrics, conversation transcript, and outcome

### 7. Add Call Scheduling Validation
- In stress_test_runner.py, add validation method:
- Implement `validate_call_scheduled(prospect_id: str) -> CallSchedulingResult`
- Query scheduled_actions table for actions with prospect_id and action_type='pre_meeting_reminder' or status changes
- Check if prospect status is ZOOM_SCHEDULED in prospects.json
- Return CallSchedulingResult with: scheduled (bool), scheduled_time (datetime), zoom_url (str | None)
- This is the key success metric: stress tests should still result in scheduled calls

### 8. Integrate Scoring and Persistence
- In stress_test_runner.py, after test completion:
- Build ConversationResult from collected turns
- Call ConversationEvaluator.evaluate(result) to get assessment
- Add stress-specific metrics to result: response_times, batch_handling_score, urgency_response_time
- Call TestResultManager.save_test_result(result, assessment) to persist
- Include call_scheduled flag from validation step

### 9. Create CLI Interface
- Extend `src/sales_agent/testing/run_conversation_tests.py` OR create new `run_stress_tests.py`
- Add CLI arguments:
  - `--scenario NAME` - Run specific stress scenario
  - `--all-stress` - Run all stress scenarios
  - `--parallel N` - Run N tests concurrently (careful with Telegram rate limits)
  - `--output FILE` - Export results to JSON
  - `--verbose` - Print real-time conversation
  - `--timing-report` - Generate timing analysis report
- Display rich console output with progress bars (use existing rich patterns)
- Show summary table with scores and pass/fail for call scheduling

### 10. Create Test Report Generator
- In stress_test_runner.py or separate module:
- Implement `generate_stress_test_report(results: list[StressTestResult]) -> StressTestReport`
- Include sections:
  - **Summary**: Total tests, pass rate (call scheduled), average score
  - **Timing Analysis**: Response time percentiles (p50, p95, p99), slowest responses
  - **Batching Analysis**: How well agent handled rapid messages
  - **Urgency Analysis**: Did agent respond faster to urgency requests?
  - **Score Distribution**: Histogram of overall scores
  - **Regression Detection**: Compare to previous runs (if available)
- Output as markdown and/or HTML for easy review

### 11. Validate End-to-End Flow
- Create test script that runs a single stress scenario end-to-end
- Verify: prospect reset → daemon starts → persona sends stress messages → agent responds → call scheduled → assessment saved
- Check database for test_results and test_assessments entries
- Verify scores are reasonable (not all zeros or error defaults)
- Confirm scheduled_actions table has meeting entry

## Testing Strategy
### Unit Tests (without Telegram)
- Test StressConfig validation and scenario loading
- Test TestResultManager CRUD operations with real database (ephemeral data)
- Test timing calculation logic
- Test message aggregation for batch scenarios

### Integration Tests (with mock Telegram)
- Test E2ETelegramPlayer can send/receive messages
- Test StressTestRunner timeout handling
- Test call scheduling validation query

### E2E Tests (with real Telegram)
- Run single stress scenario with verbose output
- Verify message delivery and response timing
- Confirm call scheduling outcome
- Persist and retrieve test results

### Stress Test Validation
- Run "Rapid Fire Burst" scenario - verify batching works
- Run "Slow Responder" scenario - verify agent patience
- Run "Urgency Demand" scenario - verify timely response
- All should result in scheduled calls (success criteria)

## Acceptance Criteria
1. **Stress scenarios executable**: Can run predefined stress scenarios against real Telegram accounts
2. **Timing variations work**: Tests can apply configurable delays and batch sizes
3. **Call scheduling validated**: Each test verifies whether a call was successfully scheduled
4. **Scoring integrated**: Every test produces a ConversationAssessment with 0-100 score
5. **Results persisted**: Test results stored in database with full conversation transcripts
6. **CLI available**: Can run stress tests from command line with various options
7. **Report generated**: Can produce summary report of test results with timing analysis
8. **Pass rate measurable**: Can determine what % of stress tests result in scheduled calls

## Validation Commands
Execute these commands to validate the task is complete:

- `uv run python -m py_compile src/sales_agent/testing/stress_test_runner.py` - Verify syntax
- `uv run python -m py_compile src/sales_agent/testing/stress_scenarios.py` - Verify syntax
- `uv run python -m py_compile src/sales_agent/testing/e2e_telegram_player.py` - Verify syntax
- `uv run python -m py_compile src/sales_agent/testing/test_result_manager.py` - Verify syntax
- `PYTHONPATH=src uv run python src/sales_agent/database/init.py` - Apply migrations (creates test_results tables)
- `PYTHONPATH=src uv run python src/sales_agent/testing/stress_scenarios.py` - Self-test stress scenarios module
- `PYTHONPATH=src uv run python src/sales_agent/testing/run_stress_tests.py --scenario "Rapid Fire Burst" --verbose` - Run single stress test
- `PYTHONPATH=src uv run python src/sales_agent/testing/run_stress_tests.py --all-stress --output results.json` - Run all stress tests

## Notes

### Test Account Setup
- **Agent Account**: @BetterBohdan (session: `~/.telegram_dl/user.session` or configured session)
- **Test Prospect Account**: @bohdanpytaichuk (Telegram ID: 7836623698) - needs separate session file
- The test prospect needs its own Telethon session to send messages AS the prospect
- Create session via: `PYTHONPATH=src uv run python -c "from telethon import TelegramClient; client = TelegramClient('test_prospect', api_id, api_hash)"`

### Telegram Rate Limits
- Avoid sending too many messages too fast (Telegram may rate limit)
- Add small delays (0.5-1s) between rapid messages even in stress tests
- Don't run parallel tests against same account pair

### Daemon Mode Options
1. **Subprocess mode**: Start daemon as subprocess, communicate via Telegram (more realistic)
2. **In-process mode**: Import and call agent directly (faster, less realistic)
- Recommend subprocess mode for accurate timing measurements

### Database Requirements
- PostgreSQL must be running with DATABASE_URL configured in .env
- Run migrations before first test: `PYTHONPATH=src uv run python src/sales_agent/database/init.py`

### Dependencies
- No new dependencies required - uses existing:
  - `telethon` for Telegram
  - `asyncpg` for database
  - `pydantic` for models
  - `rich` for CLI output
  - `anthropic` (via Agent SDK) for persona AI
