# Plan: Realistic Multi-Message Conversation Patterns in Stress Tests

## Task Description

Implement realistic multi-message conversation patterns in stress tests to replace the current strict Client-Agent-Client-Agent alternating pattern with more realistic patterns that simulate real Telegram conversations:

- Client-Client-Client-Agent (user sends burst of messages with pauses between them)
- Client-Agent-Agent (agent sends follow-up clarification naturally)
- Client-Client-Agent-Agent-Client (mixed patterns)

This will properly test the MessageBuffer batching system with realistic production traffic patterns.

## Objective

Enable stress tests to simulate realistic conversation patterns where:
1. PersonaPlayer can generate and return multiple messages (burst behavior with realistic pauses up to 1-2 minutes)
2. Agent responses can naturally span multiple messages when answering a single message
3. The test runner follows configurable message patterns for test orchestration
4. MessageBuffer batching (timing-based detection) is properly tested with these patterns

**Key Distinction:**
- **Production System**: Uses TIMING-BASED detection (MessageBuffer debounce) to determine when user has finished their message sequence. The system doesn't know "patterns" - it waits for silence.
- **Test Orchestration**: Uses PATTERNS to simulate realistic user behavior for testing purposes.

## Problem Statement

**Current Behavior:**
The test flow strictly alternates Client-Agent-Client-Agent. The logic in `stress_test_runner.py` lines 504-618 checks `last_turn.speaker` to determine who speaks next:
- If agent spoke last → persona responds
- If persona spoke last → wait for agent

**Production Reality:**
Real conversations have much more complex patterns:
- Users send 2-5 messages with variable pauses (seconds to 1-2 minutes between messages)
- The SYSTEM determines "completion" via timing (debounce timeout), not by counting messages
- Agents naturally send multiple messages when a single response would be too long or when adding clarifications
- Messages arrive in unpredictable patterns that MessageBuffer handles via timing

**Gap:**
The existing `conversation_pattern` field in `StressConfig` (line 78) is **defined but never used** in the test runner code.

## Solution Approach

Implement a two-layer solution:

1. **Test Layer (Orchestration)**:
   - Use message patterns in tests to simulate client behavior (C-C-C-A means send 3 client messages then wait)
   - PersonaPlayer returns `list[str]` with realistic inter-message delays (not just rapid-fire)
   - Test runner follows patterns for orchestration

2. **System Layer (Already Exists - MessageBuffer)**:
   - MessageBuffer already handles timing-based batching (debounce)
   - System waits for silence (timeout) before processing batch
   - Agent can naturally respond with multiple messages to any input

The tests validate that the timing-based system correctly batches messages regardless of arrival patterns.

## Relevant Files

Use these files to complete the task:

### Core Files to Modify

- **`src/sales_agent/testing/conversation_simulator.py`** (Lines 91-218)
  - PersonaPlayer class needs `generate_multi_response()` method
  - PersonaDefinition model needs multi-message configuration (probability, max count up to 5)

- **`src/sales_agent/testing/stress_scenarios.py`** (Lines 36-82, 108-386)
  - StressConfig model already has `conversation_pattern` field (unused)
  - Need to add inter-message delay configuration for realistic pauses (up to 1-2 minutes)
  - Scenarios need updated patterns for realistic testing

- **`src/sales_agent/testing/stress_test_runner.py`** (Lines 504-618, 747-952)
  - `run_mock_stress_test()` main loop needs pattern-driven flow for TEST orchestration
  - `_run_conversation()` method needs same pattern support
  - Must respect MessageBuffer timing for SYSTEM behavior validation

### Supporting Files

- **`src/sales_agent/testing/mock_telegram_daemon.py`** (Lines 337-454)
  - May need updates for collecting multiple agent responses naturally
  - Agent can send multiple messages in response to any input (not pattern-driven)
  - `simulate_incoming_message()` already supports messages with timing

- **`src/sales_agent/testing/e2e_telegram_player.py`** (Lines 372-440)
  - Already has `send_batch()` for multi-message sending
  - No changes needed, just used by updated runner

- **`src/sales_agent/messaging/message_buffer.py`** (Lines 53-113)
  - Reference for understanding TIMING-BASED batching (debounce)
  - No changes needed - this IS the system's detection mechanism
  - Tests validate this timing-based approach works correctly

### New Files

- **`src/sales_agent/testing/message_splitter.py`** (NEW)
  - Utility to intelligently split responses into multiple messages
  - Handles sentence boundaries, natural breaks

## Implementation Phases

### Phase 1: Foundation - PersonaPlayer Multi-Message Support

Extend PersonaPlayer to optionally return multiple messages (up to 5), simulating realistic human behavior where people send several messages with variable pauses between them (from seconds to 1-2 minutes).

### Phase 2: Core Implementation - Test Orchestration with Patterns

Add pattern-driven test orchestration that controls WHEN messages are sent during tests. The pattern (e.g., C-C-C-A) tells the test runner to send 3 client messages then wait for agent response. The SYSTEM still uses timing-based detection (MessageBuffer) - the pattern is only for test control.

### Phase 3: Agent Multi-Message Support

Enable the agent to naturally respond with multiple messages when appropriate. The agent decides based on content (long answer, follow-up clarification) - not based on any pattern. Tests should collect multiple agent responses within a time window.

### Phase 4: Integration & Polish

Update stress scenarios with realistic patterns and timing, add tests, and ensure backward compatibility with existing tests.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom.

### 1. Add Multi-Message Configuration Fields to PersonaDefinition

- Edit `src/sales_agent/testing/conversation_simulator.py`
- Add new fields to `PersonaDefinition` class after line 43:
  ```python
  multi_message_probability: float = 0.3  # Probability of sending multiple messages (0.0-1.0)
  max_messages_per_turn: int = 5  # Maximum messages when sending burst (up to 5)
  ```
- These fields configure per-persona multi-message behavior
- No traits - just simple probability-based behavior

### 2. Add Inter-Message Delay Configuration to StressConfig

- Edit `src/sales_agent/testing/stress_scenarios.py`
- Add new field to `StressConfig` class after `message_delays` (around line 65):
  ```python
  inter_message_delays: list[tuple[float, float]] = Field(
      default=[(0.5, 3.0)],
      description="Delay ranges between messages in a burst (seconds). Can be up to 1-2 minutes for realistic pauses."
  )
  ```
- This allows realistic pauses BETWEEN burst messages (not just rapid-fire)
- Example: `[(1.0, 5.0), (30.0, 120.0)]` means first pause is 1-5s, second pause is 30s-2min

### 3. Create Message Splitter Utility

- Create new file `src/sales_agent/testing/message_splitter.py`
- Implement `split_response_naturally(text: str, max_parts: int = 5) -> list[str]`
- Split by sentence boundaries (`.`, `!`, `?`)
- Preserve natural message breaks
- Handle edge cases: URLs, abbreviations (e.g., "т.е."), numbered lists
- Return list of 1-5 message parts

### 4. Add generate_multi_response Method to PersonaPlayer

- Edit `src/sales_agent/testing/conversation_simulator.py`
- Add new method after `generate_response()` (after line 168):
  ```python
  async def generate_multi_response(
      self,
      agent_message: str,
      conversation_history: list[ConversationTurn],
      force_multi: bool = False
  ) -> list[str]:
      """
      Generate one or more persona responses as separate messages.

      Simulates realistic user behavior where people often send multiple
      short messages instead of one long message.

      Returns:
          List of 1-5 message strings to be sent with pauses between them.
      """
  ```
- Check `self.persona.multi_message_probability` for random triggering
- Use Agent SDK with modified prompt instructing JSON array output format
- Parse JSON array response with fallback to single message
- Cap at `self.persona.max_messages_per_turn` (max 5)

### 5. Add Message Pattern Field to StressConfig

- Edit `src/sales_agent/testing/stress_scenarios.py`
- Add new field to `StressConfig` class after `conversation_pattern` (after line 81):
  ```python
  message_pattern: list[tuple[str, int]] | None = Field(
      default=None,
      description="""
      TEST ORCHESTRATION pattern as list of (speaker, count) tuples.
      Example: [('C', 3), ('A', 1), ('C', 2)] means:
      - Test sends 3 client messages (with inter_message_delays between them)
      - Test waits for agent response (system uses timing to batch)
      - Test sends 2 more client messages

      Note: This controls TEST behavior. The SYSTEM still uses timing-based
      detection (MessageBuffer debounce) to determine when client is done.
      """
  )
  ```

### 6. Create Test Pattern Iterator Helper Class

- Edit `src/sales_agent/testing/stress_test_runner.py`
- Add new class before `StressTestRunner` (around line 160):
  ```python
  class TestPatternIterator:
      """
      Iterates through test orchestration pattern.

      This controls WHEN the test sends messages, NOT how the system
      detects message completion (that's timing-based via MessageBuffer).
      """
      def __init__(self, pattern: list[tuple[str, int]] | None):
          self.pattern = pattern or [("C", 1), ("A", 1)]  # Default alternating
          self.index = 0
          self.remaining = 0

      def current(self) -> tuple[str, int]:
          """Get current speaker and message count for this step."""
          ...

      def advance(self):
          """Move to next step in pattern."""
          ...

      def reset(self):
          """Reset iterator to beginning of pattern."""
          ...
  ```

### 7. Refactor run_mock_stress_test Main Loop

- Edit `src/sales_agent/testing/stress_test_runner.py`
- Modify main loop in `run_mock_stress_test()` (lines 504-618)
- Replace `if last_turn.speaker == "agent"` logic with pattern-driven TEST control:
  ```python
  # Initialize test pattern iterator (controls TEST orchestration)
  pattern = TestPatternIterator(stress_config.message_pattern)

  while turn_counter < self.max_turns * 2:
      current_speaker, message_count = pattern.current()

      if current_speaker == "C":
          # TEST: Generate and send client messages with realistic delays
          messages = await persona_player.generate_multi_response(...)
          messages = messages[:message_count]  # Cap at pattern count

          for i, msg in enumerate(messages):
              await daemon.simulate_incoming_message(msg)
              turns.append(...)

              # Add realistic inter-message delay (can be up to 1-2 minutes)
              if i < len(messages) - 1:
                  delay_range = stress_config.inter_message_delays[i % len(stress_config.inter_message_delays)]
                  delay = random.uniform(*delay_range)
                  await asyncio.sleep(delay)

          # SYSTEM: MessageBuffer uses timing to detect "done"
          # We just wait for the debounce timeout to expire

      elif current_speaker == "A":
          # Wait for agent response(s)
          # Agent may naturally send multiple messages - collect them
          responses = await daemon.wait_for_responses(
              expected_count=message_count,
              collection_window=10.0  # Collect multiple responses within window
          )
          for response in responses:
              turns.append(...)

      pattern.advance()
  ```

### 8. Add Agent Multi-Response Collection to MockTelegramDaemon

- Edit `src/sales_agent/testing/mock_telegram_daemon.py`
- Add method `wait_for_responses()` (plural):
  ```python
  async def wait_for_responses(
      self,
      expected_count: int = 1,
      timeout: float = 60.0,
      collection_window: float = 10.0
  ) -> list[str]:
      """
      Wait for agent responses, collecting multiple if they arrive.

      The agent naturally decides when to send multiple messages
      (e.g., long answer split into parts, follow-up clarification).
      This is NOT pattern-driven - agent decides based on content.

      Args:
          expected_count: Hint for how many to expect (test orchestration)
          timeout: Max wait for first response
          collection_window: After first response, wait this long for more

      Returns:
          List of response strings (1 or more)
      """
  ```
- This allows the AGENT to naturally send multiple messages when appropriate
- Agent decides based on content, not based on any pattern

### 9. Refactor _run_conversation for Real Telegram Mode

- Edit `src/sales_agent/testing/stress_test_runner.py`
- Apply same pattern-driven TEST logic to `_run_conversation()` (lines 747-952)
- Use `player.send_batch()` with realistic inter-message delays
- Implement multi-response collection for agent (agent decides naturally)

### 10. Update Stress Scenarios with Realistic Patterns and Timing

- Edit `src/sales_agent/testing/stress_scenarios.py`
- Update "Rapid Fire Burst" scenario (lines 113-147):
  ```python
  stress_config=StressConfig(
      message_pattern=[("C", 3), ("A", 1), ("C", 2), ("A", 1)],
      inter_message_delays=[(0.5, 2.0), (1.0, 5.0)],  # Short pauses for "rapid"
      # ... existing config
  )
  ```
- Update "Interruption Pattern" scenario (lines 345-385):
  ```python
  stress_config=StressConfig(
      message_pattern=[("C", 1), ("C", 2), ("A", 1), ("C", 1), ("A", 2)],
      inter_message_delays=[(2.0, 10.0), (30.0, 90.0)],  # Mix of short and long pauses
      # ... existing config
  )
  ```
- Add new scenario "Realistic Multi-Message" with pauses up to 1-2 minutes:
  ```python
  StressScenario(
      name="Realistic Multi-Message",
      stress_config=StressConfig(
          message_pattern=[("C", 3), ("A", 2), ("C", 2), ("A", 1)],
          inter_message_delays=[(5.0, 30.0), (30.0, 120.0)],  # Up to 2 min pauses
      ),
      # ...
  )
  ```

### 11. Update PersonaDefinition in Stress Scenarios

- Edit `src/sales_agent/testing/stress_scenarios.py`
- Add multi-message fields to personas:
  ```python
  persona=PersonaDefinition(
      name="Быстрый Инвестор",
      # ... existing fields
      multi_message_probability=0.8,  # High probability of multi-message
      max_messages_per_turn=5,  # Can send up to 5 messages
  )
  ```
- Update other personas with appropriate probability values

### 12. Update Test Exports

- Edit `src/sales_agent/testing/__init__.py`
- Add new exports:
  ```python
  from .message_splitter import split_response_naturally
  from .stress_test_runner import TestPatternIterator
  ```

### 13. Validate Implementation with Self-Test

- Add self-test to `src/sales_agent/testing/message_splitter.py`
- Add self-test cases to `src/sales_agent/testing/stress_scenarios.py` to verify pattern parsing
- Ensure `if __name__ == "__main__"` blocks test the new functionality

## Testing Strategy

### Unit Tests

1. **message_splitter.py tests:**
   - Test sentence splitting with periods, exclamation marks, question marks
   - Test handling of abbreviations ("т.е.", "и т.д.")
   - Test URL preservation (don't split URLs)
   - Test empty/whitespace-only input
   - Test max 5 parts limit

2. **TestPatternIterator tests:**
   - Test default alternating pattern when None provided
   - Test cycling through pattern
   - Test reset functionality
   - Test pattern with various counts

3. **PersonaPlayer.generate_multi_response tests:**
   - Test probability-based triggering
   - Test JSON array parsing
   - Test fallback to single message on parse failure
   - Test max_messages_per_turn capping at 5

### Integration Tests

1. **Timing-Based Batching Tests (System Behavior):**
   - Test sending 3 messages with short delays (1-5s) triggers MessageBuffer batch
   - Test sending 3 messages with long delays (30-120s) may trigger multiple batches
   - Test agent receives aggregated message with timestamps when messages are batched
   - Verify MessageBuffer debounce timeout determines batching, NOT message count

2. **Agent Multi-Message Response Tests:**
   - Test agent can naturally send 2-3 messages in response to single input
   - Test `wait_for_responses()` collects multiple agent messages within window
   - Verify agent decides to multi-message based on CONTENT, not pattern

3. **Stress test with patterns:**
   - Run "Rapid Fire Burst" with pattern `[("C", 3), ("A", 1)]` and short delays
   - Verify 3 client messages are batched by MessageBuffer (timing-based)
   - Verify agent response addresses all 3 topics
   - Run "Realistic Multi-Message" with long pauses (up to 2 minutes)

### Backward Compatibility Tests

1. **Test existing scenarios without patterns:**
   - All 6 existing stress scenarios should work unchanged
   - `message_pattern=None` should default to alternating pattern
   - No regressions in existing test flow

## Acceptance Criteria

- [ ] PersonaPlayer can return `list[str]` (1-5 messages) via `generate_multi_response()`
- [ ] StressConfig `message_pattern` field controls TEST orchestration flow
- [ ] StressConfig `inter_message_delays` supports pauses up to 1-2 minutes between burst messages
- [ ] Stress tests execute with patterns like `[("C", 3), ("A", 1), ("C", 2)]`
- [ ] MessageBuffer properly batches client messages based on TIMING (debounce), not message count
- [ ] Agent can naturally send multiple messages - `wait_for_responses()` collects them
- [ ] Agent multi-message is content-driven (agent decides), not pattern-driven
- [ ] All existing stress tests pass without modification (backward compatible)
- [ ] At least 2 stress scenarios use multi-message patterns with realistic timing
- [ ] New "Realistic Multi-Message" scenario tests pauses up to 2 minutes
- [ ] Self-tests pass in all modified modules

## Validation Commands

Execute these commands to validate the task is complete:

- `uv run python -m py_compile src/sales_agent/testing/message_splitter.py` - Verify new module compiles
- `uv run python -m py_compile src/sales_agent/testing/conversation_simulator.py` - Verify PersonaPlayer changes compile
- `uv run python -m py_compile src/sales_agent/testing/stress_scenarios.py` - Verify StressConfig changes compile
- `uv run python -m py_compile src/sales_agent/testing/stress_test_runner.py` - Verify runner changes compile
- `PYTHONPATH=src uv run python src/sales_agent/testing/message_splitter.py` - Run message_splitter self-test
- `PYTHONPATH=src uv run python src/sales_agent/testing/stress_scenarios.py` - Run stress_scenarios self-test
- `PYTHONPATH=src uv run python src/sales_agent/testing/stress_test_runner.py` - Run stress_test_runner self-test
- `PYTHONPATH=src uv run python -c "from sales_agent.testing import split_response_naturally; print('Import OK')"` - Verify exports

## Notes

### Design Decisions

1. **Timing vs Patterns - Two Layers**:
   - **SYSTEM layer**: Uses TIMING-based detection. MessageBuffer debounce determines when user is "done" sending messages. The system doesn't know or care about patterns.
   - **TEST layer**: Uses PATTERNS for orchestration. The test decides when to send messages. The pattern `[("C", 3), ("A", 1)]` tells the test to send 3 messages, but the SYSTEM still batches based on timing.

2. **Realistic Inter-Message Delays**: Burst messages aren't always rapid-fire. Real users might send message 1, wait 30 seconds, send message 2, wait 2 minutes, send message 3. The `inter_message_delays` config supports pauses up to 1-2 minutes.

3. **Max 5 Messages Per Turn**: Realistic cap at 5 messages per turn. People rarely send more than 5 consecutive messages without waiting for a response.

4. **Agent Multi-Message is Content-Driven**: The agent decides to send multiple messages based on CONTENT (long answer, follow-up clarification), NOT based on any pattern. Tests collect agent responses within a time window.

5. **Backward Compatibility**: The `message_pattern` field defaults to `None`, which triggers alternating behavior. Existing tests work unchanged.

6. **JSON Array Output for Multi-Messages**: When PersonaPlayer generates bursts, it instructs the LLM to output a JSON array like `["Message 1", "Message 2"]`. This ensures semantic coherence vs. artificial sentence splitting.

7. **No Traits**: Multi-message behavior is simple probability-based, not trait-based. Just `multi_message_probability` and `max_messages_per_turn`.

### Key Insight: System vs Test Responsibility

| Aspect | SYSTEM (Production) | TEST (Orchestration) |
|--------|---------------------|----------------------|
| Detects message completion | Timing (MessageBuffer debounce) | Pattern tells when to send |
| Decides agent multi-message | Content-based (agent decides) | Collects within time window |
| Handles pauses | Natural debounce timeout | Configured `inter_message_delays` |

### Dependencies

- No new external packages required
- Uses existing Anthropic Agent SDK for LLM calls
- Uses existing MessageBuffer for batching validation (timing-based)

### Performance Considerations

- Multi-message generation adds one LLM call with modified prompt
- Pattern iteration is O(1) per step
- Message splitting is O(n) in message length
- Test duration may increase significantly with realistic pauses (up to 1-2 minutes between messages)
- Consider adding a "fast mode" for CI that uses shorter delays
