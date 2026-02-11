# Chat History from Telegram & Media Analysis Capabilities

## Objective

Two major changes to the Telegram sales bot:

1. **Use Telegram Chat Messages AS Conversation History** - Instead of relying on locally stored JSON, fetch actual chat history from Telegram via Telethon
2. **Analyze Client Voice Messages, Images, Videos** - Move beyond placeholder text to real media understanding

## Current Architecture

1. Telethon receives NewMessage event
2. Media detected by `media_detector.py`; voice transcribed by `elevenlabs.py`; other media gets placeholder text
3. Message recorded in `prospects.json` via `ProspectManager.record_response()`
4. `ProspectManager.get_conversation_context()` reads last 20 messages from JSON
5. `CLITelegramAgent.generate_response()` receives text context, calls `claude -p` CLI
6. Claude returns JSON action; daemon executes it

## New Files to Create

### 1. `src/telegram_sales_bot/temporal/chat_history_fetcher.py`
Fetches conversation context directly from Telegram API instead of local JSON.

- Uses `client.iter_messages(entity, limit=30)` to get raw Telethon messages
- Determines sender (agent vs prospect by comparing `msg.sender_id` to `bot_user_id`)
- For media messages: checks transcription cache first, falls back to placeholder
- Formats as: `[YYYY-MM-DD HH:MM] SenderName: text`
- Returns in chronological order (oldest first)
- Short-lived cache (5-10 seconds) to avoid redundant Telegram API fetches

### 2. `src/telegram_sales_bot/temporal/transcription_cache.py`
JSON-based cache that maps `(chat_id, message_id)` to analysis results.

- Bridges both changes: caches media analysis results for history fetcher
- Voice transcriptions, photo descriptions, video transcriptions all cached
- Used by chat_history_fetcher when encountering media in historical messages
- Written to when daemon processes new media messages
- Pydantic model: `TranscriptionCacheEntry` with message_id, chat_id, media_type, transcription

### 3. `src/telegram_sales_bot/integrations/media_analyzer.py`
Analyzes photos via Claude Code CLI, extracts audio from videos and transcribes.

- `analyze_photo()`: Downloads photo → calls `claude -p` CLI (Read tool reads image natively) → returns description
- `analyze_video()`: Downloads video → ffmpeg audio extraction → ElevenLabs transcription
- `analyze_video_note()`: Same as video but for circle messages (audio extraction sufficient)
- Uses Claude Code CLI with `claude-sonnet-4-20250514` for photo analysis (consistent with rest of codebase)
- Photo descriptions scoped to real estate context (1-2 sentences)
- Video size limit: 50MB max
- Graceful degradation: falls back to placeholders if analysis fails

## Existing Files to Modify

### 4. `src/telegram_sales_bot/core/models.py`
- Add `MediaAnalysisResult` model (media_type, original_text, analyzed_text, combined_text, analysis_method)
- Add `TranscriptionCacheEntry` model (message_id, telegram_chat_id, media_type, transcription, created_at)

### 5. `src/telegram_sales_bot/core/daemon.py`
Major changes:
- **Initialize new components** in `__init__()` and `initialize()`: chat_history_fetcher, media_analyzer, transcription_cache
- **Replace 4 `get_conversation_context()` calls** with chat_history_fetcher:
  - Line ~379: `_process_message_batch()`
  - Line ~947: `handle_incoming()` (non-batched path)
  - Line ~1076: `process_follow_ups()`
  - Line ~1147: `execute_scheduled_action()`
- **Update media handling in `handle_incoming()`** (~lines 846-876):
  - Photos: call `media_analyzer.analyze_photo()` + cache result
  - Videos: call `media_analyzer.analyze_video()` + cache result
  - Video notes: call `media_analyzer.analyze_video_note()` + cache result
  - All results cached via transcription_cache

### 6. Agent System Prompt (knowledge base)
Update media handling instructions to reflect new capabilities:
- Photos now include descriptions, react to content
- Videos/voice transcribed to text, treat as normal messages
- Sticker reactions can be action="wait"

## Implementation Batches

### Batch 1 (No dependencies - can be parallel)
- `models.py` changes (new Pydantic models)
- `transcription_cache.py` (new file, depends only on models)
- `media_analyzer.py` (new file, depends on elevenlabs + anthropic)

### Batch 2 (Depends on Batch 1)
- `chat_history_fetcher.py` (uses transcription_cache)

### Batch 3 (Depends on Batch 1 + 2)
- `daemon.py` modifications (integrates all new components)

## Key Design Decisions

1. **Hybrid approach**: Keep ProspectManager for metadata (status, email, timezone, BANT facts, session_id). Use Telegram API only for conversation context.
2. **Transcription cache is critical**: When fetching history from Telegram, historical media can't be cheaply re-analyzed. Cache bridges real-time analysis with history retrieval.
3. **No re-transcription of historical media**: If cache misses, show placeholder. Only new incoming messages get full analysis.
4. **Claude Sonnet for photo analysis**: Fast, cheap, sufficient quality for 1-2 sentence descriptions.
5. **ffmpeg for video audio**: System tool, async subprocess, OGG/Opus output (same format as Telegram voice).

## Potential Challenges

1. **Telegram rate limits**: iter_messages with limit=30 per response. Mitigate with short-lived cache.
2. **Photo analysis latency**: 2-5 seconds. Acceptable within message buffer wait time.
3. **Video processing latency**: 10-30 seconds for ffmpeg + transcription. Size/duration limits needed.
4. **ffmpeg in Docker**: Need `apt-get install ffmpeg` in Dockerfile.
5. **Fresh start without cache**: Historical media shows as placeholders. Acceptable degradation.
