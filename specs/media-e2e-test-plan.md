# Media E2E Test Plan: Voice + Image Location Identification

## Objective

Add a new E2E test phase that validates the agent's ability to:
1. Transcribe a voice message from the client
2. Analyze an image (Tegallalang Rice Terraces = Ubud)
3. Identify the Bali location from the image
4. Explain the area and continue sales qualification

## Files to Modify

### 1. `e2e_telegram_player.py` - Add `send_file()` method
- New method wrapping Telethon's `client.send_file()`
- Supports `voice=True` for .ogg files, regular file send for images
- Pattern follows existing `send_message()`

### 2. `run_e2e_auto_test.py` - Add Phase 4 + renumber phases
- Insert new **Phase 4: Media Message Analysis (Voice + Image)**
- Renumber existing phases 4-9 → 5-10
- Update `main()` orchestration, methodology compliance, summary
- New phase sends: voice (.ogg) → 2.5s delay → image (.png) → wait 120s for response
- PASS criteria: identifies Ubud + provides area info + continues conversation

### 3. `agent_system_prompt.md` - Add location identification instruction
- Add line about identifying Bali locations from photos (rice terraces, temples, beaches)
- Reference knowledge base for area details

### 4. `media_analyzer.py` - Enhance PHOTO_ANALYSIS_PROMPT
- Add sentence asking Claude to name specific Bali landmarks when identifiable

## Implementation Batches

### Batch 1 (No dependencies - parallel)
- `e2e_telegram_player.py` - Add `send_file()` method
- `media_analyzer.py` - Enhance PHOTO_ANALYSIS_PROMPT
- `agent_system_prompt.md` - Add location identification instruction

### Batch 2 (Depends on Batch 1 - player must have send_file)
- `run_e2e_auto_test.py` - Add Phase 4 + renumber all phases

## Test Media Files
- `data/media_for_test/response.ogg` - Voice message (client asking about area)
- `data/media_for_test/image.png` - Tegallalang Rice Terraces (Ubud landmark)

## PASS/FAIL Criteria for New Phase
1. `identifies_ubud`: Response contains "убуд" or "ubud"
2. `has_area_info`: Response contains area description keywords
3. `continues_conversation`: Response has follow-up question or engagement
