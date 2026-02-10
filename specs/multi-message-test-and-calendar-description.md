# Implementation Plan: Multi-Message Test Phase + Client-Oriented Calendar Events

## Objective

1. **Add Multi-Message Flow Test Phase**: Insert new Phase 4 in E2E test for rapid message burst handling
2. **Improve Calendar Event Description**: Transform internal-notes style into professional client-facing invitation

## Files to Modify

1. `.claude/commands/telegram_conversation_automatic_test.md` - Add phase 4, renumber 4-8 → 5-9
2. `.claude/skills/testing/scripts/run_e2e_auto_test.py` - Add `phase4_multi_message_burst()`, renumber phases
3. `src/telegram_sales_bot/scheduling/tool.py` - Add `_generate_client_facing_description()`, update `book_meeting()`

## Task 1: Multi-Message Burst Test Phase

Insert after Phase 3 (ROI + Bubble), before current Phase 4 (Budget + Need).

Messages (1-2s apart):
1. "У меня несколько вопросов накопилось."
2. "Во-первых, сколько реально стоит содержание виллы?"
3. "Во-вторых, можно ли купить на компанию?"
4. "И еще - как с визами для длительного проживания?"

PASS criteria: Agent addresses 2+ topics, natural length, follow-up question.

## Task 2: Client-Oriented Calendar Events

Summary: "True Real Estate: Инвестиционная Консультация Бали" (contextual)
Description: Personalized value points + prominent Zoom link + professional sign-off
No internal notes visible to client.
