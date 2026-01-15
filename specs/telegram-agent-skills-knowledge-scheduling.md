# Plan: Telegram Agent Skills Integration & Zoom Scheduling

## Task Description

Enhance the Telegram bot agent to:
1. **Always load and use BOTH communication skills** (`tone-of-voice` and `how-to-communicate`) during all client interactions
2. **Integrate knowledge_base_final context** into conversations - always search and consider this knowledge when responding
3. **Create mock sales slots system** and implement a tool/action for booking Zoom appointments based on available times

## Objective

When complete, the Telegram agent will:
- Communicate using both the HOW (tone-of-voice) and WHAT (how-to-communicate) methodologies
- Have factual knowledge about Bali real estate from the knowledge base to answer client questions accurately
- Be able to check available sales slots and book Zoom meetings when clients are ready

## Problem Statement

Currently the `TelegramAgent` class in `telegram_agent.py`:
1. Only loads `tone-of-voice` skill (line 56) but NOT `how-to-communicate`
2. Has NO integration with `knowledge_base_final/` - cannot answer factual questions about Bali real estate
3. Has NO scheduling capability - cannot check availability or book Zoom calls

This limits the agent's ability to qualify leads effectively (missing methodology) and provide accurate information (missing knowledge base).

## Solution Approach

**Three-pronged approach:**

1. **Skill Loading Enhancement**: Extend `TelegramAgent` to load both skills, with configurable skill paths
2. **Knowledge Base Integration**: Add selective knowledge loading based on conversation topic detection
3. **Scheduling System**: Create `SalesCalendar` model with mock slots + `SchedulingTool` for booking

## Relevant Files

### Existing Files to Modify

- **`.claude/skills/telegram/scripts/telegram_agent.py`** (Lines 24-97)
  - Primary file to extend with additional skill loading and knowledge integration
  - `_load_tone_of_voice()` method will be generalized to `_load_skill()`
  - `_build_system_prompt()` will include knowledge base context

- **`.claude/skills/telegram/scripts/models.py`** (Lines 1-65)
  - Add `SalesSlot`, `SalesCalendar`, and `SchedulingResult` Pydantic models
  - Extend `AgentAction` to include scheduling actions
  - Add `AgentConfig` fields for skill paths and scheduling

- **`.claude/skills/telegram/scripts/run_daemon.py`**
  - Update initialization to pass both skill paths to agent
  - Add scheduling tool integration into message handling

- **`.claude/skills/telegram/config/agent_config.json`**
  - Add configuration for skill paths and scheduling settings

### New Files to Create

- **`.claude/skills/telegram/scripts/knowledge_loader.py`**
  - Knowledge base loader with topic detection and selective loading
  - Methods: `detect_topic()`, `load_relevant_knowledge()`, `get_master_cheatsheet()`

- **`.claude/skills/telegram/scripts/sales_calendar.py`**
  - Sales calendar management with mock slot generation
  - Methods: `get_available_slots()`, `book_slot()`, `cancel_booking()`

- **`.claude/skills/telegram/scripts/scheduling_tool.py`**
  - LLM tool interface for scheduling Zoom meetings
  - Integrates with existing Zoom API client

- **`.claude/skills/telegram/config/sales_slots.json`**
  - Mock sales availability data (working hours, blocked times, booked meetings)

### Reference Files (Read-Only Context)

- **`.claude/skills/tone-of-voice/SKILL.md`** - Communication style principles
- **`.claude/skills/how-to-communicate/SKILL.md`** - Sales methodology (BANT, Snake)
- **`knowledge_base_final/00_MASTER_CHEATSHEET.md`** - Compressed knowledge overview
- **`knowledge_base_final/01-11_*.md`** - Detailed topic files
- **`.claude/skills/zoom/scripts/zoom_meetings.py`** - Existing Zoom API client

## Implementation Phases

### Phase 1: Foundation (Skill Loading & Configuration)

Establish the infrastructure for loading multiple skills and configuring the agent.

**Goals:**
- Generalize skill loading mechanism
- Update configuration model
- Ensure backward compatibility

### Phase 2: Core Implementation (Knowledge Base + Skills Integration)

Implement the knowledge base loader and integrate both skills into the system prompt.

**Goals:**
- Topic detection from conversation
- Selective knowledge loading (stay within token limits)
- Dual-skill system prompt construction

### Phase 3: Scheduling System

Create the sales calendar model, mock data, and scheduling tool.

**Goals:**
- Pydantic models for slots and bookings
- Mock slot generation (weekdays 10:00-19:00 UTC+8)
- Tool interface for LLM to query and book

### Phase 4: Integration & Polish

Connect all components and test end-to-end flow.

**Goals:**
- Update daemon to use all new components
- Add scheduling action to response flow
- Test complete qualification → booking flow

## Step by Step Tasks

### 1. Extend Agent Configuration Model

- In `models.py`, add new fields to `AgentConfig`:
  ```python
  tone_of_voice_path: Optional[Path] = None
  how_to_communicate_path: Optional[Path] = None
  knowledge_base_path: Optional[Path] = None
  sales_calendar_path: Optional[Path] = None
  include_knowledge_base: bool = True
  max_knowledge_tokens: int = 4000  # Token limit for KB context
  ```
- Add `SalesSlot` model:
  ```python
  class SalesSlot(BaseModel):
      id: str
      date: date
      start_time: time
      end_time: time
      salesperson: str = "Expert"
      is_available: bool = True
      booked_by: Optional[str] = None  # prospect telegram_id
  ```
- Add `SchedulingResult` model for tool responses

### 2. Create Knowledge Loader Module

- Create `knowledge_loader.py` with class `KnowledgeLoader`:
  - `__init__(self, knowledge_base_path: Path)`
  - `detect_topic(message: str) -> list[str]` - Returns relevant topic IDs (01, 02, etc.)
  - `load_master_cheatsheet() -> str` - Always-available compressed context
  - `load_topic(topic_id: str) -> str` - Load specific topic file
  - `get_relevant_context(message: str, max_tokens: int) -> str` - Main method
- Topic detection keywords mapping:
  ```python
  TOPIC_KEYWORDS = {
      "01": ["geography", "район", "локация", "чангу", "убуд", "семиньяк", "букит"],
      "02": ["legal", "leasehold", "freehold", "закон", "право", "собственность"],
      "03": ["tax", "налог", "ндфл", "налогообложение"],
      "04": ["financial", "доходность", "roi", "инвестиц", "окупаемость"],
      "05": ["sales", "преимущество", "usp", "почему мы"],
      "06": ["market", "рынок", "тренд", "цен"],
  }
  ```

### 3. Generalize Skill Loading in TelegramAgent

- Rename `_load_tone_of_voice()` to `_load_skill(skill_path: Path) -> str`
- Add new method `_load_all_skills() -> str` that loads both:
  - tone-of-voice (HOW to communicate)
  - how-to-communicate (WHAT to communicate)
- Update `__init__` to accept both skill paths:
  ```python
  def __init__(
      self,
      tone_of_voice_path: str | Path,
      how_to_communicate_path: str | Path = None,
      knowledge_base_path: str | Path = None,
      config: Optional[AgentConfig] = None,
      agent_name: str = "Мария"
  ):
  ```

### 4. Integrate Knowledge Base into System Prompt

- Modify `_build_system_prompt()` to include:
  1. Base agent instructions (existing)
  2. Tone of voice skill content
  3. How to communicate skill content
  4. Master cheatsheet from knowledge base (always loaded)
- Add dynamic knowledge injection in `generate_response()`:
  - Detect topic from incoming message
  - Load relevant knowledge section
  - Include in user prompt context

### 5. Create Sales Calendar Module

- Create `sales_calendar.py` with class `SalesCalendar`:
  - `__init__(self, config_path: Path)`
  - `generate_mock_slots(days_ahead: int = 7) -> list[SalesSlot]`
  - `get_available_slots(from_date: date = None) -> list[SalesSlot]`
  - `book_slot(slot_id: str, prospect_id: str) -> SchedulingResult`
  - `cancel_booking(slot_id: str) -> SchedulingResult`
  - `_load_slots()` and `_save_slots()` for JSON persistence
- Mock slot generation logic:
  - Weekdays only (Monday-Friday)
  - Hours: 10:00, 11:00, 14:00, 15:00, 16:00, 17:00, 18:00 (UTC+8 Bali time)
  - Random availability (70% available, 30% pre-booked)
  - 7 days ahead rolling window

### 6. Create Scheduling Tool Interface

- Create `scheduling_tool.py` with class `SchedulingTool`:
  - `__init__(self, calendar: SalesCalendar, zoom_api_path: Path)`
  - `get_available_times(preferred_date: Optional[date] = None) -> str`
  - `book_zoom_call(slot_id: str, prospect: Prospect, topic: str) -> SchedulingResult`
- Integration with Zoom API:
  - Use existing `zoom_meetings.py` `cmd_create` pattern
  - Set meeting topic based on prospect context
  - Return join URL in result

### 7. Extend AgentAction for Scheduling

- In `models.py`, extend `AgentAction`:
  ```python
  class AgentAction(BaseModel):
      action: Literal["reply", "wait", "escalate", "schedule", "check_availability"]
      message: Optional[str] = None
      reason: Optional[str] = None
      scheduling_data: Optional[dict] = None  # For scheduling actions
  ```
- Update response parsing in `telegram_agent.py` to handle new actions

### 8. Update System Prompt for Scheduling Capability

- Add scheduling instructions to system prompt:
  ```
  ## Назначение Zoom-звонка
  Когда клиент готов к звонку или подобрали BANT:
  - Предложи конкретные слоты: "Завтра в 14:00 или 16:00?"
  - Используй action="check_availability" чтобы проверить свободные слоты
  - Используй action="schedule" с slot_id когда клиент выбрал время
  ```

### 9. Update Run Daemon for Full Integration

- In `run_daemon.py`, update `TelegramDaemon.__init__`:
  - Initialize `KnowledgeLoader` with knowledge_base_path
  - Initialize `SalesCalendar` with slots config path
  - Initialize `SchedulingTool` with calendar and zoom path
  - Pass all to `TelegramAgent`
- Update `handle_incoming()` to handle new actions:
  - `check_availability`: Query calendar, include slots in next prompt
  - `schedule`: Book slot, create Zoom meeting, update prospect status

### 10. Create Mock Sales Slots Configuration

- Create `sales_slots.json`:
  ```json
  {
    "salesperson": "Эксперт True Real Estate",
    "timezone": "Asia/Makassar",
    "working_hours": {"start": "10:00", "end": "19:00"},
    "slot_duration_minutes": 30,
    "break_between_slots_minutes": 15,
    "days_ahead": 7,
    "blocked_dates": [],
    "pre_booked": []
  }
  ```

### 11. Validate and Test End-to-End Flow

- Create test script `test_integration.py`:
  - Test skill loading (both skills present in prompt)
  - Test knowledge detection and loading
  - Test slot availability query
  - Test booking flow (slot → Zoom meeting)
  - Test full conversation: inquiry → qualification → booking

## Testing Strategy

### Unit Tests

1. **Knowledge Loader Tests**
   - `test_topic_detection()` - Verify correct topics detected from messages
   - `test_load_master_cheatsheet()` - Verify file loading
   - `test_max_tokens_respected()` - Verify token limits work

2. **Sales Calendar Tests**
   - `test_mock_slot_generation()` - Verify slots generated correctly
   - `test_booking_flow()` - Verify slot becomes unavailable after booking
   - `test_cancellation()` - Verify slot becomes available after cancel

3. **Agent Integration Tests**
   - `test_dual_skill_loading()` - Both skills in system prompt
   - `test_knowledge_in_response()` - Facts appear in responses
   - `test_scheduling_action_parsing()` - New actions parsed correctly

### Integration Tests

1. **Full Conversation Flow**
   ```
   [Client] Привет, интересуюсь виллой
   [Agent] (uses tone-of-voice + how-to-communicate + geography knowledge)

   [Client] Какая доходность?
   [Agent] (loads 04_FINANCIAL_MODEL_ANALYSIS, provides factual answer)

   [Client] Хочу созвониться
   [Agent] (action=check_availability, offers specific times)

   [Client] Давайте завтра в 14:00
   [Agent] (action=schedule, creates Zoom, confirms)
   ```

### Edge Cases

- Empty knowledge base files
- No available slots
- Zoom API failure (graceful degradation)
- Token limit exceeded (truncation)
- Unknown topic (fallback to master cheatsheet)

## Acceptance Criteria

1. **Skills Integration**
   - [ ] `telegram_agent.py` loads BOTH tone-of-voice AND how-to-communicate skills
   - [ ] System prompt contains content from both skills
   - [ ] Agent responses follow both communication style AND methodology

2. **Knowledge Base Integration**
   - [ ] Master cheatsheet always loaded in system prompt
   - [ ] Topic-specific knowledge loaded based on message content
   - [ ] Agent can answer factual questions about Bali real estate

3. **Scheduling System**
   - [ ] `SalesCalendar` generates realistic mock slots
   - [ ] Agent can check availability via `action=check_availability`
   - [ ] Agent can book slots via `action=schedule`
   - [ ] Booking creates actual Zoom meeting (or mock in test mode)
   - [ ] Prospect status updated to `ZOOM_SCHEDULED` after booking

4. **Configuration**
   - [ ] All new paths configurable via `agent_config.json`
   - [ ] Backward compatible (existing configs still work)
   - [ ] Token limits respected for knowledge loading

## Validation Commands

Execute these commands to validate the task is complete:

```bash
# 1. Verify Python syntax
uv run python -m py_compile .claude/skills/telegram/scripts/telegram_agent.py
uv run python -m py_compile .claude/skills/telegram/scripts/models.py
uv run python -m py_compile .claude/skills/telegram/scripts/knowledge_loader.py
uv run python -m py_compile .claude/skills/telegram/scripts/sales_calendar.py
uv run python -m py_compile .claude/skills/telegram/scripts/scheduling_tool.py

# 2. Run unit tests
uv run pytest .claude/skills/telegram/tests/ -v

# 3. Test agent initialization (loads both skills)
uv run python -c "
from pathlib import Path
import sys
sys.path.insert(0, str(Path('.claude/skills/telegram/scripts')))
from telegram_agent import TelegramAgent

agent = TelegramAgent(
    tone_of_voice_path=Path('.claude/skills/tone-of-voice'),
    how_to_communicate_path=Path('.claude/skills/how-to-communicate'),
    knowledge_base_path=Path('knowledge_base_final')
)
print('✅ Agent initialized with both skills')
assert 'Змейка' in agent.system_prompt or 'BANT' in agent.system_prompt
print('✅ How-to-communicate content present')
"

# 4. Test knowledge loader
uv run python -c "
from pathlib import Path
import sys
sys.path.insert(0, str(Path('.claude/skills/telegram/scripts')))
from knowledge_loader import KnowledgeLoader

loader = KnowledgeLoader(Path('knowledge_base_final'))
context = loader.get_relevant_context('Какая доходность у вилл в Чангу?', max_tokens=2000)
print('✅ Knowledge loader works')
print(f'Context length: {len(context)} chars')
"

# 5. Test sales calendar
uv run python -c "
from pathlib import Path
import sys
sys.path.insert(0, str(Path('.claude/skills/telegram/scripts')))
from sales_calendar import SalesCalendar

calendar = SalesCalendar(Path('.claude/skills/telegram/config/sales_slots.json'))
slots = calendar.get_available_slots()
print(f'✅ Found {len(slots)} available slots')
"
```

## Notes

### Dependencies

Add to project if not present:
```bash
uv add tiktoken  # For token counting in knowledge loader
```

### Token Management

The knowledge base totals ~50k tokens across all files. Strategy:
- Master cheatsheet (~2k tokens): Always loaded
- Topic files (~3-8k each): Loaded on-demand based on detection
- Max context budget: 4000 tokens for knowledge (configurable)

### Zoom Integration

The scheduling tool will use the existing Zoom API client at `.claude/skills/zoom/scripts/zoom_meetings.py`. Ensure `~/.zoom_credentials/credentials.json` is configured before testing the full booking flow.

### Future Enhancements

1. **Real Calendar Integration**: Replace mock slots with Google Calendar or Calendly API
2. **RAG Implementation**: Add vector search for semantic knowledge retrieval
3. **Multi-Salesperson**: Support multiple sales team members with their own calendars
4. **Timezone Handling**: Auto-detect client timezone for slot presentation
