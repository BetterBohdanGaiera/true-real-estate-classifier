# Plan: System Architecture Visualization HTML

## Task Description

Create an interactive HTML visualization that illustrates the complete Telegram Sales Agent system architecture for business stakeholders. The visualization should cover:

1. **Local Development Environment** - How developers run and test the system
2. **Production Deployment** - Docker-based multi-service architecture
3. **Testing Mechanisms** - Both manual testing and automated stress/simulation tests
4. **Telegram Classifier/Agent Flow** - Message processing, AI integration, response generation
5. **Special Features** - Wait/follow-up scheduling, message batching, Zoom booking
6. **Integration Points** - PostgreSQL, Google Calendar, Zoom, ElevenLabs
7. **Communication Methodology** - Змейка structure, BANT qualification, and core sales principles that drive the AI agent

The visualization should be presentable to a business representative using clear, non-technical language while accurately representing the system's capabilities.

## Objective

Deliver a single, self-contained HTML file with interactive diagrams that visually explain the entire True Real Estate Telegram Sales Agent system workflow, including the critical communication methodology (Змейка, BANT) that powers the AI agent's responses. Suitable for business stakeholder presentations.

## Problem Statement

The current system is complex with multiple interconnected components (Telegram daemon, AI agent, scheduling, testing, communication methodology, etc.) spread across various skills and scripts. There is no unified visual representation that stakeholders can use to understand:
- How prospects are contacted and managed
- How the AI generates responses using communication methodology (Змейка, BANT)
- How scheduling/wait functionality works
- How testing validates the system
- How production deployment differs from local development
- What communication principles guide the AI agent

## Solution Approach

Create an interactive HTML page that includes:
1. **Main architecture overview** - High-level system diagram
2. **Message flow animation** - Showing the journey of a message from Telegram to AI to response
3. **Communication methodology visualization** - Змейка structure, BANT, 12 principles
4. **Wait/follow-up visualization** - Demonstrating the scheduling system
5. **Environment switcher** - Toggle between Local/Docker/Production views
6. **Interactive components** - Clickable sections that reveal more detail

## Relevant Files

Use these files to understand the system architecture:

### Core Daemon & Agent
- `.claude/skills/telegram/scripts/daemon.py` - Main orchestrator (1224 lines), handles message events, component initialization
- `.claude/skills/telegram/scripts/telegram_agent.py` - Claude AI integration (806 lines), response generation with tool calling
- `.claude/skills/telegram/scripts/telegram_service.py` - Telethon wrapper (355 lines), human-like behavior simulation
- `.claude/skills/telegram/scripts/message_buffer.py` - Message batching (423 lines), debounce logic

### Communication Methodology (CRITICAL)
- `.claude/skills/how-to-communicate/SKILL.md` - Core methodology: 12 principles, Змейка structure, BANT qualification
- `.claude/skills/how-to-communicate/references/методология_змейка_обогащенная.md` - Detailed Змейка (Snake) 4-stage call structure
- `.claude/skills/how-to-communicate/references/методология_bant.md` - BANT lead qualification system
- `.claude/skills/how-to-communicate/references/паттерны_успеха.md` - Success patterns in calls
- `.claude/skills/how-to-communicate/references/антипаттерны.md` - Anti-patterns to avoid
- `.claude/skills/how-to-communicate/references/скрипты_возражения.md` - Objection handling scripts
- `.claude/skills/how-to-communicate/references/классы_лидов.md` - A/B/C lead classification
- `.claude/skills/how-to-communicate/references/чеклист_оценки.md` - Call evaluation checklist
- `.claude/skills/how-to-communicate/references/client_personas.md` - Client persona types

### Tone of Voice
- `.claude/skills/tone-of-voice/SKILL.md` - HOW to communicate (style, tone, 7 principles)

### Scheduling & Follow-ups
- `.claude/skills/telegram/scripts/scheduler_service.py` - APScheduler wrapper (400 lines), delayed action execution
- `.claude/skills/telegram/scripts/scheduled_action_manager.py` - PostgreSQL CRUD (540 lines) for scheduled_actions
- `.claude/skills/telegram/scripts/scheduling_tool.py` - Zoom meeting booking (632 lines), email validation
- `.claude/skills/scheduling/scripts/followup_polling_daemon.py` - Database-driven polling (314 lines)

### State Management
- `.claude/skills/telegram/scripts/prospect_manager.py` - Prospect state management (559 lines)
- `.claude/skills/telegram/scripts/models.py` - Pydantic data models (270 lines)
- `.claude/skills/telegram/config/prospects.json` - Prospect database (JSON)
- `.claude/skills/telegram/config/agent_config.json` - Agent configuration

### Testing Infrastructure
- `.claude/skills/testing/scripts/manual_test.py` - Manual testing entry point (319 lines)
- `.claude/skills/testing/scripts/stress_test_runner.py` - Stress test orchestration (1123 lines)
- `.claude/skills/testing/scripts/mock_telegram_daemon.py` - Production simulation without Telegram (762 lines)
- `.claude/skills/testing/scripts/conversation_simulator.py` - AI persona roleplay (731 lines)
- `.claude/skills/testing/scripts/behavior_tests/run_behavior_tests.py` - Behavior validation (727 lines)
- `.claude/skills/testing/scripts/test_scenarios.py` - 10 challenging persona scenarios
- `.claude/skills/testing/scripts/stress_scenarios.py` - 7 stress test scenarios
- `.claude/skills/testing/scripts/conversation_evaluator.py` - Quality assessment against methodology

### Deployment
- `deployment/docker/docker-compose.yml` - Multi-service orchestration (211 lines)
- `deployment/docker/Dockerfile` - Telegram agent container (111 lines)
- `deployment/docker/Dockerfile.registry` - Registry bot container (95 lines)
- `deployment/docker/Dockerfile.outreach` - Outreach daemon container (95 lines)
- `deployment/systemd/telegram-agent.service` - Linux systemd service (89 lines)

### Integration Skills
- `.claude/skills/google-calendar/SKILL.md` - Calendar event management
- `.claude/skills/zoom/SKILL.md` - Zoom meeting creation
- `.claude/skills/eleven-labs/SKILL.md` - Voice transcription
- `.claude/skills/humanizer/SKILL.md` - Natural timing simulation
- `.claude/skills/database/SKILL.md` - PostgreSQL management

### Configuration
- `.env.example` - Environment variables template (216 lines)
- `.claude/skills/telegram/config/agent_config.json` - Agent behavioral settings

### New Files

- `visualization/system-architecture.html` - Main visualization file (new)

## Implementation Phases

### Phase 1: Foundation
1. Create the HTML structure with responsive layout
2. Set up interactive framework (vanilla JS for simplicity)
3. Design the section structure for all major components

### Phase 2: Core Implementation
1. Build the main architecture overview diagram
2. Create animated message flow visualization
3. **Create communication methodology section** (Змейка, BANT, 12 principles)
4. Implement environment toggle (Local/Docker/Production)
5. Add wait/follow-up scheduling visualization
6. Create testing modes section

### Phase 3: Integration & Polish
1. Add interactive tooltips and detail panels
2. Implement smooth animations and transitions
3. Add Russian language support for business stakeholder
4. Ensure all methodology details are clearly presented

## Step by Step Tasks

### 1. Create Directory Structure
- Create `visualization/` directory in project root
- This will contain the HTML visualization file

### 2. Build HTML Structure
- Create semantic HTML5 structure with sections for each major component
- Include meta tags for proper encoding and viewport
- Structure sections: Overview, Message Flow, Methodology, Scheduling, Testing, Deployment

### 3. Create Main Architecture Overview Section
- Visual diagram showing all components:
  - Telegram Client (Telethon)
  - Message Buffer
  - Telegram Agent (Claude AI)
  - Knowledge Base (Tone of Voice + How to Communicate)
  - Prospect Manager
  - Scheduler Service
  - PostgreSQL Database
  - External APIs (Zoom, Google Calendar, ElevenLabs)
- Use SVG or CSS-based diagram with animated connections

### 4. Build Message Flow Animation
- Animate the journey of an incoming message:
  1. Message arrives via Telegram
  2. Enters Message Buffer (batching)
  3. Passes to Telegram Agent
  4. Claude AI processes with knowledge base (Tone of Voice + Methodology)
  5. Response generated following Змейка structure
  6. Human-like delay applied
  7. Message sent back to prospect
- Use CSS animations with step indicators

### 5. Create Communication Methodology Section (CRITICAL)
- **Змейка (Snake) Structure Visualization:**
  1. Легкий вход (Easy Entry) - establishing contact without pressure
  2. Отражение (Reflection) - reformulating client's words
  3. Экспертность (Expertise) - demonstrating knowledge through facts
  4. Следующий вопрос (Next Question) - moving dialogue forward
  - Show as a snake-like flow diagram

- **BANT Qualification Diagram:**
  - Budget (Бюджет) - purchase budget
  - Authority (Авторитет) - decision maker
  - Need (Потребность) - real need (living/investment)
  - Timeline (Сроки) - purchase timeline
  - Show as 4-quadrant or checklist visual

- **12 Principles Grid:**
  1. Структура "Змейка" - основа звонка
  2. Выяви BANT за первые 5-7 минут
  3. Отражай, не анкетируй
  4. Экспертность через факты, не утверждения
  5. Слушай триггерные точки клиента
  6. Саммари болей -> потом приглашение на зум
  7. Предлагай конкретное время, не "когда удобно"
  8. Не сдавайся на "вышлите каталог"
  9. Не обесценивай клиента
  10. Не отпускай без следующего шага
  11. ВСЕГДА закрывай на Zoom для подбора объектов
  12. НИКОГДА не продавай на выдуманной информации
  13. Відповідай максимально коротко (1-3 речення)

- **Success vs Anti-patterns:**
  - Visual comparison of what works vs what to avoid
  - Include examples from паттерны_успеха.md and антипаттерны.md

- **Call Structure Timeline:**
  ```
  [0-2 мин]  Легкий вход, установление раппорта
  [2-7 мин]  Выяснение BANT через естественный диалог
  [7-12 мин] Отражение болей, демонстрация экспертности
  [12-15 мин] Саммари + приглашение на зум с конкретным временем
  ```

### 6. Create Wait/Follow-up Visualization
- Show how "write in 5 minutes" request flows:
  1. Client message parsed by Claude
  2. `schedule_followup` tool called
  3. Action saved to PostgreSQL
  4. Scheduler service waits
  5. Action executed at scheduled time
  6. Automatic cancellation if client responds first
- Include timeline visualization

### 7. Implement Environment Toggle
- Three modes: Local / Docker / Production
- Each shows different:
  - Components running
  - Configuration sources
  - Database connections
  - Credential locations
- Smooth transition between views

### 8. Add Testing Section
- Visualize testing modes:
  1. **Manual Testing**: Reset prospect, run daemon, interact via real Telegram
  2. **Stress Testing**: 7 scenarios (Rapid Fire, Slow Responder, Urgency, etc.)
  3. **Conversation Simulation**: 10 persona scenarios with AI evaluation
  4. **Behavior Tests**: Specific capability validation (batching, wait, Zoom)
- Show test accounts: @BetterBohdan (agent) and @bohdanpytaichuk (test prospect)
- **Include conversation evaluator metrics** (based on methodology adherence):
  - Overall score (0-100)
  - BANT coverage tracking
  - Zmeyka adherence score
  - Objection handling score

### 9. Create Integration Points Panel
- Expandable cards for each external service:
  - PostgreSQL (scheduled_actions, sales_representatives tables)
  - Google Calendar (OAuth, availability checking)
  - Zoom (Server-to-Server OAuth, meeting creation)
  - ElevenLabs (voice transcription)
- Show connection flows with arrows

### 10. Add Business-Friendly Explanations
- Russian language labels and descriptions
- Non-technical summaries for each section
- "What this means for the business" annotations
- Key metrics and capabilities highlighted:
  - Автоматические ответы 24/7
  - Персонализированное общение по методологии Змейка
  - Квалификация лидов по BANT
  - Умные напоминания и отложенные сообщения
  - Интеграция с Zoom и Google Calendar
  - Комплексное тестирование качества

### 11. Implement Interactive Features
- Clickable components that reveal details
- Hover effects showing descriptions
- Collapsible sections for detailed information
- Navigation menu for jumping between sections

### 12. Add Responsive Design
- Mobile-first approach
- Breakpoints for tablet and desktop
- Touch-friendly interactions
- Readable on presentation screens

### 13. Validate and Polish
- Test in Chrome, Firefox, Safari
- Verify all animations work smoothly
- Check Russian text rendering
- Ensure all methodology content is accurate

## Testing Strategy

### Visual Testing
1. Open HTML in browser and verify all sections render correctly
2. Test environment toggle switches between views
3. Verify animations play smoothly
4. Check responsive behavior at different viewport sizes

### Content Verification
1. **Verify Змейка structure is accurately represented** (4 stages)
2. **Verify BANT is correctly explained** (4 components)
3. **Verify all 12+ principles are listed**
4. Verify Russian text displays correctly
5. Check all diagrams accurately represent the system
6. Ensure business explanations are clear and accurate

### Interaction Testing
1. Click all interactive elements
2. Verify hover states work correctly
3. Test collapsible sections expand/collapse
4. Ensure navigation menu works

## Acceptance Criteria

1. **Single HTML File**: Complete self-contained visualization with inline CSS and JS
2. **Architecture Coverage**: Shows all major system components
3. **Message Flow**: Animated visualization of message processing
4. **Communication Methodology**: Clear visualization of Змейка, BANT, 12 principles
5. **Wait Feature**: Clear visualization of follow-up scheduling
6. **Environment Modes**: Toggle between Local/Docker/Production views
7. **Testing Section**: Explains all testing mechanisms with evaluation metrics
8. **Integration Points**: Shows external service connections
9. **Russian Language**: Business-friendly Russian explanations
10. **Interactive**: Clickable elements with detail panels
11. **Responsive**: Works on desktop and tablet screens

## Validation Commands

Execute these commands to validate the task is complete:

- `open visualization/system-architecture.html` - Open in default browser to verify rendering
- `wc -l visualization/system-architecture.html` - Verify file is substantial (expect 500+ lines)
- `grep -c "Змейка\|BANT\|12 принцип" visualization/system-architecture.html` - Verify methodology content included

## Notes

### Communication Methodology Key Points to Visualize

**Змейка (Snake) - 4-Stage Call Structure:**
```
Легкий вход → Отражение → Экспертность → Следующий вопрос
   ↓              ↓            ↓              ↓
Контакт без   Перефраз     Факты, не    Продвижение
давления      клиента      утверждения   диалога
```

**BANT Qualification:**
| Компонент | Что выяснить |
|-----------|--------------|
| **B**udget | Бюджет покупки |
| **A**uthority | Кто принимает решение |
| **N**eed | Реальная потребность |
| **T**imeline | Сроки покупки |

**Key USPs to Show:**
1. Протокол комплексной проверки на 140 пунктов
2. Estate Market - собственный аналитический софт
3. Британские стандарты управления капиталом
4. Руководитель продаж лично бывает на стройках

**CRITICAL WARNING to Display:**
- НЕ упоминать "freehold для иностранцев" - юридически невозможно на Бали

### Relationship Between Skills
| Скилл | Фокус |
|-------|-------|
| **Tone of Voice** | КАК общаться (стиль, тон, 7 принципов) |
| **How To Communicate** | ЧТО говорить (методологии, скрипты, паттерны) |

Both skills together = complete agent knowledge base

### Technical Decisions
- Vanilla JavaScript (no frameworks) for simplicity and portability
- Inline CSS and JS for single-file deployment
- CSS Grid/Flexbox for layout
- CSS animations for smooth transitions

### Business Value Highlights
- Автоматические ответы 24/7
- Персонализированное общение по методологии Змейка
- Квалификация лидов по системе BANT
- Умные напоминания и отложенные сообщения
- Интеграция с Zoom и Google Calendar
- Комплексное тестирование качества с оценкой по методологии
- Защита от типичных ошибок через антипаттерны

### Dependencies
- No external dependencies required (self-contained HTML)
- Works offline after initial load
