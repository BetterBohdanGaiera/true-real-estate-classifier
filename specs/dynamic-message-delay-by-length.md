# Plan: Dynamic Message Delay Based on Message Length

## Task Description
Modify the Telegram service to implement dynamic pauses before sending messages, where the delay duration scales based on message length. Currently, the system uses a static delay range (2-5 seconds) regardless of message content. The enhancement will create more human-like behavior by using shorter delays for brief messages and longer delays for lengthy messages.

## Objective
Implement a three-tier delay system based on message character count:
- **Short messages** (<50 characters): 1-2 seconds delay
- **Medium messages** (50-200 characters): 3-5 seconds delay
- **Long messages** (>200 characters): 5-10 seconds delay

Additionally, update `agent_config.json` with configurable parameters for these delay tiers.

## Problem Statement
The current implementation applies the same random delay (2-5 seconds) to all messages regardless of length. This creates unrealistic behavior because:
- A quick "Got it!" response should have minimal delay (real humans respond faster to short acknowledgments)
- A detailed explanation about investment properties should have a longer delay (real humans take more time to compose thoughtful responses)
- The current typing simulation already scales with message length (1-5 seconds based on chars/20), but the "thinking" delay before typing doesn't scale

## Solution Approach
Replace the static `response_delay_range` with a message-length-aware delay calculation function. The delay tiers will be configurable through new fields in `AgentConfig`, allowing runtime tuning without code changes. The solution maintains backward compatibility by keeping `response_delay_range` as a fallback.

## Relevant Files
Use these files to complete the task:

- **`src/sales_agent/telegram/telegram_service.py`** (lines 35-72, 73-92)
  - Contains `send_message()` method with current static delay logic (lines 53-55)
  - Contains `_simulate_typing()` method that already uses message length (lines 73-92)
  - Primary modification target for dynamic delay implementation

- **`src/sales_agent/crm/models.py`** (lines 95-119)
  - Contains `AgentConfig` Pydantic model with `response_delay_range` field (line 101)
  - Needs new fields for length-based delay configuration

- **`src/sales_agent/config/agent_config.json`** (lines 1-27)
  - Runtime configuration file loaded by daemon
  - Needs new delay parameters: `delay_short`, `delay_medium`, `delay_long`

### New Files
None required - all changes are to existing files.

## Implementation Phases

### Phase 1: Foundation
Add new configuration fields to the Pydantic model and JSON config file. Ensure backward compatibility with existing configurations.

### Phase 2: Core Implementation
Implement the delay calculation logic in `telegram_service.py` that selects the appropriate delay tier based on message length.

### Phase 3: Integration & Polish
Test the implementation, verify backward compatibility, and ensure logging captures delay decisions for debugging.

## Step by Step Tasks
IMPORTANT: Execute every step in order, top to bottom.

### 1. Add Configuration Fields to AgentConfig Model
- Open `src/sales_agent/crm/models.py`
- Add new fields after `response_delay_range` (around line 101):
  ```python
  # Length-based delay configuration (seconds)
  delay_short: tuple[float, float] = (1.0, 2.0)  # <50 chars
  delay_medium: tuple[float, float] = (3.0, 5.0)  # 50-200 chars
  delay_long: tuple[float, float] = (5.0, 10.0)  # >200 chars
  ```
- These are tuples representing (min_seconds, max_seconds) ranges for random selection
- Default values match the requirements: short 1-2s, medium 3-5s, long 5-10s

### 2. Update agent_config.json with New Parameters
- Open `src/sales_agent/config/agent_config.json`
- Add new delay parameters after `response_delay_range` (line 6):
  ```json
  "delay_short": [1.0, 2.0],
  "delay_medium": [3.0, 5.0],
  "delay_long": [5.0, 10.0],
  ```
- Keep `response_delay_range` for backward compatibility

### 3. Implement Dynamic Delay Calculation Method
- Open `src/sales_agent/telegram/telegram_service.py`
- Add a new private method `_calculate_delay()` after line 72 (before `_simulate_typing`):
  ```python
  def _calculate_delay(self, text: str) -> float:
      """Calculate response delay based on message length.

      Delay tiers:
      - Short (<50 chars): quick acknowledgments
      - Medium (50-200 chars): standard responses
      - Long (>200 chars): detailed explanations
      """
      text_length = len(text)

      if text_length < 50:
          delay_range = self.config.delay_short
      elif text_length <= 200:
          delay_range = self.config.delay_medium
      else:
          delay_range = self.config.delay_long

      return random.uniform(*delay_range)
  ```

### 4. Update send_message to Use Dynamic Delay
- In `src/sales_agent/telegram/telegram_service.py`
- Replace lines 53-55:
  ```python
  # Human-like delay before sending
  delay = random.uniform(*self.config.response_delay_range)
  await asyncio.sleep(delay)
  ```
- With:
  ```python
  # Human-like delay before sending (scaled by message length)
  delay = self._calculate_delay(text)
  await asyncio.sleep(delay)
  ```

### 5. Validate the Implementation
- Run Python syntax check: `uv run python -m py_compile src/sales_agent/telegram/telegram_service.py`
- Run Python syntax check: `uv run python -m py_compile src/sales_agent/crm/models.py`
- Verify JSON is valid: `uv run python -c "import json; json.load(open('src/sales_agent/config/agent_config.json'))"`
- Test config loading: `uv run python -c "from sales_agent.crm.models import AgentConfig; import json; c = AgentConfig(**json.load(open('src/sales_agent/config/agent_config.json'))); print(f'Short: {c.delay_short}, Medium: {c.delay_medium}, Long: {c.delay_long}')"`

## Testing Strategy

### Unit Tests
1. **Delay calculation boundaries**: Test that messages at boundary lengths (49, 50, 200, 201 chars) trigger correct delay tiers
2. **Configuration override**: Verify custom delay ranges from config override defaults
3. **Backward compatibility**: Ensure old configs without new fields still work (Pydantic defaults)

### Integration Tests
1. **Message sending flow**: Send messages of varying lengths and log actual delays
2. **Full daemon cycle**: Run manual test with different message types

### Edge Cases
- Empty message (0 chars) - should use short delay
- Very long message (>1000 chars) - should use long delay
- Unicode characters (Cyrillic) - `len()` counts characters correctly

## Acceptance Criteria
- [ ] Short messages (<50 chars) use 1-2 second delay range
- [ ] Medium messages (50-200 chars) use 3-5 second delay range
- [ ] Long messages (>200 chars) use 5-10 second delay range
- [ ] Delay tiers are configurable via `agent_config.json`
- [ ] Existing configs without new fields continue to work (backward compatibility)
- [ ] No changes to typing simulation logic (already length-based)
- [ ] Python syntax validation passes
- [ ] JSON config is valid and loadable

## Validation Commands
Execute these commands to validate the task is complete:

- `uv run python -m py_compile src/sales_agent/telegram/telegram_service.py` - Verify telegram_service.py syntax
- `uv run python -m py_compile src/sales_agent/crm/models.py` - Verify models.py syntax
- `uv run python -c "import json; json.load(open('src/sales_agent/config/agent_config.json'))"` - Verify JSON syntax
- `PYTHONPATH=src uv run python -c "from sales_agent.crm.models import AgentConfig; print(AgentConfig().delay_short, AgentConfig().delay_medium, AgentConfig().delay_long)"` - Verify Pydantic defaults
- `PYTHONPATH=src uv run python -c "from sales_agent.telegram.telegram_service import TelegramService; print('Import OK')"` - Verify import works

## Notes

### Backward Compatibility
- The `response_delay_range` field is kept in the model for reference but no longer used in `send_message()`
- If a deployment has an old `agent_config.json` without the new fields, Pydantic defaults will be used
- No migration script needed - additive changes only

### Typing Simulation Interaction
The typing simulation (`_simulate_typing`) already uses message length to calculate duration:
- Formula: `len(text) / 20 chars_per_second`, clamped to 1-5 seconds
- This is **separate** from the response delay and will continue to work unchanged
- Total perceived delay = typing duration + response delay

### Example Total Delays
| Message Length | Typing (1-5s) | Response Delay | Total Range |
|---------------|---------------|----------------|-------------|
| 20 chars | 1.0s | 1-2s | 2-3s |
| 100 chars | 5.0s | 3-5s | 8-10s |
| 300 chars | 5.0s (max) | 5-10s | 10-15s |

### Future Enhancements (Not in Scope)
- Make typing speed configurable (`chars_per_second` is hardcoded at 20)
- Add jitter to avoid predictable patterns
- Log delay decisions for analytics
