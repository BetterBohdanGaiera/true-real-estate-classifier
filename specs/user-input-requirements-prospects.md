# Plan: User Input Requirements for Adding New Prospects

## Task Description
Проаналізувати та задокументувати увесь необхідний user input для додавання нових prospects. Дослідити поточну структуру даних, менеджмент prospects та моделі даних. Створити перелік всіх полів, їх валідацією, та пропозицією user-friendly форми для збору даних.

## Objective
Створити вичерпну документацію вимог до user input для додавання нових prospects у систему, включаючи:
- Перелік всіх полів та їх типів
- Правила валідації для кожного поля
- Пропозицію user-friendly інтерфейсу для збору даних

## Problem Statement
Система Sales Agent наразі використовує **whitelist підхід** для роботи з prospects:
- Prospects повинні бути заздалегідь додані в систему
- Вхідні повідомлення від невідомих користувачів ігноруються
- Немає production-ready інтерфейсу для додавання нових prospects (тільки ручне редагування JSON)

Ця документація визначає вимоги до створення user-friendly форми для додавання prospects.

## Solution Approach
На основі аналізу:
- `src/sales_agent/config/prospects.json` - поточна структура даних
- `src/sales_agent/crm/prospect_manager.py` - ProspectManager.add_prospect() метод
- `src/sales_agent/crm/models.py` - Pydantic модель Prospect

Документуємо всі поля, їх валідацію, та пропонуємо форму для збору даних.

---

## Relevant Files

### Існуючі файли

- **`src/sales_agent/crm/models.py`** (Lines 42-59) - Pydantic модель `Prospect` з усіма полями та їх типами
- **`src/sales_agent/crm/prospect_manager.py`** (Lines 115-137) - Метод `add_prospect()` з параметрами для створення
- **`src/sales_agent/config/prospects.json`** - JSON файл зі списком prospects (runtime storage)
- **`src/sales_agent/registry/registry_bot.py`** - Приклад conversational form для sales reps (pattern to follow)

### New Files
- **`src/sales_agent/cli/add_prospect.py`** - CLI інструмент для додавання prospects (якщо буде реалізовано)
- **`src/sales_agent/registry/prospect_intake_bot.py`** - Telegram bot для збору prospect data (альтернатива)

---

## Детальний Аналіз Полів

### Структура Моделі Prospect

```python
class Prospect(BaseModel):
    telegram_id: int | str      # REQUIRED - @username або numeric ID
    name: str                   # REQUIRED - ім'я клієнта
    context: str                # REQUIRED - причина контакту
    status: ProspectStatus      # AUTO - default: NEW
    first_contact: datetime     # AUTO - заповнюється при першому контакті
    last_contact: datetime      # AUTO - заповнюється автоматично
    last_response: datetime     # AUTO - заповнюється автоматично
    message_count: int          # AUTO - default: 0
    conversation_history: list  # AUTO - default: []
    notes: str                  # OPTIONAL - додаткові нотатки
    email: str                  # OPTIONAL - email для Zoom invite
    human_active: bool          # AUTO - default: False
```

---

## Поля для User Input

### 1. telegram_id (ОБОВ'ЯЗКОВЕ)

| Властивість | Значення |
|-------------|----------|
| **Тип** | `int \| str` |
| **Обов'язковість** | Так |
| **Опис** | Унікальний ідентифікатор Telegram користувача |
| **Формати** | `@username` або numeric ID (e.g., `7836623698`) |
| **Приклади** | `@bohdanpytaichuk`, `@ivan_petrov`, `7836623698` |

**Валідація:**
```python
# Normalization в ProspectManager._normalize_id()
def validate_telegram_id(telegram_id: int | str) -> str:
    if isinstance(telegram_id, int):
        if telegram_id <= 0:
            raise ValueError("Telegram ID must be positive")
        return str(telegram_id)

    telegram_id = telegram_id.strip()
    if not telegram_id:
        raise ValueError("Telegram ID cannot be empty")

    if telegram_id.startswith('@'):
        # Username format: 5-32 alphanumeric + underscore
        if len(telegram_id) < 6:  # @ + min 5 chars
            raise ValueError("Username too short (min 5 characters)")
        if not re.match(r'^@[a-zA-Z0-9_]{5,32}$', telegram_id):
            raise ValueError("Invalid username format")
    else:
        # Numeric ID
        try:
            numeric = int(telegram_id)
            if numeric <= 0:
                raise ValueError("Telegram ID must be positive")
        except ValueError:
            raise ValueError("Must be @username or numeric ID")

    return telegram_id
```

**Бізнес-правило:** Перевірка на дублікати (ProspectManager.add_prospect):
```python
if key in self._prospects:
    raise ValueError(f"Prospect {telegram_id} already exists")
```

---

### 2. name (ОБОВ'ЯЗКОВЕ)

| Властивість | Значення |
|-------------|----------|
| **Тип** | `str` |
| **Обов'язковість** | Так |
| **Опис** | Ім'я клієнта для персоналізації повідомлень |
| **Мова** | Російська/Англійська (Unicode підтримується) |
| **Приклади** | `Богдан`, `Алексей Петров`, `Maria` |

**Валідація:**
```python
def validate_name(name: str) -> str:
    name = name.strip()
    if not name:
        raise ValueError("Name cannot be empty")
    if len(name) < 2:
        raise ValueError("Name too short (min 2 characters)")
    if len(name) > 100:
        raise ValueError("Name too long (max 100 characters)")
    # Перевірка на заборонені символи (optional)
    if re.search(r'[<>{}[\]\\]', name):
        raise ValueError("Name contains invalid characters")
    return name
```

**Використання в системі:**
- Персоналізація привітання: `"Добрый день, {name}!"`
- Відображення в conversation context

---

### 3. context (ОБОВ'ЯЗКОВЕ)

| Властивість | Значення |
|-------------|----------|
| **Тип** | `str` |
| **Обов'язковість** | Так |
| **Опис** | Причина контакту / контекст для AI агента |
| **Мова** | Російська (переважно) |
| **Приклади** | `Ищу виллу в Чангу от 250к до 400к` |

**Валідація:**
```python
def validate_context(context: str) -> str:
    context = context.strip()
    if not context:
        raise ValueError("Context cannot be empty")
    if len(context) < 10:
        raise ValueError("Context too short (min 10 characters)")
    if len(context) > 1000:
        raise ValueError("Context too long (max 1000 characters)")
    return context
```

**Критичне значення:**
- Використовується AI агентом для генерації ПЕРШОГО повідомлення
- Має містити:
  - Тип нерухомості (вілла, апартаменти, земля)
  - Локація (Чангу, Убуд, Семіньяк)
  - Бюджет (якщо відомо)
  - Мета (інвестиція, проживання, оренда)

**Шаблони контексту:**
```
# Приклади якісного context:
"Ищу виллу в Чангу, бюджет $300-500k, для личного проживания"
"Инвестор, рассматривает апартаменты для сдачи в аренду, бюджет до $200k"
"Семья с детьми, ищут дом для переезда на Бали через 6 месяцев"
"Интересуется земельным участком под строительство в Убуде"
```

---

### 4. notes (ОПЦІОНАЛЬНЕ)

| Властивість | Значення |
|-------------|----------|
| **Тип** | `str` |
| **Обов'язковість** | Ні |
| **Default** | `""` (порожній рядок) |
| **Опис** | Додаткові нотатки для менеджера |
| **Приклади** | `Рекомендация от клиента`, `Видел рекламу в Instagram` |

**Валідація:**
```python
def validate_notes(notes: str | None) -> str:
    if notes is None:
        return ""
    notes = notes.strip()
    if len(notes) > 2000:
        raise ValueError("Notes too long (max 2000 characters)")
    return notes
```

**Використання:**
- Внутрішня інформація для менеджера
- Джерело ліда (Instagram, referral, website)
- Особливі примітки

---

### 5. email (ОПЦІОНАЛЬНЕ)

| Властивість | Значення |
|-------------|----------|
| **Тип** | `str \| None` |
| **Обов'язковість** | Ні |
| **Default** | `None` |
| **Опис** | Email клієнта для Zoom meeting invite |
| **Формат** | RFC 5322 email |
| **Приклади** | `alex.petrov@gmail.com`, `client@company.com` |

**Валідація:**
```python
def validate_email(email: str | None) -> str | None:
    if email is None or email.strip() == "":
        return None

    email = email.strip().lower()

    # RFC 5322 simplified pattern
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        raise ValueError(f"Invalid email format: {email}")

    return email
```

**Використання:**
- Надсилання calendar invite через Google Calendar API
- Zoom meeting invitation
- Може бути зібраний пізніше в розмові

---

## Поля з Автоматичним Заповненням

Ці поля НЕ потребують user input:

| Поле | Тип | Default | Коли заповнюється |
|------|-----|---------|-------------------|
| `status` | `ProspectStatus` | `NEW` | Автоматично при створенні |
| `first_contact` | `datetime` | `None` | При першому повідомленні |
| `last_contact` | `datetime` | `None` | При кожному повідомленні агента |
| `last_response` | `datetime` | `None` | При кожній відповіді prospect |
| `message_count` | `int` | `0` | Інкрементується автоматично |
| `conversation_history` | `list` | `[]` | Автоматично з кожним повідомленням |
| `human_active` | `bool` | `False` | При ручному takeover |

---

## Пропозиція User-Friendly Форми

### Варіант 1: CLI Інструмент (Рекомендовано)

```bash
# Використання:
uv run python -m sales_agent.cli.add_prospect

# Інтерактивний режим:
$ uv run python -m sales_agent.cli.add_prospect
┌─────────────────────────────────────┐
│   Додавання Нового Prospect         │
├─────────────────────────────────────┤
│ Telegram ID (@username або ID):     │
│ > @ivan_petrov                      │
│                                     │
│ Ім'я клієнта:                       │
│ > Иван Петров                       │
│                                     │
│ Контекст (чому контактуємо):        │
│ > Ищу виллу в Чангу, бюджет 300-400k│
│                                     │
│ Нотатки (optional, Enter to skip):  │
│ > Рекомендация от Алексея           │
│                                     │
│ Email (optional, Enter to skip):    │
│ > ivan@gmail.com                    │
├─────────────────────────────────────┤
│ ✓ Prospect @ivan_petrov додано!     │
│   Status: new                       │
└─────────────────────────────────────┘

# Аргументи командного рядка:
uv run python -m sales_agent.cli.add_prospect \
  --telegram-id "@ivan_petrov" \
  --name "Иван Петров" \
  --context "Ищу виллу в Чангу" \
  --notes "Referral" \
  --email "ivan@gmail.com"
```

### Варіант 2: Telegram Bot Interface

Розширення існуючого Registry Bot (`registry_bot.py`) з командами:

```
/addprospect - Початок додавання нового prospect

Бот: Введіть Telegram ID клієнта (@username):
User: @ivan_petrov

Бот: Як звати клієнта?
User: Иван Петров

Бот: Опишіть контекст (чому контактуємо):
User: Ищу виллу в Чангу, бюджет 300-400k

Бот: Додаткові нотатки? (напишіть "-" щоб пропустити)
User: Рекомендация от Алексея

Бот: Email клієнта? (напишіть "-" щоб пропустити)
User: ivan@gmail.com

Бот: ✅ Prospect додано!
     ID: @ivan_petrov
     Ім'я: Иван Петров
     Статус: new
```

### Варіант 3: JSON Template

Для bulk import або ручного редагування:

```json
{
  "prospects": [
    {
      "telegram_id": "@ivan_petrov",
      "name": "Иван Петров",
      "context": "Ищу виллу в Чангу, бюджет 300-400k",
      "notes": "Рекомендация от Алексея",
      "email": "ivan@gmail.com"
    }
  ]
}
```

---

## Таблиця Валідації Полів

| Поле | Тип | Required | Min Length | Max Length | Pattern | Default |
|------|-----|----------|------------|------------|---------|---------|
| `telegram_id` | `str \| int` | ✅ | 1 | 33 | `@[a-zA-Z0-9_]{5,32}` або `int > 0` | - |
| `name` | `str` | ✅ | 2 | 100 | Unicode, no `<>{}[]\\` | - |
| `context` | `str` | ✅ | 10 | 1000 | Free text | - |
| `notes` | `str` | ❌ | 0 | 2000 | Free text | `""` |
| `email` | `str \| None` | ❌ | 5 | 254 | RFC 5322 email | `None` |

---

## Implementation Phases

### Phase 1: Foundation
1. Створити Pydantic модель `ProspectInput` для валідації user input
2. Додати field validators до моделі
3. Написати unit tests для валідації

### Phase 2: Core Implementation
1. Створити CLI tool `add_prospect.py`
2. Інтегрувати з ProspectManager
3. Додати Rich panels для user-friendly output

### Phase 3: Integration & Polish
1. Додати команди до Telegram Registry Bot (optional)
2. Створити bulk import functionality (optional)
3. Документувати usage

---

## Step by Step Tasks

### 1. Створити ProspectInput модель з валідаторами
- Створити `src/sales_agent/crm/prospect_input.py`
- Додати Pydantic модель `ProspectInput` з полями: telegram_id, name, context, notes, email
- Реалізувати `@field_validator` для кожного поля
- Написати тести у `tests/test_prospect_input.py`

### 2. Створити CLI інструмент
- Створити `src/sales_agent/cli/__init__.py`
- Створити `src/sales_agent/cli/add_prospect.py`
- Реалізувати інтерактивний режим з Rich prompts
- Реалізувати аргументи командного рядка (argparse)
- Інтегрувати з ProspectManager.add_prospect()

### 3. Валідація та тестування
- Написати unit tests для CLI
- Протестувати edge cases (duplicates, invalid formats)
- Перевірити integration з daemon

---

## Testing Strategy

### Unit Tests
```python
def test_validate_telegram_id_username():
    assert validate_telegram_id("@ivan_petrov") == "@ivan_petrov"

def test_validate_telegram_id_numeric():
    assert validate_telegram_id(7836623698) == "7836623698"

def test_validate_telegram_id_invalid():
    with pytest.raises(ValueError):
        validate_telegram_id("@ab")  # Too short

def test_validate_email_valid():
    assert validate_email("test@example.com") == "test@example.com"

def test_validate_email_invalid():
    with pytest.raises(ValueError):
        validate_email("not-an-email")

def test_add_prospect_duplicate():
    # Setup manager with existing prospect
    with pytest.raises(ValueError, match="already exists"):
        manager.add_prospect("@existing", "Name", "Context")
```

### Integration Tests
```python
def test_cli_add_prospect_interactive():
    # Test interactive CLI flow

def test_cli_add_prospect_args():
    # Test command-line arguments

def test_daemon_recognizes_new_prospect():
    # Add prospect via CLI, verify daemon processes messages
```

---

## Acceptance Criteria

1. ✅ Документація містить повний перелік полів для user input
2. ✅ Кожне поле має чітку валідацію з error messages
3. ✅ Запропоновано user-friendly форму (CLI та/або Telegram bot)
4. ✅ Валідація відповідає існуючим pattern'ам в коді
5. ✅ Документація може бути використана для імплементації

---

## Validation Commands

Execute these commands to validate the specification:

```bash
# Перевірити що prospects.json валідний
uv run python -c "
from src.sales_agent.crm.prospect_manager import ProspectManager
pm = ProspectManager('src/sales_agent/config/prospects.json')
print(f'Loaded {len(pm.get_all_prospects())} prospects')
"

# Перевірити модель Prospect
uv run python -c "
from src.sales_agent.crm.models import Prospect, ProspectStatus
p = Prospect(
    telegram_id='@test_user',
    name='Test User',
    context='Test context for validation'
)
print(f'Created prospect: {p.telegram_id}, status: {p.status}')
"
```

---

## Notes

### Технічні особливості
- Система використовує Pydantic v2 для валідації
- Всі datetime зберігаються в ISO 8601 форматі
- Telegram IDs нормалізуються до lowercase без `@` для lookup
- ProspectManager автоматично зберігає зміни в JSON

### Майбутні розширення
- Web dashboard для prospect management
- Bulk import з CSV/Excel
- Integration з CRM системами (HubSpot, Salesforce)
- Webhook для автоматичного додавання з lead generation форм

### Безпека
- Не зберігати sensitive дані в context/notes
- Email валідація захищає від injection
- Telegram ID унікальний - захист від дублікатів
