# Plan: Update Tone of Voice & How To Communicate Skills

## Task Description
Analyze the new version of "Основной скрипт для переписок NEW.docx" and update both the `tone-of-voice` and `how-to-communicate` skills to reflect the latest communication standards, corrected information, and new strategic approaches.

## Objective
Update both skills with new USPs, corrected legal information, enhanced scripts, English translations, and new client personas while maintaining backward compatibility with existing structure.

## Problem Statement
The current skills contain outdated information and miss critical new elements:
1. **CRITICAL BUG:** Current skills mention "freehold на 80 лет" — this is legally impossible for foreigners in Bali
2. Missing new USPs: 140-point due diligence, Estate Market software, British management standards
3. Missing English translations for international traffic
4. Missing new client personas (финансист, житель Бали, etc.)
5. Missing blacklisted developer handling scripts
6. Outdated positioning: "эксперт по недвижимости" instead of "инвестиционный консультант"

## Solution Approach
Systematically update both skills with new content from the NEW.docx, prioritizing critical corrections (legal information) over enhancements.

## Relevant Files

**tone-of-voice skill (TO UPDATE):**
- `.claude/skills/tone-of-voice/SKILL.md` — Main skill file, update principles
- `.claude/skills/tone-of-voice/references/фразы.md` — Phrase templates, major updates needed
- `.claude/skills/tone-of-voice/references/структуры.md` — Message structures, moderate updates
- `.claude/skills/tone-of-voice/references/примеры.md` — Case examples, add new personas

**how-to-communicate skill (TO UPDATE):**
- `.claude/skills/how-to-communicate/SKILL.md` — Main skill, add new rules
- `.claude/skills/how-to-communicate/references/скрипты_возражения.md` — CRITICAL: Fix leasehold/freehold error
- `.claude/skills/how-to-communicate/references/методология_змейка_обогащенная.md` — Add new expert phrases

### New Files
- `.claude/skills/tone-of-voice/references/phrases_en.md` — English phrase templates
- `.claude/skills/tone-of-voice/references/cases_en.md` — English case scripts
- `.claude/skills/how-to-communicate/references/blacklist_handling.md` — Developer blacklist scripts
- `.claude/skills/how-to-communicate/references/client_personas.md` — Specialized client scripts

## Implementation Phases

### Phase 1: Critical Corrections
Fix legally incorrect information that could cause harm.

### Phase 2: Core Updates
Update existing files with new USPs and positioning.

### Phase 3: New Content
Add new files for English scripts and specialized client handling.

## Step by Step Tasks

### 1. Fix Critical Legal Error in Leasehold/Freehold Scripts
**File:** `.claude/skills/how-to-communicate/references/скрипты_возражения.md`

- **REMOVE** any mention of "freehold на 80 лет" — this is legally impossible for foreigners in Bali
- **REPLACE** with proper explanation:
  ```
  "Вопрос владения землей - ключевой. Мы детально разбираем разницу между
  Leasehold и Hak Pakai, а также проверяем договоры на наличие гарантированного
  продления. Именно это мы обсуждаем на нашей видео-встрече с цифрами в руках."
  ```
- **UPDATE** also in `.claude/skills/tone-of-voice/references/примеры.md` (Кейс 7)

### 2. Update Core USPs and Positioning in SKILL.md Files
**Files:** `tone-of-voice/SKILL.md`, `how-to-communicate/SKILL.md`

Add new USPs to both skills:
- "Протокол комплексной проверки на 140 пунктов" — main trust hook
- "Аналитика Estate Market" — IT software as authority
- "Британские стандарты управления капиталом" — positioning
- Change "эксперт по недвижимости" → "инвестиционный консультант"

### 3. Update Phrase Templates with New Positioning
**File:** `.claude/skills/tone-of-voice/references/фразы.md`

**Update представление:**
```
OLD: "Меня зовут <Имя>, я эксперт по недвижимости в агентстве True Real Estate."
NEW: "Меня зовут <Имя>, я инвестиционный консультант компании True Real Estate."
```

**Update value proposition:**
```
OLD: "Мы предоставляем профессиональные консультации..."
NEW: "Мы работаем по британским стандартам управления капиталом и
      применяем протокол проверки на 140 пунктов, чтобы Ваша
      инвестиция была выгодной и безопасной."
```

**Add new phrases:**
- "аналитическая подборка объектов, прошедших наш аудит" (instead of "самые выгодные инвестиции")
- "Руководитель отдела продаж Антон Мироненко лично бывает на стройках"
- "Estate Market — наш собственный аналитический софт"

### 4. Add Micro-Insight Follow-up Pattern
**File:** `.claude/skills/tone-of-voice/references/структуры.md`

Add new follow-up structure (alternative to soft reminder):
```markdown
## Структура Follow-up с Микро-Инсайтом

Вместо "мягкого напоминания" — давайте ценность сразу:

```
"<Имя>, добрый день! Решил поделиться свежими данными нашего софта Estate Market
по району Чангу — за прошлый месяц реальная заполняемость в сегменте апартаментов
составила 82%. Если для вас актуален расчёт доходности на основе этих фактов,
а не рекламных буклетов — дайте знать, пришлю цифры."
```
```

### 5. Update Case Scripts with New Approaches
**File:** `.claude/skills/tone-of-voice/references/примеры.md`

**Update Кейс 4 (Запрос каталога):**
```
OLD: "Я могу подготовить Вам подборку самых выгодных инвестиций..."
NEW: "Я подготовлю для вас не просто каталог, а выборку объектов,
      которые прошли наш внутренний аудит по 140 пунктам."
```

**Update Кейс 1 (Первый контакт):**
```
NEW: "Мы специализируемся на инвестиционном консалтинге и работаем
      по британским стандартам управления капиталом. Чтобы проекты
      в подборке идеально для вас подходили..."
```

### 6. Create Blacklist Developer Handling Script
**New File:** `.claude/skills/how-to-communicate/references/blacklist_handling.md`

Content:
```markdown
# Обработка Запросов по Черному Списку Застройщиков

## Черный Список (НЕ рекомендуем)
- Moonlight Villas
- Serenity Villas
- PARQ - Family
- Loyo - Melasti Dream Residence, XO Pandawa, PANDAWA HILLS, Pandawa Dream
- Aura (Ubud)

## Под Вопросом (Проверка, Due Diligence)
- Loyo - XO Project Canggu
- PARQ BLUE - Zen Estate
- OUR PLACE - Green Bowl
- BREIG - Elysium
- PARQ - Citadel
- HQC - BLOOM
- Archestet

## Скрипт Обработки

"Знаем этот объект. Но пока не могу Вам рекомендовать, так как проект
не прошёл нашу внутреннюю проверку из 140 пунктов. Мы дорожим капиталом
наших клиентов, поэтому предлагаю рассмотреть варианты от проверенных
застройщиков. Подскажите, какие именно параметры этого объекта вас
заинтересовали, чтобы я подобрал максимально качественную альтернативу?"
```

### 7. Create Client Persona Scripts
**New File:** `.claude/skills/how-to-communicate/references/client_personas.md`

Add three specialized personas:
1. **Финансист** — focus on ROI, risk models, spreadsheets
2. **Житель Бали** — already knows the island, focus on legals
3. **"Дорого/Нет денег"** — soft approach, educational focus

### 8. Add AI Agent Rules
**File:** `.claude/skills/how-to-communicate/SKILL.md`

Add new section:
```markdown
## Правила для AI-Агента

1. **Имя менеджера как гарант:** Упоминать "Наш руководитель продаж
   Антон Мироненко лично бывает на этих стройках"
2. **Estate Market как авторитет:** "Проанализируем цифры через наш софт"
3. **Смещение фокуса:** "Встреча ни к чему не обязывает, это
   ознакомительный формат"
4. **Гибкость:** Если клиент занят — мгновенно: "Всё хорошо,
   напишу текстом / вышлю календарь"
5. **Учёт контекста:** Учитывать часовой пояс (Киев/Европа),
   личные обстоятельства (дети, работа, отпуск)
```

### 9. Create English Phrase Templates
**New File:** `.claude/skills/tone-of-voice/references/phrases_en.md`

Add all English templates from Cases 1-14, including:
- British capital management standards
- 140-point due diligence protocol
- Estate Market analytics platform
- Leasehold/Hak Pakai explanation

### 10. Create English Case Scripts
**New File:** `.claude/skills/tone-of-voice/references/cases_en.md`

Add all 14 English cases:
- Case 1: New lead (Funnel)
- Case 2: No response (Value follow-up)
- Case 3: Refused dialogue
- Case 4: Catalog request
- Case 5: Not ready to buy immediately
- Case 6: Referral
- Case 7: Oceanfront interest
- Case 8: Not in Bali / New to locations
- Case 9: Land Ownership Fears (Leasehold handling)
- Case 10: High ROI & installment plans
- Case 11: Market study & technical risks
- Case 12: Fund Transfers & Crypto
- Case 13: Residential + Yield
- Case 14: Investment Newbie

### 11. Update Quick Check Lists
**Files:** `tone-of-voice/SKILL.md`, `how-to-communicate/SKILL.md`

Add new checklist items:
- [ ] Упомянут протокол проверки 140 пунктов?
- [ ] Используется Estate Market как аргумент?
- [ ] Позиционирование как консультант, не риелтор?
- [ ] **НЕ упоминается freehold для иностранцев?**

### 12. Validate All Changes
Run validation:
- Grep for "freehold" in both skills — should NOT appear without correct context
- Grep for "эксперт по недвижимости" — should be replaced
- Ensure all 14 Russian cases are present
- Ensure all 14 English cases are present

## Testing Strategy
1. Read all updated files to verify no remaining "freehold на 80 лет" mentions
2. Check that new USPs (140 пунктов, Estate Market) appear in key files
3. Verify English files are syntactically correct markdown
4. Count total cases in Russian (14) and English (14)

## Acceptance Criteria
- [ ] CRITICAL: No "freehold на 80 лет" mentions remain (legal fix)
- [ ] "инвестиционный консультант" replaces "эксперт по недвижимости"
- [ ] 140-point audit mentioned in SKILL.md and key phrase files
- [ ] Estate Market mentioned as authority source
- [ ] Blacklist handling script created
- [ ] 3 client persona scripts created (финансист, житель Бали, дорого)
- [ ] AI Agent rules section added
- [ ] English phrases_en.md created with all templates
- [ ] English cases_en.md created with all 14 cases
- [ ] Quick checklists updated in both skills

## Validation Commands
Execute these commands to validate the task is complete:

- `grep -r "freehold на 80" .claude/skills/` — Should return NOTHING (critical fix)
- `grep -r "140 пунктов" .claude/skills/tone-of-voice/` — Should find matches
- `grep -r "Estate Market" .claude/skills/how-to-communicate/` — Should find matches
- `ls .claude/skills/tone-of-voice/references/` — Should include phrases_en.md, cases_en.md
- `ls .claude/skills/how-to-communicate/references/` — Should include blacklist_handling.md, client_personas.md

## Notes
- The NEW document takes precedence over existing content
- Правки от Даши (12.01.26) are explicitly marked as corrections to apply
- English scripts are for "англ.трафик" (English-speaking clients)
- Blacklist is marked as "уточнить у Антона конкретику" — use as-is for now
- Some cases in the NEW doc are marked "с правками от Артема" — these are the latest versions
