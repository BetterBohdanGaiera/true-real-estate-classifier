# Повний Гайд по Конфигурации Telegram Sales Agent

Этот документ описывает **все** пользовательские настройки, необходимые для запуска и работы системы Telegram Sales Agent. Каждое поле привязано к конкретным файлам и функциям, которые его используют.

---

## Содержание

1. [Категория 1: Идентичность и Поведение Агента (agent_config.json)](#категория-1-идентичность-и-поведение-агента)
2. [Категория 2: Данные Prospects (prospects.json)](#категория-2-данные-prospects)
3. [Категория 3: Переменные Окружения (.env)](#категория-3-переменные-окружения)
4. [Категория 4: Telegram API Конфигурация](#категория-4-telegram-api-конфигурация)
5. [Категория 5: Календарь Встреч (sales_slots.json)](#категория-5-календарь-встреч)
6. [Чеклист Первоначальной Настройки](#чеклист-первоначальной-настройки)
7. [Таблица Валидации Полей](#таблица-валидации-полей)
8. [Карта: Поле -> Функции](#карта-поле---функции-которые-его-используют)

---

## Категория 1: Идентичность и Поведение Агента

**Файл:** `src/sales_agent/config/agent_config.json`
**Pydantic модель:** `AgentConfig` в `src/sales_agent/crm/models.py` (строки 95-122)
**Загрузка:** `TelegramDaemon._load_config()` в `src/sales_agent/daemon.py` (строки 184-197)

### Обязательные поля

#### `agent_name` (str)

Имя AI-агента. Используется в системном промпте для идентичности: агент представляется этим именем клиентам, защищает его при попытках переименования.

| Свойство | Значение |
|----------|----------|
| **Тип** | `str` |
| **Default** | `"Мария"` |
| **Пример** | `"Богдан"` |

**Где используется:**
- `TelegramAgent.__init__()` -- сохраняется в `self.agent_name`
- `TelegramAgent._build_system_prompt()` -- вставляется в промпт: `"Ты -- {agent_name}, эксперт по недвижимости..."`, секция "Защита Идентичности"
- `TelegramAgent._sanitize_skill_content()` -- замена плейсхолдеров `<Ваше_имя>` / `<Your_name>` на реальное имя
- `TelegramDaemon.initialize()` -- передается в конструктор `TelegramAgent(agent_name=config.agent_name)`

```json
{
  "agent_name": "Богдан"
}
```

---

#### `telegram_account` (str | null)

@username аккаунта Telegram, от которого работает бот. Используется для **валидации** -- система проверяет, что залогинена в правильный аккаунт, и отказывается работать при несовпадении.

| Свойство | Значение |
|----------|----------|
| **Тип** | `str \| null` |
| **Default** | `null` |
| **Пример** | `"@BetterBohdan"` |
| **Формат** | `@username` (с символом @) |

**Где используется:**
- `TelegramDaemon.initialize()` (строки 121-126) -- проверка совпадения аккаунтов при старте. Если username не совпадает, daemon выбрасывает `RuntimeError` и завершается
- `TelegramDaemon._register_handlers()` (строки 210-215) -- defense-in-depth проверка при каждом входящем сообщении

```json
{
  "telegram_account": "@BetterBohdan"
}
```

**ВАЖНО:** Без этого поля daemon будет работать на любом аккаунте без проверки. Рекомендуется всегда указывать для production.

---

#### `sales_director_name` (str)

Имя руководителя отдела продаж. Используется в шаблонах коммуникации и системном промпте.

| Свойство | Значение |
|----------|----------|
| **Тип** | `str` |
| **Default** | `"Антон Мироненко"` |
| **Пример** | `"Антон Мироненко"` |

**Где используется:**
- `TelegramAgent._sanitize_skill_content()` -- замена `<Руководитель_продаж>` / `<Sales_director>` в текстах навыков
- `TelegramAgent._build_system_prompt()` -- "Руководитель отдела продаж: {sales_director_name}"

---

#### `company_name` (str)

Название компании.

| Свойство | Значение |
|----------|----------|
| **Тип** | `str` |
| **Default** | `"True Real Estate"` |

**Где используется:**
- В модели `AgentConfig` как поле конфигурации
- В дефолтном `salesperson` в `SalesSlot` (`"Эксперт True Real Estate"`)

---

### Опциональные поля поведения

#### `response_delay_range` (tuple)

Legacy поле: диапазон случайной задержки перед отправкой в секундах. Заменено системой length-based delays, но остается для обратной совместимости.

| Свойство | Значение |
|----------|----------|
| **Тип** | `tuple[float, float]` |
| **Default** | `[2.0, 5.0]` |
| **Единица** | секунды |

---

#### `delay_short` / `delay_medium` / `delay_long` (tuple)

Задержка отправки сообщения, зависящая от длины текста. Имитирует набор текста реальным человеком.

| Поле | Default | Применяется при |
|------|---------|-----------------|
| `delay_short` | `[1.0, 2.0]` | Текст < 50 символов |
| `delay_medium` | `[3.0, 5.0]` | Текст 50-200 символов |
| `delay_long` | `[5.0, 10.0]` | Текст > 200 символов |

**Где используется:**
- `TelegramService._calculate_delay()` (строки 73-90) -- выбирает диапазон по длине текста и генерирует случайное значение

```json
{
  "delay_short": [1.0, 2.0],
  "delay_medium": [3.0, 5.0],
  "delay_long": [5.0, 10.0]
}
```

---

#### `reading_delay_short` / `reading_delay_medium` / `reading_delay_long` (tuple)

Задержка перед обработкой входящего сообщения, зависящая от длины текста клиента. Имитирует время чтения сообщения реальным человеком.

| Поле | Default | Применяется при |
|------|---------|-----------------|
| `reading_delay_short` | `[2.0, 4.0]` | Входящий текст < 50 символов |
| `reading_delay_medium` | `[4.0, 8.0]` | Входящий текст 50-200 символов |
| `reading_delay_long` | `[8.0, 15.0]` | Входящий текст > 200 символов |

**Где используется:**
- `TelegramService._calculate_reading_delay()` - выбирает диапазон по длине входящего сообщения и генерирует случайное значение
- `TelegramDaemon.handle_incoming()` - вызывает reading delay перед `generate_response()`

```json
{
  "reading_delay_short": [2.0, 4.0],
  "reading_delay_medium": [4.0, 8.0],
  "reading_delay_long": [8.0, 15.0]
}
```

---

#### `max_messages_per_day_per_prospect` (int | null)

Максимальное количество сообщений агента одному prospect в день. `null` = без ограничений.

| Свойство | Значение |
|----------|----------|
| **Тип** | `int \| null` |
| **Default** | `null` |

**Где используется:**
- `TelegramAgent.check_rate_limit()` -- проверяет лимит перед каждой отправкой
- `TelegramDaemon.handle_incoming()` / `process_new_prospects()` / `process_follow_ups()` -- вызывает проверку

---

#### `working_hours` (tuple | null)

Рабочие часы агента. Вне этих часов агент не отправляет сообщения. `null` = круглосуточно.

| Свойство | Значение |
|----------|----------|
| **Тип** | `tuple[int, int] \| null` |
| **Default** | `null` |
| **Формат** | `[start_hour, end_hour]` (24h) |
| **Пример** | `[9, 21]` = с 9:00 до 21:00 |

**Где используется:**
- `TelegramAgent.is_within_working_hours()` -- проверка текущего часа
- `TelegramDaemon.handle_incoming()` / `process_new_prospects()` / `process_follow_ups()` -- вызывает проверку

---

#### `typing_simulation` (bool)

Симуляция индикатора набора текста (typing...) перед отправкой сообщения.

| Свойство | Значение |
|----------|----------|
| **Тип** | `bool` |
| **Default** | `true` |

**Где используется:**
- `TelegramService.send_message()` -- вызывает `_simulate_typing()` если включено
- `TelegramService._simulate_typing()` -- отправляет Telegram typing action, ждет пропорционально длине текста (~20 символов/сек, мин 1 сек, макс 5 сек)

---

#### `auto_follow_up_hours` (int)

Количество часов без ответа, после которых daemon отправляет автоматический follow-up.

| Свойство | Значение |
|----------|----------|
| **Тип** | `int` |
| **Default** | `24` |
| **Единица** | часы |

**Где используется:**
- `TelegramDaemon.process_follow_ups()` -- `prospect_manager.should_follow_up(hours=config.auto_follow_up_hours)`

---

#### `escalation_keywords` (list[str])

Ключевые слова, при обнаружении которых сообщение автоматически эскалируется (вместо ответа агента).

| Свойство | Значение |
|----------|----------|
| **Тип** | `list[str]` |
| **Default** | `["call", "phone", "urgent", "срочно", "позвони", "звонок"]` |

**Где используется:**
- `TelegramAgent.generate_response()` (строки 396-401) -- проверка каждого входящего сообщения на содержание ключевых слов (case-insensitive)

```json
{
  "escalation_keywords": [
    "call", "phone", "urgent",
    "срочно", "позвони", "звонок", "перезвони"
  ]
}
```

---

#### `escalation_notify` (str | null)

Telegram ID администратора для получения уведомлений при эскалации. `null` = уведомления не отправляются.

| Свойство | Значение |
|----------|----------|
| **Тип** | `str \| null` |
| **Default** | `null` |
| **Формат** | Telegram numeric ID или @username |

**Где используется:**
- `TelegramDaemon.handle_incoming()` (строки 518-525) -- `service.notify_escalation(config.escalation_notify, ...)`
- `TelegramService.notify_escalation()` -- отправляет форматированное уведомление с именем клиента, причиной и текстом сообщения

---

#### `include_knowledge_base` (bool)

Использовать ли базу знаний для контекстных ответов.

| Свойство | Значение |
|----------|----------|
| **Тип** | `bool` |
| **Default** | `true` |

**Где используется:**
- `TelegramAgent.generate_response()` (строка 406) -- если `true`, загружает релевантный контекст из knowledge base через `KnowledgeLoader.get_relevant_context()`

---

#### `max_knowledge_tokens` (int)

Максимальное количество токенов для контекста из базы знаний.

| Свойство | Значение |
|----------|----------|
| **Тип** | `int` |
| **Default** | `4000` |

**Где используется:**
- `TelegramAgent.generate_response()` (строка 409) -- `knowledge_loader.get_relevant_context(max_tokens=config.max_knowledge_tokens)`

---

### Полный пример agent_config.json

```json
{
  "agent_name": "Богдан",
  "telegram_account": "@BetterBohdan",
  "sales_director_name": "Антон Мироненко",
  "company_name": "True Real Estate",
  "response_delay_range": [2.0, 5.0],
  "delay_short": [1.0, 2.0],
  "delay_medium": [3.0, 5.0],
  "delay_long": [5.0, 10.0],
  "max_messages_per_day_per_prospect": null,
  "working_hours": null,
  "typing_simulation": true,
  "auto_follow_up_hours": 24,
  "escalation_keywords": [
    "call", "phone", "urgent",
    "срочно", "позвони", "звонок", "перезвони"
  ],
  "escalation_notify": null,
  "include_knowledge_base": true,
  "max_knowledge_tokens": 4000
}
```

---

## Категория 2: Данные Prospects

**Файл:** `src/sales_agent/config/prospects.json`
**Pydantic модель:** `Prospect` в `src/sales_agent/crm/models.py` (строки 42-58)
**Загрузка:** `ProspectManager` в `src/sales_agent/crm/prospect_manager.py`

### Обязательные поля (вводит пользователь)

#### `telegram_id` (str | int)

Уникальный идентификатор Telegram пользователя. Определяет, кому агент отправляет сообщения и от кого принимает ответы.

| Свойство | Значение |
|----------|----------|
| **Тип** | `str \| int` |
| **Обязательно** | Да |
| **Форматы** | `@username` или числовой Telegram ID |
| **Примеры** | `"@bohdanpytaichuk"`, `7836623698` |

**Валидация:**
- `@username`: от 5 до 32 символов, допустимы `a-zA-Z0-9_`
- Числовой ID: положительное целое число
- Уникальность: дубликаты запрещены (`ProspectManager.add_prospect()`)

**Где используется:**
- `ProspectManager.is_prospect()` -- проверка входящих сообщений
- `ProspectManager.get_prospect()` -- получение данных по ID
- `TelegramService.send_message()` -- адресат отправки через `resolve_entity()`
- `TelegramDaemon.handle_incoming()` -- маршрутизация входящих

---

#### `name` (str)

Имя клиента. Используется для персонализации первого сообщения и во всех ответах агента.

| Свойство | Значение |
|----------|----------|
| **Тип** | `str` |
| **Обязательно** | Да |
| **Примеры** | `"Богдан"`, `"Алексей Петров"`, `"Maria"` |

**Где используется:**
- `TelegramAgent.generate_initial_message()` -- "Имя: {prospect.name}" в промпте
- `TelegramAgent.generate_response()` -- замена `<Имя_клиента>` / `<Client_name>` на `prospect.name`
- `TelegramAgent.generate_follow_up()` -- персонализация follow-up сообщений
- Console logging -- отображение имени в логах daemon

---

#### `context` (str)

Причина контакта / что ищет клиент. Это **критически важное** поле -- AI агент генерирует первое сообщение на его основе.

| Свойство | Значение |
|----------|----------|
| **Тип** | `str` |
| **Обязательно** | Да |
| **Мин. длина** | 10 символов (рекомендация) |
| **Макс. длина** | 1000 символов (рекомендация) |

**Где используется:**
- `TelegramAgent.generate_initial_message()` -- "Контекст: {prospect.context}" -- основа для генерации первого сообщения
- `TelegramAgent.generate_response()` -- включается в контекст для каждого ответа
- `TelegramAgent.generate_follow_up()` -- учитывается при генерации follow-up

**Примеры качественного context:**
```
"Ищу виллу в Чангу от 250к до 400к"
"Инвестор, рассматривает апартаменты для сдачи в аренду, бюджет до $200k"
"Семья с детьми, ищут дом для переезда на Бали через 6 месяцев"
"Интересуется земельным участком под строительство в Убуде"
```

---

### Опциональные поля (вводит пользователь)

#### `notes` (str)

Внутренние заметки для менеджера. Не передаются в AI-промпт напрямую, но видны в данных prospect.

| Свойство | Значение |
|----------|----------|
| **Тип** | `str` |
| **Default** | `""` |
| **Примеры** | `"Рекомендация от клиента"`, `"Видел рекламу в Instagram"` |

---

#### `email` (str | null)

Email клиента. Необходим для отправки Zoom-приглашения. Может быть добавлен заранее или собран в процессе разговора.

| Свойство | Значение |
|----------|----------|
| **Тип** | `str \| null` |
| **Default** | `null` |
| **Формат** | RFC 5322 email |

**Где используется:**
- `TelegramDaemon.handle_incoming()` (schedule action) -- email **обязателен** для бронирования встречи. Без email бронирование отклоняется
- `SchedulingTool.book_meeting()` -- валидация email формата, отправка приглашения
- `ProspectManager.update_prospect_email()` -- сохранение при получении от клиента

---

### Автозаполняемые поля (НЕ вводит пользователь)

Эти поля управляются системой и **не требуют** ручного ввода:

| Поле | Тип | Default | Когда заполняется |
|------|-----|---------|-------------------|
| `status` | `ProspectStatus` | `"new"` | Автоматически: new -> contacted -> in_conversation -> zoom_scheduled -> converted -> archived |
| `first_contact` | `datetime \| null` | `null` | При отправке первого сообщения (`mark_contacted()`) |
| `last_contact` | `datetime \| null` | `null` | При каждом сообщении от агента (`record_agent_message()`) |
| `last_response` | `datetime \| null` | `null` | При каждом ответе от клиента (`record_response()`) |
| `message_count` | `int` | `0` | Инкремент при каждом сообщении агента |
| `conversation_history` | `list[ConversationMessage]` | `[]` | Автоматически с каждым сообщением |
| `human_active` | `bool` | `false` | При ручном takeover оператором |

---

### Полный пример prospects.json

```json
{
  "prospects": [
    {
      "telegram_id": "@bohdanpytaichuk",
      "name": "Богдан",
      "context": "Ищу виллу в Чангу от 250к до 400к",
      "notes": "Primary test prospect",
      "email": null
    }
  ]
}
```

**Минимальный prospect (только обязательные поля):**
```json
{
  "telegram_id": "@ivan_petrov",
  "name": "Иван Петров",
  "context": "Инвестиция в виллу, бюджет $500k, Чангу"
}
```

---

## Категория 3: Переменные Окружения

**Файл:** `.env` (в корне проекта)
**Шаблон:** `.env.example`
**Загрузка:** `python-dotenv` через `load_dotenv()` в каждом модуле

### Обязательные

#### `ANTHROPIC_API_KEY`

API-ключ Anthropic для Claude API. Без этого ключа агент не может генерировать сообщения.

| Свойство | Значение |
|----------|----------|
| **Обязательно** | Да |
| **Получить** | https://console.anthropic.com/ |
| **Формат** | `sk-ant-...` |

**Где используется:**
- `TelegramAgent.__init__()` -- `Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))`
- Все вызовы `client.messages.create()` для генерации сообщений

```
ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxxxxx
```

---

#### `DATABASE_URL`

PostgreSQL connection string. Обязательна для работы scheduled actions (follow-ups, reminders).

| Свойство | Значение |
|----------|----------|
| **Обязательно** | Да (для scheduled actions) |
| **Формат** | PostgreSQL connection string |

**Где используется:**
- `database/init.py` -- проверка подключения, миграции схемы
- `scheduling/scheduled_action_manager.py` -- CRUD для запланированных действий через `asyncpg`

```
# NeonDB (рекомендуется - бесплатный tier):
DATABASE_URL=postgresql://username:password@ep-xxx-xxx.aws.neon.tech/neondb?sslmode=require

# Docker:
DATABASE_URL=postgresql://postgres:mypassword@localhost:5432/orchestrator

# Локальный PostgreSQL:
DATABASE_URL=postgresql://localhost:5432/orchestrator
```

---

### Опциональные

#### `REGISTRY_BOT_TOKEN`

Токен Telegram бота для Registry Bot (регистрация sales-менеджеров).

| Свойство | Значение |
|----------|----------|
| **Обязательно** | Нет (только для registry bot) |
| **Получить** | @BotFather в Telegram |
| **Формат** | `1234567890:ABCdefGHI...` |

```
REGISTRY_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrstUVWxyz
```

---

#### `CORPORATE_EMAIL_DOMAIN`

Домен корпоративной почты для валидации при регистрации sales-менеджеров.

| Свойство | Значение |
|----------|----------|
| **Обязательно** | Нет |
| **Default** | не задан |
| **Пример** | `truerealestate.bali` |

```
CORPORATE_EMAIL_DOMAIN=truerealestate.bali
```

---

#### `OUTREACH_INTERVAL_SECONDS`

Интервал проверки новых prospect assignments в секундах.

| Свойство | Значение |
|----------|----------|
| **Default** | `300` (5 минут) |
| **Единица** | секунды |

---

#### `MAX_PROSPECTS_PER_REP`

Максимум prospects, назначаемых одному rep за раз.

| Свойство | Значение |
|----------|----------|
| **Default** | `5` |

---

#### `OUTREACH_ENABLED`

Включение/отключение outreach daemon.

| Свойство | Значение |
|----------|----------|
| **Default** | `true` |
| **Формат** | `true` / `false` |

---

## Категория 4: Telegram API Конфигурация

**Файл:** `~/.telegram_dl/config.json`
**Session:** `~/.telegram_dl/user.session`
**Код:** `src/sales_agent/telegram/telegram_fetch.py`

### Необходимые параметры

#### `api_id` и `api_hash`

Telegram API credentials. Без них невозможно подключение к Telegram.

| Свойство | Значение |
|----------|----------|
| **Обязательно** | Да |
| **Получить** | https://my.telegram.org/auth |

**Шаги получения:**
1. Перейти на https://my.telegram.org/auth
2. Авторизоваться по номеру телефона
3. Нажать "API development tools"
4. Создать новое приложение (любое имя/описание)
5. Записать `api_id` (число) и `api_hash` (строка)

**Формат config.json (`~/.telegram_dl/config.json`):**
```json
{
  "api_id": 12345678,
  "api_hash": "abcdef0123456789abcdef0123456789"
}
```

**Где используется:**
- `telegram_fetch.get_client()` -- `TelegramClient(session_file, config["api_id"], config["api_hash"])`
- `telegram_fetch.is_configured()` -- проверка наличия обоих ключей

---

#### Session файл

Файл сессии Telethon. Создается автоматически при первой авторизации.

| Свойство | Значение |
|----------|----------|
| **Путь** | `~/.telegram_dl/user.session` |
| **Создание** | Автоматически при `client.start()` |

**Первоначальная настройка:**
```bash
# Установить telegram_dl и запустить авторизацию:
# 1. Ввести api_id и api_hash
# 2. Ввести номер телефона (с кодом страны)
# 3. Ввести SMS-код от Telegram
# 4. Ввести пароль 2FA (если включена)
```

**Проверка статуса:**
```bash
PYTHONPATH=src uv run python src/sales_agent/telegram/telegram_fetch.py setup --status
```

---

## Категория 5: Календарь Встреч

**Файл конфигурации:** `src/sales_agent/config/sales_slots.json`
**Файл данных (автогенерация):** `src/sales_agent/config/sales_slots_data.json`
**Код:** `src/sales_agent/scheduling/sales_calendar.py`

### Поля конфигурации

#### `salesperson` (str)

Имя эксперта, отображаемое в слотах.

| Свойство | Значение |
|----------|----------|
| **Default** | `"Эксперт True Real Estate"` |

---

#### `timezone` (str)

Часовой пояс для расчета слотов.

| Свойство | Значение |
|----------|----------|
| **Default** | `"Asia/Makassar"` (UTC+8, Бали) |

---

#### `working_hours` (object)

Рабочие часы для генерации слотов.

```json
{
  "working_hours": {
    "start": "10:00",
    "end": "19:00"
  }
}
```

---

#### `available_hours` (list[int])

Конкретные часы, в которые генерируются слоты. Модуль `sales_calendar.py` использует захардкоженный список `WORKING_HOURS = [10, 11, 14, 15, 16, 17, 18]` при генерации mock-слотов, но конфиг-файл хранит это для документации и будущего использования.

```json
{
  "available_hours": [10, 11, 14, 15, 16, 17, 18]
}
```

---

#### `slot_duration_minutes` (int)

Длительность одного слота в минутах.

| Свойство | Значение |
|----------|----------|
| **Default** | `30` |

---

#### `break_between_slots_minutes` (int)

Перерыв между слотами.

| Свойство | Значение |
|----------|----------|
| **Default** | `15` |

---

#### `days_ahead` (int)

Количество дней вперед для генерации слотов.

| Свойство | Значение |
|----------|----------|
| **Default** | `7` |

**Где используется:**
- `SalesCalendar.refresh_slots()` -- определяет окно генерации
- `SalesCalendar.generate_mock_slots()` -- количество дней вперед

---

#### `include_weekends` (bool)

Включать ли выходные дни в расписание.

| Свойство | Значение |
|----------|----------|
| **Default** | `false` |

**Где используется:**
- `SalesCalendar.generate_mock_slots()` -- `if current_date.weekday() >= 5: continue` (пропуск выходных)

---

#### `blocked_dates` (list[str])

Список заблокированных дат (праздники, отпуска).

| Свойство | Значение |
|----------|----------|
| **Default** | `[]` |
| **Формат** | ISO 8601 даты |
| **Пример** | `["2026-02-14", "2026-03-01"]` |

---

#### `pre_booked` (list)

Предзабронированные слоты (зарезервированные заранее).

| Свойство | Значение |
|----------|----------|
| **Default** | `[]` |

---

### Полный пример sales_slots.json

```json
{
  "salesperson": "Эксперт True Real Estate",
  "timezone": "Asia/Makassar",
  "working_hours": {
    "start": "10:00",
    "end": "19:00"
  },
  "available_hours": [10, 11, 14, 15, 16, 17, 18],
  "slot_duration_minutes": 30,
  "break_between_slots_minutes": 15,
  "days_ahead": 7,
  "include_weekends": false,
  "blocked_dates": [],
  "pre_booked": []
}
```

---

## Чеклист Первоначальной Настройки

### Шаг 1: Environment Variables

```bash
# Скопировать шаблон
cp .env.example .env

# Заполнить обязательные ключи в .env:
# - ANTHROPIC_API_KEY  (обязательно)
# - DATABASE_URL       (обязательно для scheduled actions)
```

### Шаг 2: Telegram API

```bash
# 1. Получить api_id и api_hash на https://my.telegram.org/auth
# 2. Создать конфиг:
mkdir -p ~/.telegram_dl
cat > ~/.telegram_dl/config.json << 'EOF'
{
  "api_id": YOUR_API_ID,
  "api_hash": "YOUR_API_HASH"
}
EOF

# 3. Авторизоваться (создаст session файл):
PYTHONPATH=src uv run python src/sales_agent/telegram/telegram_fetch.py setup --status
```

### Шаг 3: Agent Identity

```bash
# Редактировать src/sales_agent/config/agent_config.json:
# - agent_name        -- имя агента
# - telegram_account  -- @username аккаунта
# - sales_director_name -- имя руководителя
```

### Шаг 4: Prospects

```bash
# Редактировать src/sales_agent/config/prospects.json:
# Добавить минимум одного prospect с полями:
# - telegram_id  -- @username или числовой ID
# - name         -- имя клиента
# - context      -- причина контакта
```

### Шаг 5: Sales Calendar

```bash
# Проверить/настроить src/sales_agent/config/sales_slots.json
# Слоты генерируются автоматически, но можно настроить:
# - working_hours, available_hours
# - blocked_dates (праздники)
# - include_weekends
```

### Шаг 6: Запуск

```bash
# Запустить daemon:
PYTHONPATH=src uv run python src/sales_agent/daemon.py

# Daemon выполнит:
# 1. Инициализацию базы данных (миграции)
# 2. Подключение к Telegram
# 3. Проверку совпадения аккаунта
# 4. Загрузку prospects
# 5. Инициализацию knowledge base
# 6. Запуск calendar и scheduler
# 7. Обработку новых prospects
# 8. Прослушивание входящих сообщений
```

---

## Таблица Валидации Полей

### Agent Config (agent_config.json)

| Поле | Тип | Required | Default | Min | Max | Паттерн |
|------|-----|----------|---------|-----|-----|---------|
| `agent_name` | `str` | Нет (есть default) | `"Мария"` | 1 | - | Unicode |
| `telegram_account` | `str \| null` | Нет | `null` | 6 | 33 | `@[a-zA-Z0-9_]{5,32}` |
| `sales_director_name` | `str` | Нет (есть default) | `"Антон Мироненко"` | 1 | - | Unicode |
| `company_name` | `str` | Нет (есть default) | `"True Real Estate"` | 1 | - | Free text |
| `response_delay_range` | `tuple[float, float]` | Нет | `(2.0, 5.0)` | 0.0 | - | `[min, max]` |
| `delay_short` | `tuple[float, float]` | Нет | `(1.0, 2.0)` | 0.0 | - | `[min, max]` |
| `delay_medium` | `tuple[float, float]` | Нет | `(3.0, 5.0)` | 0.0 | - | `[min, max]` |
| `delay_long` | `tuple[float, float]` | Нет | `(5.0, 10.0)` | 0.0 | - | `[min, max]` |
| `max_messages_per_day_per_prospect` | `int \| null` | Нет | `null` | 1 | - | Positive int |
| `working_hours` | `tuple[int, int] \| null` | Нет | `null` | - | - | `[0-23, 0-23]` |
| `typing_simulation` | `bool` | Нет | `true` | - | - | `true/false` |
| `auto_follow_up_hours` | `int` | Нет | `24` | 1 | - | Positive int |
| `escalation_keywords` | `list[str]` | Нет | 6 keywords | - | - | list of strings |
| `escalation_notify` | `str \| null` | Нет | `null` | - | - | Telegram ID |
| `include_knowledge_base` | `bool` | Нет | `true` | - | - | `true/false` |
| `max_knowledge_tokens` | `int` | Нет | `4000` | 1 | - | Positive int |

### Prospect Fields (prospects.json)

| Поле | Тип | Required | Default | Min | Max | Паттерн |
|------|-----|----------|---------|-----|-----|---------|
| `telegram_id` | `str \| int` | Да | - | 1 | 33 | `@[a-zA-Z0-9_]{5,32}` или `int > 0` |
| `name` | `str` | Да | - | 2 | 100 | Unicode, без `<>{}[]\\` |
| `context` | `str` | Да | - | 10 | 1000 | Free text |
| `notes` | `str` | Нет | `""` | 0 | 2000 | Free text |
| `email` | `str \| null` | Нет | `null` | 5 | 254 | RFC 5322 email |

### Sales Calendar (sales_slots.json)

| Поле | Тип | Required | Default | Допустимые значения |
|------|-----|----------|---------|---------------------|
| `salesperson` | `str` | Нет | `"Эксперт True Real Estate"` | Free text |
| `timezone` | `str` | Нет | `"Asia/Makassar"` | IANA timezone |
| `working_hours.start` | `str` | Нет | `"10:00"` | `HH:MM` |
| `working_hours.end` | `str` | Нет | `"19:00"` | `HH:MM` |
| `available_hours` | `list[int]` | Нет | `[10,11,14,15,16,17,18]` | 0-23 |
| `slot_duration_minutes` | `int` | Нет | `30` | Positive int |
| `break_between_slots_minutes` | `int` | Нет | `15` | Positive int |
| `days_ahead` | `int` | Нет | `7` | Positive int |
| `include_weekends` | `bool` | Нет | `false` | `true/false` |
| `blocked_dates` | `list[str]` | Нет | `[]` | ISO 8601 dates |

### Environment Variables (.env)

| Переменная | Required | Default | Формат |
|------------|----------|---------|--------|
| `ANTHROPIC_API_KEY` | Да | - | `sk-ant-...` |
| `DATABASE_URL` | Да* | - | PostgreSQL URI |
| `REGISTRY_BOT_TOKEN` | Нет | - | Telegram bot token |
| `CORPORATE_EMAIL_DOMAIN` | Нет | - | Domain name |
| `OUTREACH_INTERVAL_SECONDS` | Нет | `300` | Positive int |
| `MAX_PROSPECTS_PER_REP` | Нет | `5` | Positive int |
| `OUTREACH_ENABLED` | Нет | `true` | `true/false` |

\* Обязательна для scheduled actions (follow-ups). Daemon упадет при старте без нее.

### Telegram Config (~/.telegram_dl/config.json)

| Поле | Required | Формат |
|------|----------|--------|
| `api_id` | Да | Positive int |
| `api_hash` | Да | 32-char hex string |

---

## Карта: Поле -> Функции, Которые Его Используют

### agent_config.json

| Поле | Файл | Функция/Метод |
|------|------|---------------|
| `agent_name` | `agent/telegram_agent.py` | `__init__()`, `_build_system_prompt()`, `_sanitize_skill_content()` |
| `agent_name` | `daemon.py` | `TelegramDaemon.initialize()` -- передает в конструктор TelegramAgent |
| `telegram_account` | `daemon.py` | `initialize()` (строки 121-126), `_register_handlers()` (строки 210-215) |
| `sales_director_name` | `agent/telegram_agent.py` | `_sanitize_skill_content()`, `_build_system_prompt()` |
| `delay_short` | `telegram/telegram_service.py` | `_calculate_delay()` -- text < 50 chars |
| `delay_medium` | `telegram/telegram_service.py` | `_calculate_delay()` -- text 50-200 chars |
| `delay_long` | `telegram/telegram_service.py` | `_calculate_delay()` -- text > 200 chars |
| `max_messages_per_day_per_prospect` | `agent/telegram_agent.py` | `check_rate_limit()` |
| `working_hours` | `agent/telegram_agent.py` | `is_within_working_hours()` |
| `typing_simulation` | `telegram/telegram_service.py` | `send_message()` -> `_simulate_typing()` |
| `auto_follow_up_hours` | `daemon.py` | `process_follow_ups()` |
| `escalation_keywords` | `agent/telegram_agent.py` | `generate_response()` -- keyword matching |
| `escalation_notify` | `daemon.py` | `handle_incoming()` -> `service.notify_escalation()` |
| `include_knowledge_base` | `agent/telegram_agent.py` | `generate_response()` -- контроль KB контекста |
| `max_knowledge_tokens` | `agent/telegram_agent.py` | `generate_response()` -- лимит KB токенов |

### prospects.json

| Поле | Файл | Функция/Метод |
|------|------|---------------|
| `telegram_id` | `crm/prospect_manager.py` | `is_prospect()`, `get_prospect()`, `_normalize_id()` |
| `telegram_id` | `telegram/telegram_service.py` | `send_message()` -> `resolve_entity()` |
| `telegram_id` | `daemon.py` | `handle_incoming()` -- маршрутизация |
| `name` | `agent/telegram_agent.py` | `generate_initial_message()`, `generate_response()`, `generate_follow_up()` |
| `context` | `agent/telegram_agent.py` | `generate_initial_message()`, `generate_response()`, `generate_follow_up()` |
| `email` | `daemon.py` | `handle_incoming()` schedule action -- валидация и сохранение |
| `email` | `scheduling/scheduling_tool.py` | `book_meeting()` -- обязательная проверка |

### sales_slots.json

| Поле | Файл | Функция/Метод |
|------|------|---------------|
| `salesperson` | `scheduling/sales_calendar.py` | `generate_mock_slots()`, `_get_default_config()` |
| `timezone` | `scheduling/sales_calendar.py` | `_get_default_config()` (хранится для справки) |
| `working_hours` | `scheduling/sales_calendar.py` | `_get_default_config()` (хранится для справки) |
| `days_ahead` | `scheduling/sales_calendar.py` | `refresh_slots()`, `generate_mock_slots()` |
| `blocked_dates` | `scheduling/sales_calendar.py` | `generate_mock_slots()` -- пропуск дат |
| `slot_duration_minutes` | `scheduling/sales_calendar.py` | `_get_default_config()` |

### .env

| Переменная | Файл | Функция/Метод |
|------------|------|---------------|
| `ANTHROPIC_API_KEY` | `agent/telegram_agent.py` | `__init__()` -- создание Anthropic client |
| `DATABASE_URL` | `database/init.py` | `check_database_connection()`, `run_migrations()`, `init_database()` |
| `DATABASE_URL` | `scheduling/scheduled_action_manager.py` | `_get_pool()` -- пул подключений asyncpg |
| `REGISTRY_BOT_TOKEN` | `registry/registry_bot.py` | Инициализация Telegram bot |
| `CORPORATE_EMAIL_DOMAIN` | `registry/registry_bot.py` | Валидация email при регистрации |

### ~/.telegram_dl/config.json

| Поле | Файл | Функция/Метод |
|------|------|---------------|
| `api_id` | `telegram/telegram_fetch.py` | `get_client()` -- `TelegramClient(session, api_id, api_hash)` |
| `api_hash` | `telegram/telegram_fetch.py` | `get_client()` -- `TelegramClient(session, api_id, api_hash)` |
| `api_id` + `api_hash` | `telegram/telegram_fetch.py` | `is_configured()` -- проверка наличия обоих ключей |
