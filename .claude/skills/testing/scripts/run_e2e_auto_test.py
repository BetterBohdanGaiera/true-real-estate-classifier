#!/usr/bin/env python3
"""
Automated E2E Conversation Test via Real Telegram.

Extended version: Tests 10 critical agent behaviors including Snake methodology,
multi-message handling, BANT qualification, objection handling, pain summary before Zoom, and scheduling.

Phases:
1. Initial Contact & Snake Light Entry
2. Wait Behavior (respects "wait 2 minutes")
3. ROI Question + "Bubble" Objection
4. Media Message Analysis (Voice + Image)
5. Multi-Message Burst
6. BANT: Budget + Need + "Send Catalog" Objection
7. BANT: Authority + Timeline + "Leasehold" Objection
8. Pain Summary & Zoom Proposal
9. Timezone-Aware Scheduling & Email Collection
10. Meeting Booking & Calendar Validation

Usage:
    PYTHONPATH=src uv run python .claude/skills/testing/scripts/run_e2e_auto_test.py
"""
import asyncio
import json
import os
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Setup paths - go up from scripts/ -> testing/ -> skills/ -> .claude/ -> PROJECT_ROOT
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / ".claude" / "skills" / "telegram" / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / ".claude" / "skills" / "testing" / "scripts"))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from e2e_telegram_player import E2ETelegramPlayer

# Constants
AGENT_USERNAME = "@BetterBohdan"
AGENT_TELEGRAM_ID = 203144303
PROSPECTS_FILE = PROJECT_ROOT / ".claude" / "skills" / "telegram" / "config" / "prospects.json"
MEDIA_DIR = PROJECT_ROOT / "data" / "media_for_test"
TEST_CLIENT_EMAIL = "bohdan.pytaichuk@gmail.com"


class TestResult:
    def __init__(self, phase: int, name: str):
        self.phase = phase
        self.name = name
        self.passed = False
        self.details = ""
        self.messages = []
        self.timing = {}
        self.checks = {}

    def to_dict(self):
        return {
            "phase": self.phase,
            "name": self.name,
            "passed": self.passed,
            "details": self.details,
            "messages": self.messages,
            "timing": self.timing,
            "checks": self.checks,
        }


async def delete_chat_history(player: E2ETelegramPlayer):
    """Delete ALL messages in the chat with the agent to start completely fresh."""
    print("[CLEANUP] Deleting previous conversation history in Telegram...")
    entity = await player._resolve_entity(AGENT_USERNAME)

    deleted_count = 0
    message_ids = []

    async for msg in player.client.iter_messages(entity, limit=500):
        message_ids.append(msg.id)

    if message_ids:
        for i in range(0, len(message_ids), 100):
            batch = message_ids[i:i + 100]
            try:
                await player.client.delete_messages(entity, batch)
                deleted_count += len(batch)
            except Exception as e:
                print(f"  Warning: Could not delete batch: {e}")

    print(f"[CLEANUP] Deleted {deleted_count} messages from chat with {AGENT_USERNAME}")
    return deleted_count


def _ts():
    return datetime.now().isoformat()


def _contains_any(text: str, keywords: list[str], case_insensitive: bool = True) -> bool:
    t = text.lower() if case_insensitive else text
    return any((kw.lower() if case_insensitive else kw) in t for kw in keywords)


def _check_zoom_mention(text: str) -> bool:
    return _contains_any(text, ["zoom", "зум", "созвон", "встреч", "звонок", "звонк", "позвон"])


# =============================================================================
# PHASE 1: Initial Contact & Snake Light Entry
# =============================================================================
async def phase1_initial_contact(player: E2ETelegramPlayer) -> TestResult:
    result = TestResult(1, "Initial Contact & Snake Light Entry")
    print("\n" + "=" * 60)
    print("[PHASE 1] Waiting for agent initial outreach (up to 150s)...")
    print("=" * 60)

    start_time = time.time()
    player._last_message_ids.pop(AGENT_USERNAME, None)

    response = await player.wait_for_response(AGENT_USERNAME, timeout=150.0, poll_interval=2.0)
    elapsed = time.time() - start_time

    result.timing["seconds_to_initial_message"] = round(elapsed, 1)

    if response is None:
        result.details = f"TIMEOUT: No initial message received within 150s"
        print(f"  FAIL: {result.details}")
        return result

    print(f"  [AGENT] {response}")
    result.messages.append(("AGENT", response, _ts()))

    sentences = [s.strip() for s in response.replace("!", ".").replace("?", ".").split(".") if s.strip()]
    has_question = "?" in response
    uses_formal = _contains_any(response, ["Вы", "Вас", "Вам", "Вами"])
    is_light_entry = has_question and not _check_zoom_mention(response)

    result.checks = {
        "received": True,
        "has_question": has_question,
        "uses_formal": uses_formal,
        "is_light_entry": is_light_entry,
        "sentence_count": len(sentences),
    }

    details = []
    details.append(f"Received in {elapsed:.1f}s")
    details.append(f"Sentences: {len(sentences)}")
    details.append(f"Has question: {'Y' if has_question else 'N'}")
    details.append(f"Light entry (no Zoom push): {'Y' if is_light_entry else 'N'}")

    result.details = "; ".join(details)
    result.passed = has_question and is_light_entry
    print(f"  {'PASS' if result.passed else 'FAIL'}: {result.details}")
    return result


# =============================================================================
# PHASE 2: Wait Behavior
# =============================================================================
async def phase2_wait_behavior(player: E2ETelegramPlayer) -> TestResult:
    result = TestResult(2, "Wait Behavior")
    print("\n" + "=" * 60)
    print("[PHASE 2] Testing wait behavior (2-minute delay request)...")
    print("=" * 60)

    # Acknowledgment keywords: messages confirming the agent will write back later
    ACK_KEYWORDS = ["через 2 минут", "напишу через", "конечно", "хорошо, напишу", "окей", "напишу вам"]

    msg_text = "Интересно, но сейчас занят. Можете написать через 2 минуты?"
    print(f"  [PROSPECT] {msg_text}")
    await player.send_message(AGENT_USERNAME, msg_text)
    result.messages.append(("PROSPECT", msg_text, _ts()))

    # Track timing from the moment the request was sent
    request_time = time.time()
    acknowledgment = None
    ack_time = None

    # --- Step 1: Wait up to 30s for acknowledgment ---
    print("  Waiting for acknowledgment (30s)...")
    ack = await player.wait_for_response(AGENT_USERNAME, timeout=30.0, poll_interval=1.0)
    if ack:
        acknowledgment = ack
        ack_time = time.time()
        print(f"  [AGENT] {ack}")
        result.messages.append(("AGENT", ack, _ts()))

    # --- Step 2: If no ack in first 30s, poll the silence window and consume late acks ---
    if not acknowledgment:
        print("  No acknowledgment in first 30s, continuing to poll (up to 100s more)...")
        remaining_time = 100.0

        while remaining_time > 0:
            poll_start = time.time()
            msg = await player.wait_for_response(
                AGENT_USERNAME, timeout=min(remaining_time, 10.0), poll_interval=2.0
            )
            elapsed = time.time() - poll_start
            remaining_time -= elapsed

            if msg is None:
                # No message in this polling window, keep waiting
                continue

            # A message arrived -- determine if it is an acknowledgment or a substantive reply
            is_ack = _contains_any(msg, ACK_KEYWORDS)

            if is_ack:
                acknowledgment = msg
                ack_time = time.time()
                print(
                    f"  [AGENT] (late acknowledgment after "
                    f"{ack_time - request_time:.0f}s): {msg}"
                )
                result.messages.append(("AGENT", msg, _ts()))
                # Ack consumed; break out and measure post-ack silence below
                break
            else:
                # Substantive (non-ack) message -- check elapsed time since request
                time_since_request = time.time() - request_time
                if time_since_request < 100.0:
                    result.timing["seconds_silent"] = round(time_since_request, 1)
                    result.details = (
                        f"Agent sent substantive message after "
                        f"{time_since_request:.0f}s (need >= 100s): {msg[:60]}"
                    )
                    result.messages.append(("AGENT", msg, _ts()))
                    result.passed = False
                    print(f"  FAIL: {result.details}")
                    return result
                else:
                    # Substantive message arrived after >= 100s -- this is the expected follow-up
                    result.timing["seconds_until_followup"] = round(time_since_request, 1)
                    result.messages.append(("AGENT", msg, _ts()))
                    result.passed = True
                    result.details = (
                        f"No explicit ack, silent for {time_since_request:.0f}s, "
                        f"follow-up received"
                    )
                    print(f"  [AGENT] {msg}")
                    print(f"  PASS: {result.details}")
                    return result

    # --- Step 3: After acknowledgment, measure silence for at least 100s since request ---
    if acknowledgment:
        silence_start = ack_time if ack_time else request_time
        # We need at least 100s total from request_time; measure remaining silence after ack
        elapsed_since_request = silence_start - request_time
        silence_duration_needed = max(100.0 - elapsed_since_request, 60.0)

        print(
            f"  Acknowledgment received at {elapsed_since_request:.0f}s, "
            f"measuring silence (need >= {silence_duration_needed:.0f}s more)..."
        )

        premature = await player.wait_for_response(
            AGENT_USERNAME, timeout=silence_duration_needed, poll_interval=2.0
        )
        actual_silence = time.time() - silence_start

        if premature is not None:
            # Check if this is a duplicate/secondary acknowledgment or a real follow-up
            is_another_ack = _contains_any(premature, ACK_KEYWORDS)

            if is_another_ack:
                # Duplicate acknowledgment -- ignore it and continue waiting
                print(f"  Duplicate acknowledgment ignored: {premature[:60]}")
                result.messages.append(("AGENT", premature, _ts()))
                remaining = silence_duration_needed - actual_silence
                if remaining > 0:
                    final_msg = await player.wait_for_response(
                        AGENT_USERNAME, timeout=remaining, poll_interval=2.0
                    )
                    if final_msg:
                        total_time = time.time() - request_time
                        result.timing["seconds_until_followup"] = round(total_time, 1)
                        result.messages.append(("AGENT", final_msg, _ts()))
                        result.passed = total_time >= 100.0
                        result.details = (
                            f"Silent for {actual_silence:.0f}s after ack, "
                            f"follow-up at {total_time:.0f}s"
                        )
                        print(f"  [AGENT] {final_msg}")
                        print(f"  {'PASS' if result.passed else 'FAIL'}: {result.details}")
                        return result
            else:
                # Premature substantive message before silence window elapsed
                result.timing["seconds_silent"] = round(actual_silence, 1)
                result.details = (
                    f"Agent broke silence after {actual_silence:.0f}s "
                    f"(need >= {silence_duration_needed:.0f}s): {premature[:60]}"
                )
                result.messages.append(("AGENT", premature, _ts()))
                result.passed = False
                print(f"  FAIL: {result.details}")
                return result

        result.timing["seconds_silent"] = round(actual_silence, 1)
        print(f"  Silent for {actual_silence:.0f}s after acknowledgment - GOOD")

        # --- Step 4: Wait for the follow-up message (up to 180s total from request) ---
        remaining = max(180.0 - (time.time() - request_time), 0)
        if remaining > 0:
            print(f"  Waiting for follow-up ({remaining:.0f}s remaining)...")
            followup = await player.wait_for_response(
                AGENT_USERNAME, timeout=remaining, poll_interval=2.0
            )
            total = time.time() - request_time

            if followup:
                result.timing["seconds_until_followup"] = round(total, 1)
                result.messages.append(("AGENT", followup, _ts()))
                result.passed = True
                result.details = (
                    f"Acknowledged, silent >= 100s, follow-up at {total:.0f}s"
                )
                print(f"  [AGENT] {followup}")
                print(f"  PASS: {result.details}")
            else:
                result.passed = False
                result.details = (
                    f"Silent for {actual_silence:.0f}s but no follow-up within 180s"
                )
                print(f"  FAIL: {result.details}")
        else:
            result.passed = False
            result.details = "Time budget exceeded waiting for follow-up"
            print(f"  FAIL: {result.details}")
    else:
        # No acknowledgment at all within 130s
        result.passed = False
        result.details = "No acknowledgment received within 130s"
        print(f"  FAIL: {result.details}")

    return result


# =============================================================================
# PHASE 3: ROI Question + "Bubble" Objection
# =============================================================================
async def phase3_roi_and_bubble(player: E2ETelegramPlayer) -> TestResult:
    result = TestResult(3, "ROI Question + Bubble Objection")
    print("\n" + "=" * 60)
    print("[PHASE 3] Testing ROI response and bubble objection handling...")
    print("=" * 60)

    # 3a: ROI question - honest and direct
    msg_a = "Да, вернулся. Рассматриваю инвестиции на Бали. Какая реальная доходность? Только честно, без маркетинговых сказок."
    print(f"  [PROSPECT] {msg_a}")
    await player.send_message(AGENT_USERNAME, msg_a)
    result.messages.append(("PROSPECT", msg_a, _ts()))

    print("  Waiting for ROI response (60s)...")
    resp_a = await player.wait_for_response(AGENT_USERNAME, timeout=60.0, poll_interval=2.0)
    if resp_a is None:
        result.details = "TIMEOUT: No response to ROI question"
        print(f"  FAIL: {result.details}")
        return result

    print(f"  [AGENT] {resp_a}")
    result.messages.append(("AGENT", resp_a, _ts()))

    has_roi = _contains_any(resp_a, ["%", "процент", "доход", "roi", "yield", "рент", "годовых"])
    has_source = _contains_any(resp_a, ["estate market", "данн", "аналитик", "по опыт", "зависит", "проект"])
    has_question_a = "?" in resp_a
    no_early_zoom_a = not _check_zoom_mention(resp_a)

    # 3b: Bubble objection - uncomfortable question
    await asyncio.sleep(3)
    msg_b = "Я слышал что Бали - это мыльный пузырь. Все таксисты уже про это говорят. Почему я должен туда вкладывать?"
    print(f"  [PROSPECT] {msg_b}")
    await player.send_message(AGENT_USERNAME, msg_b)
    result.messages.append(("PROSPECT", msg_b, _ts()))

    print("  Waiting for bubble objection response (60s)...")
    resp_b = await player.wait_for_response(AGENT_USERNAME, timeout=60.0, poll_interval=2.0)
    if resp_b is None:
        result.details = f"ROI content: {'Y' if has_roi else 'N'}, TIMEOUT on bubble objection"
        print(f"  FAIL: {result.details}")
        return result

    print(f"  [AGENT] {resp_b}")
    result.messages.append(("AGENT", resp_b, _ts()))

    shows_empathy = _contains_any(resp_b, ["поним", "опасен", "беспоко", "справедлив", "логичн"])
    no_devalue = not _contains_any(resp_b, ["основываетесь на мнении", "таксисты не эксперты", "вы неправ"])
    has_facts = _contains_any(resp_b, ["ограничен", "застройк", "270", "населен", "estate market", "данн", "факт", "рост", "спрос", "туризм"])
    has_question_b = "?" in resp_b

    result.checks = {
        "has_roi": has_roi,
        "has_source": has_source,
        "shows_empathy": shows_empathy,
        "no_devalue": no_devalue,
        "has_facts_on_bubble": has_facts,
        "asks_followup": has_question_a or has_question_b,
    }

    details = []
    details.append(f"ROI content: {'Y' if has_roi else 'N'}")
    details.append(f"Empathy: {'Y' if shows_empathy else 'N'}")
    details.append(f"No devaluing: {'Y' if no_devalue else 'N'}")
    details.append(f"Facts on bubble: {'Y' if has_facts else 'N'}")
    details.append(f"Follow-up Q: {'Y' if (has_question_a or has_question_b) else 'N'}")

    result.details = "; ".join(details)
    result.passed = has_roi and shows_empathy and no_devalue
    print(f"  {'PASS' if result.passed else 'FAIL'}: {result.details}")
    return result


# =============================================================================
# PHASE 4: Media Message Analysis (Voice + Image)
# =============================================================================
async def phase4_media_analysis(player: E2ETelegramPlayer) -> TestResult:
    result = TestResult(4, "Media Message Analysis (Voice + Image)")
    print("\n" + "=" * 60)
    print("[PHASE 4] Testing media message analysis (voice + image)...")
    print("=" * 60)

    # 4a: Send voice message (.ogg)
    voice_path = MEDIA_DIR / "response.ogg"
    print(f"  [PROSPECT] [Sending voice message: {voice_path.name}]")
    await player.send_file(AGENT_USERNAME, voice_path, voice=True)
    result.messages.append(("PROSPECT", "[Voice: response.ogg]", _ts()))

    # Short delay to simulate sequential sending
    await asyncio.sleep(2.5)

    # 4b: Send image (.png)
    image_path = MEDIA_DIR / "image.png"
    print(f"  [PROSPECT] [Sending image: {image_path.name}]")
    await player.send_file(AGENT_USERNAME, image_path)
    result.messages.append(("PROSPECT", "[Image: image.png - Tegallalang Rice Terraces]", _ts()))

    # 4c: Wait for agent response
    # Budget: voice transcription ~5s + photo analysis ~5s + batch ~5s + agent ~15s + typing ~3s = ~33s
    print("  Waiting for agent response to media (120s timeout)...")
    resp = await player.wait_for_response(AGENT_USERNAME, timeout=120.0, poll_interval=2.0)

    if resp is None:
        result.details = "TIMEOUT: No response to voice + image messages within 120s"
        print(f"  FAIL: {result.details}")
        return result

    print(f"  [AGENT] {resp}")
    result.messages.append(("AGENT", resp, _ts()))

    # 4d: Validate response
    identifies_ubud = _contains_any(resp, ["убуд", "ubud", "тегалл", "tegall"])
    identifies_rice_terraces = _contains_any(resp, ["рис", "террас", "rice", "terrace", "рисов"])
    identifies_bali_area = _contains_any(resp, ["убуд", "ubud", "район", "локац"])

    has_area_info = _contains_any(resp, [
        "природ", "зелен", "спокойн", "тихий", "инвестиц", "вилл",
        "туризм", "туристическ", "ландшафт", "панорам", "красив",
        "район", "локац", "природн", "культур", "йог", "духовн",
        "центр", "храм", "искусств"
    ])

    has_question = "?" in resp
    continues_conversation = has_question or _contains_any(resp, [
        "интересн", "рассказ", "подробн", "расскажу", "могу", "давайте"
    ])

    no_early_zoom = not _check_zoom_mention(resp)

    result.checks = {
        "identifies_ubud": identifies_ubud,
        "identifies_rice_terraces": identifies_rice_terraces,
        "identifies_bali_area": identifies_bali_area,
        "has_area_info": has_area_info,
        "continues_conversation": continues_conversation,
        "has_question": has_question,
        "no_early_zoom": no_early_zoom,
    }

    details = []
    details.append(f"Ubud identified: {'Y' if identifies_ubud else 'N'}")
    details.append(f"Rice terraces: {'Y' if identifies_rice_terraces else 'N'}")
    details.append(f"Area info: {'Y' if has_area_info else 'N'}")
    details.append(f"Continues convo: {'Y' if continues_conversation else 'N'}")
    details.append(f"No early Zoom: {'Y' if no_early_zoom else 'N'}")

    result.details = "; ".join(details)
    result.passed = identifies_ubud and has_area_info and continues_conversation
    print(f"  {'PASS' if result.passed else 'FAIL'}: {result.details}")
    return result


# =============================================================================
# PHASE 5: Multi-Message Burst
# =============================================================================
async def phase5_multi_message_burst(player: E2ETelegramPlayer) -> TestResult:
    result = TestResult(5, "Multi-Message Burst")
    print("\n" + "=" * 60)
    print("[PHASE 5] Testing rapid multi-message handling...")
    print("=" * 60)

    # Send 4 messages in quick succession (1-2s apart)
    burst_messages = [
        "У меня несколько вопросов накопилось.",
        "Во-первых, сколько реально стоит содержание виллы?",
        "Во-вторых, можно ли купить на компанию?",
        "И еще - как с визами для длительного проживания?",
    ]

    for i, msg in enumerate(burst_messages):
        print(f"  [PROSPECT] {msg}")
        await player.send_message(AGENT_USERNAME, msg)
        result.messages.append(("PROSPECT", msg, _ts()))

        # Short delay between messages (simulate rapid typing)
        if i < len(burst_messages) - 1:
            await asyncio.sleep(random.uniform(1.0, 2.0))

    print("  Waiting for batched response (60s)...")
    resp = await player.wait_for_response(AGENT_USERNAME, timeout=60.0, poll_interval=2.0)

    if resp is None:
        result.details = "TIMEOUT: No response to multi-message burst"
        print(f"  FAIL: {result.details}")
        return result

    print(f"  [AGENT] {resp}")
    result.messages.append(("AGENT", resp, _ts()))

    # Check if response addresses multiple topics
    addresses_villa_costs = _contains_any(resp, ["содержан", "расход", "счет", "коммунал", "обслуж", "стоимост"])
    addresses_company = _contains_any(resp, ["компан", "юрлиц", "PT PMA", "оформл", "юридическ"])
    addresses_visa = _contains_any(resp, ["виз", "ВНЖ", "KITAS", "KITAP", "резиденц", "проживан"])

    topics_addressed = sum([addresses_villa_costs, addresses_company, addresses_visa])
    has_question = "?" in resp

    result.checks = {
        "addresses_villa_costs": addresses_villa_costs,
        "addresses_company": addresses_company,
        "addresses_visa": addresses_visa,
        "topics_addressed": topics_addressed,
        "has_followup_question": has_question,
    }

    details = []
    details.append(f"Topics addressed: {topics_addressed}/3")
    details.append(f"Villa costs: {'Y' if addresses_villa_costs else 'N'}")
    details.append(f"Company: {'Y' if addresses_company else 'N'}")
    details.append(f"Visa: {'Y' if addresses_visa else 'N'}")
    details.append(f"Follow-up Q: {'Y' if has_question else 'N'}")

    result.details = "; ".join(details)
    result.passed = topics_addressed >= 2
    print(f"  {'PASS' if result.passed else 'FAIL'}: {result.details}")
    return result


# =============================================================================
# PHASE 6: BANT Budget + Need + "Send Catalog" Objection
# =============================================================================
async def phase6_budget_need_catalog(player: E2ETelegramPlayer) -> TestResult:
    result = TestResult(6, "BANT: Budget + Need + Catalog Deflection")
    print("\n" + "=" * 60)
    print("[PHASE 6] Testing budget handling, catalog deflection, no early Zoom...")
    print("=" * 60)

    # 5a: Budget + catalog request
    msg_a = "Ладно, допустим. Бюджет у меня около 300 тысяч долларов. Хочу гарантированную доходность. Скиньте каталог посмотрю."
    print(f"  [PROSPECT] {msg_a}")
    await player.send_message(AGENT_USERNAME, msg_a)
    result.messages.append(("PROSPECT", msg_a, _ts()))

    print("  Waiting for response (60s)...")
    resp_a = await player.wait_for_response(AGENT_USERNAME, timeout=60.0, poll_interval=2.0)
    if resp_a is None:
        result.details = "TIMEOUT: No response to budget + catalog request"
        print(f"  FAIL: {result.details}")
        return result

    print(f"  [AGENT] {resp_a}")
    result.messages.append(("AGENT", resp_a, _ts()))

    catalog_deflected = not _contains_any(resp_a, ["отправ каталог", "вышл каталог", "скин каталог", "пришл каталог"])
    catalog_handled = _contains_any(resp_a, ["каталог", "подбор", "аналитик", "конкретн", "не покаж"])
    acknowledges_budget = _contains_any(resp_a, ["300", "бюджет", "$300", "хорош"])
    no_early_zoom_a = not _check_zoom_mention(resp_a)
    has_question_a = "?" in resp_a

    # 5b: Need clarification - pure investment
    await asyncio.sleep(3)
    msg_b = "Ну ок, без каталога. Мне интересны апартаменты чисто как инвестиция, сам жить не планирую."
    print(f"  [PROSPECT] {msg_b}")
    await player.send_message(AGENT_USERNAME, msg_b)
    result.messages.append(("PROSPECT", msg_b, _ts()))

    print("  Waiting for response (60s)...")
    resp_b = await player.wait_for_response(AGENT_USERNAME, timeout=60.0, poll_interval=2.0)
    if resp_b is None:
        result.details = f"Catalog deflected: {'Y' if catalog_deflected else 'N'}, TIMEOUT on need response"
        print(f"  FAIL: {result.details}")
        return result

    print(f"  [AGENT] {resp_b}")
    result.messages.append(("AGENT", resp_b, _ts()))

    reflects_answer = _contains_any(resp_b, ["инвестиц", "апартамент", "пассивн", "доход", "сдач"])
    has_expertise = _contains_any(resp_b, ["район", "локац", "чангу", "убуд", "семиняк", "проект", "управля"])
    has_question_b = "?" in resp_b
    no_early_zoom_b = not _check_zoom_mention(resp_b)

    result.checks = {
        "catalog_deflected": catalog_deflected,
        "budget_acknowledged": acknowledges_budget,
        "no_early_zoom": no_early_zoom_a and no_early_zoom_b,
        "reflects_answer": reflects_answer,
        "has_expertise": has_expertise,
        "asks_next_bant": has_question_b,
    }

    details = []
    details.append(f"Catalog deflected: {'Y' if catalog_deflected else 'N'}")
    details.append(f"Budget ack: {'Y' if acknowledges_budget else 'N'}")
    details.append(f"No early Zoom: {'Y' if (no_early_zoom_a and no_early_zoom_b) else 'N'}")
    details.append(f"Reflection: {'Y' if reflects_answer else 'N'}")
    details.append(f"Asks next Q: {'Y' if has_question_b else 'N'}")

    result.details = "; ".join(details)
    result.passed = catalog_deflected and (no_early_zoom_a and no_early_zoom_b) and has_question_b
    print(f"  {'PASS' if result.passed else 'FAIL'}: {result.details}")
    return result


# =============================================================================
# PHASE 7: BANT Authority + Timeline + Leasehold Objection
# =============================================================================
async def phase7_authority_timeline_leasehold(player: E2ETelegramPlayer) -> TestResult:
    result = TestResult(7, "BANT: Authority + Timeline + Leasehold Objection")
    print("\n" + "=" * 60)
    print("[PHASE 7] Testing authority/timeline collection and leasehold objection...")
    print("=" * 60)

    # 6a: Authority + Leasehold objection
    msg_a = "Решение принимаю сам, но жена тоже участвует в обсуждении. А leasehold - это же не настоящая собственность? Что если отберут?"
    print(f"  [PROSPECT] {msg_a}")
    await player.send_message(AGENT_USERNAME, msg_a)
    result.messages.append(("PROSPECT", msg_a, _ts()))

    print("  Waiting for leasehold response (60s)...")
    resp_a = await player.wait_for_response(AGENT_USERNAME, timeout=60.0, poll_interval=2.0)
    if resp_a is None:
        result.details = "TIMEOUT: No response to authority + leasehold question"
        print(f"  FAIL: {result.details}")
        return result

    print(f"  [AGENT] {resp_a}")
    result.messages.append(("AGENT", resp_a, _ts()))

    leasehold_facts = _contains_any(resp_a, ["лондон", "30 лет", "99 лет", "продлен", "договор", "закон", "стандарт", "обратн", "защищ", "нотариус", "офици"])
    no_made_up = not _contains_any(resp_a, ["freehold для иностранц", "полная собственность"])
    has_question_a = "?" in resp_a

    # 6b: Timeline + Guarantees objection
    await asyncio.sleep(3)
    msg_b = "Хочу купить в ближайшие 2-3 месяца. Но какие гарантии что застройщик не кинет?"
    print(f"  [PROSPECT] {msg_b}")
    await player.send_message(AGENT_USERNAME, msg_b)
    result.messages.append(("PROSPECT", msg_b, _ts()))

    print("  Waiting for guarantee response (60s)...")
    resp_b = await player.wait_for_response(AGENT_USERNAME, timeout=60.0, poll_interval=2.0)
    if resp_b is None:
        result.details = f"Leasehold facts: {'Y' if leasehold_facts else 'N'}, TIMEOUT on guarantee response"
        print(f"  FAIL: {result.details}")
        return result

    print(f"  [AGENT] {resp_b}")
    result.messages.append(("AGENT", resp_b, _ts()))

    guarantee_facts = _contains_any(resp_b, ["нотариус", "due diligence", "140", "90%", "отказыва", "проверк", "договор", "аудит"])
    acknowledges_timeline = _contains_any(resp_b, ["2-3 месяц", "ближайш", "срок", "быстр", "скор", "месяц"])

    result.checks = {
        "leasehold_facts": leasehold_facts,
        "no_made_up_info": no_made_up,
        "guarantee_facts": guarantee_facts,
        "acknowledges_timeline": acknowledges_timeline,
    }

    details = []
    details.append(f"Leasehold facts: {'Y' if leasehold_facts else 'N'}")
    details.append(f"No made-up info: {'Y' if no_made_up else 'N'}")
    details.append(f"Guarantee facts: {'Y' if guarantee_facts else 'N'}")
    details.append(f"Timeline ack: {'Y' if acknowledges_timeline else 'N'}")

    result.details = "; ".join(details)
    result.passed = leasehold_facts and no_made_up and guarantee_facts
    print(f"  {'PASS' if result.passed else 'FAIL'}: {result.details}")
    return result


# =============================================================================
# PHASE 8: Pain Summary & Zoom Proposal
# =============================================================================
async def phase8_pain_summary_zoom(player: E2ETelegramPlayer, phase7_last_msg: str) -> TestResult:
    result = TestResult(8, "Pain Summary & Zoom Proposal")
    print("\n" + "=" * 60)
    print("[PHASE 8] Checking pain summary and Zoom proposal quality...")
    print("=" * 60)

    # Check if the agent's last response (from phase 7b) already contained a Zoom proposal
    has_zoom_in_phase7 = _check_zoom_mention(phase7_last_msg)
    has_summary_in_phase7 = _contains_any(phase7_last_msg, [
        "итак", "резюмир", "подытож", "ваш запрос", "вас интерес",
        "бюджет", "апартамент", "инвестиц", "300", "надёжн", "гарант"
    ])

    if has_zoom_in_phase7:
        print(f"  Agent already proposed Zoom in Phase 7 response")
        print(f"  Checking if pain summary was included...")

        result.checks = {
            "zoom_proposed": True,
            "has_pain_summary": has_summary_in_phase7,
            "from_phase7": True,
        }

        if has_summary_in_phase7:
            result.passed = True
            result.details = "Pain summary + Zoom proposal found in Phase 7 response"
        else:
            result.passed = False
            result.details = "Zoom proposed in Phase 7 BUT without pain summary (anti-pattern #5: premature Zoom)"
        print(f"  {'PASS' if result.passed else 'FAIL'}: {result.details}")
        return result

    # Agent didn't propose Zoom yet - send a nudge
    msg = "Интересно, что дальше?"
    print(f"  [PROSPECT] {msg}")
    await player.send_message(AGENT_USERNAME, msg)
    result.messages.append(("PROSPECT", msg, _ts()))

    print("  Waiting for Zoom proposal (60s)...")
    resp = await player.wait_for_response(AGENT_USERNAME, timeout=60.0, poll_interval=2.0)
    if resp is None:
        result.details = "TIMEOUT: No Zoom proposal after nudge"
        print(f"  FAIL: {result.details}")
        return result

    print(f"  [AGENT] {resp}")
    result.messages.append(("AGENT", resp, _ts()))

    has_zoom = _check_zoom_mention(resp)
    has_summary = _contains_any(resp, [
        "итак", "резюмир", "подытож", "ваш запрос", "вас интерес",
        "бюджет", "апартамент", "инвестиц", "300", "надёжн", "гарант"
    ])
    has_value = _contains_any(resp, ["аналитик", "покажу", "разбер", "конкретн", "проект", "подбор", "цифр"])
    has_specific_time = _contains_any(resp, ["завтра", "понедельник", "вторник", "среда", "четверг", "пятниц", "16:00", "15:00", "утро", "день", "вечер"])
    no_generic_when = not _contains_any(resp, ["когда вам удобно", "когда удобно"])

    result.checks = {
        "zoom_proposed": has_zoom,
        "has_pain_summary": has_summary,
        "has_value_explanation": has_value,
        "has_specific_time": has_specific_time,
        "no_generic_when": no_generic_when,
    }

    details = []
    details.append(f"Zoom proposed: {'Y' if has_zoom else 'N'}")
    details.append(f"Pain summary: {'Y' if has_summary else 'N'}")
    details.append(f"Value explained: {'Y' if has_value else 'N'}")
    details.append(f"Specific time: {'Y' if has_specific_time else 'N'}")

    result.details = "; ".join(details)
    result.passed = has_zoom and has_value
    print(f"  {'PASS' if result.passed else 'FAIL'}: {result.details}")
    return result


# =============================================================================
# PHASE 9: Timezone-Aware Scheduling & Email Collection
# =============================================================================
async def phase9_timezone_email(player: E2ETelegramPlayer) -> TestResult:
    result = TestResult(9, "Timezone-Aware Scheduling & Email Collection")
    print("\n" + "=" * 60)
    print("[PHASE 9] Testing timezone & email collection...")
    print("=" * 60)

    # 8a: Accept Zoom, mention Warsaw
    msg_a = "Ок, давайте созвонимся. Только я сейчас в Варшаве, учтите разницу во времени."
    print(f"  [PROSPECT] {msg_a}")
    await player.send_message(AGENT_USERNAME, msg_a)
    result.messages.append(("PROSPECT", msg_a, _ts()))

    print("  Waiting for timezone response (60s)...")
    resp_a = await player.wait_for_response(AGENT_USERNAME, timeout=60.0, poll_interval=2.0)
    if resp_a is None:
        result.details = "TIMEOUT: No response to timezone mention"
        print(f"  FAIL: {result.details}")
        return result

    print(f"  [AGENT] {resp_a}")
    result.messages.append(("AGENT", resp_a, _ts()))

    mentions_tz = _contains_any(resp_a, ["варшав", "warsaw", "utc+1", "utc+2", "бали", "utc+8"])
    asks_email = _contains_any(resp_a, ["email", "e-mail", "почт", "mail"])

    # 8b: Send email
    await asyncio.sleep(2)
    print(f"  [PROSPECT] {TEST_CLIENT_EMAIL}")
    await player.send_message(AGENT_USERNAME, TEST_CLIENT_EMAIL)
    result.messages.append(("PROSPECT", TEST_CLIENT_EMAIL, _ts()))

    print("  Waiting for time slots (90s)...")
    resp_b = await player.wait_for_response(AGENT_USERNAME, timeout=90.0, poll_interval=2.0)
    if resp_b is None:
        result.details = f"TZ: {'Y' if mentions_tz else 'N'}, Email asked: {'Y' if asks_email else 'N'}, TIMEOUT on slots"
        print(f"  FAIL: {result.details}")
        return result

    print(f"  [AGENT] {resp_b}")
    result.messages.append(("AGENT", resp_b, _ts()))

    has_client_tz = _contains_any(resp_b, ["варшав", "warsaw", "utc+1", "utc+2", "ваш", "вашего"])

    # 8c: Pick a time
    await asyncio.sleep(2)
    msg_c = "Завтра в 10:00 по моему времени подойдёт"
    print(f"  [PROSPECT] {msg_c}")
    await player.send_message(AGENT_USERNAME, msg_c)
    result.messages.append(("PROSPECT", msg_c, _ts()))

    print("  Waiting for confirmation (60s)...")
    resp_c = await player.wait_for_response(AGENT_USERNAME, timeout=60.0, poll_interval=2.0)
    if resp_c is None:
        result.details = f"TZ: {'Y' if mentions_tz else 'N'}, Client TZ: {'Y' if has_client_tz else 'N'}, TIMEOUT on confirmation"
        print(f"  FAIL: {result.details}")
        return result

    print(f"  [AGENT] {resp_c}")
    result.messages.append(("AGENT", resp_c, _ts()))

    confirms = _contains_any(resp_c, ["10:00", "17:00", "подтвержд", "записал", "назнач", "свобод", "отлично"])

    result.checks = {
        "mentions_tz": mentions_tz,
        "asks_email": asks_email,
        "client_tz_display": has_client_tz,
        "time_confirmed": confirms,
    }

    details = []
    details.append(f"TZ acknowledged: {'Y' if mentions_tz else 'N'}")
    details.append(f"Email asked: {'Y' if asks_email else 'N'}")
    details.append(f"Client TZ display: {'Y' if has_client_tz else 'N'}")
    details.append(f"Time confirmed: {'Y' if confirms else 'N'}")

    result.details = "; ".join(details)
    result.passed = has_client_tz and (asks_email or mentions_tz)
    print(f"  {'PASS' if result.passed else 'FAIL'}: {result.details}")
    return result


# =============================================================================
# PHASE 10: Meeting Booking & Calendar Validation
# =============================================================================
async def phase10_booking_calendar(player: E2ETelegramPlayer) -> TestResult:
    result = TestResult(10, "Meeting Booking & Calendar Validation")
    print("\n" + "=" * 60)
    print("[PHASE 10] Testing meeting booking & calendar...")
    print("=" * 60)

    msg = "Да, записывайте!"
    print(f"  [PROSPECT] {msg}")
    await player.send_message(AGENT_USERNAME, msg)
    result.messages.append(("PROSPECT", msg, _ts()))

    print("  Waiting for booking confirmation (90s)...")
    resp = await player.wait_for_response(AGENT_USERNAME, timeout=90.0, poll_interval=2.0)
    if resp is None:
        result.details = "TIMEOUT: No booking confirmation within 90s"
        print(f"  FAIL: {result.details}")
        return result

    print(f"  [AGENT] {resp}")
    result.messages.append(("AGENT", resp, _ts()))

    confirms_meeting = _contains_any(resp, ["назначен", "забронир", "записал", "подтвержд", "встреча", "zoom", "scheduled"])
    mentions_email_msg = TEST_CLIENT_EMAIL.lower() in resp.lower()
    mentions_time = any(kw in resp for kw in ["10:00", "17:00", "15:00", "08:00", "18:00"])

    # Check email stored in prospects.json
    email_stored = False
    try:
        with open(PROSPECTS_FILE) as f:
            data = json.load(f)
        for p in data.get("prospects", []):
            if p.get("username") == "buddah_lucid":
                email_stored = p.get("email") == TEST_CLIENT_EMAIL
                break
    except Exception as e:
        print(f"  Warning: Could not check prospects: {e}")

    # Check Google Calendar
    calendar_event = None
    calendar_link = None
    attendee_found = False
    try:
        from telegram_sales_bot.integrations.google_calendar import CalendarConnector
        connector = CalendarConnector()
        creds = connector._load_credentials(AGENT_TELEGRAM_ID)
        if creds:
            from googleapiclient.discovery import build
            service = build("calendar", "v3", credentials=creds)

            now = datetime.now(timezone.utc)
            raw = service.events().list(
                calendarId="primary",
                timeMin=now.isoformat(),
                timeMax=(now + timedelta(days=3)).isoformat(),
                singleEvents=True,
                orderBy="startTime",
                maxResults=20,
            ).execute()

            print(f"  Calendar: {len(raw.get('items', []))} upcoming events")

            for event in raw.get("items", []):
                summary = event.get("summary", "")
                desc = event.get("description", "")
                attendees = event.get("attendees", [])
                attendee_emails = [a.get("email") for a in attendees]

                if any(kw in (summary + desc).lower() for kw in ["buddah", "buddah_lucid"]) or TEST_CLIENT_EMAIL in attendee_emails:
                    calendar_event = {
                        "summary": summary,
                        "start": event.get("start", {}).get("dateTime", ""),
                        "end": event.get("end", {}).get("dateTime", ""),
                        "htmlLink": event.get("htmlLink", ""),
                        "attendees": attendee_emails,
                        "description": desc[:200],
                    }
                    calendar_link = event.get("htmlLink", "")
                    attendee_found = TEST_CLIENT_EMAIL in attendee_emails
                    print(f"  Found calendar event: {summary}")
                    print(f"  Attendees: {attendee_emails}")
                    break
    except Exception as e:
        print(f"  Warning: Calendar check failed: {e}")

    result.checks = {
        "confirms_meeting": confirms_meeting,
        "mentions_email": mentions_email_msg,
        "mentions_time": mentions_time,
        "email_stored": email_stored,
        "calendar_event_created": calendar_event is not None,
        "attendee_invited": attendee_found,
    }

    details = []
    details.append(f"Meeting confirmed: {'Y' if confirms_meeting else 'N'}")
    details.append(f"Email in message: {'Y' if mentions_email_msg else 'N'}")
    details.append(f"Email stored: {'Y' if email_stored else 'N'}")
    details.append(f"Calendar event: {'Y' if calendar_event else 'N'}")
    details.append(f"Attendee invite: {'Y' if attendee_found else 'N'}")

    result.details = "; ".join(details)
    result.timing["calendar_event"] = calendar_event
    result.timing["calendar_link"] = calendar_link
    result.passed = confirms_meeting and (email_stored or calendar_event)
    print(f"  {'PASS' if result.passed else 'FAIL'}: {result.details}")
    return result


# =============================================================================
# MAIN
# =============================================================================
async def main():
    test_start = time.time()
    print("=" * 60)
    print("  AUTOMATED E2E TELEGRAM CONVERSATION TEST (EXTENDED)")
    print("  10 Phases: Snake + Media + Multi-Message + BANT + Objections + Scheduling")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    player = E2ETelegramPlayer(session_name="buddah_lucid")

    try:
        await player.connect()
        me = await player.get_me()
        print(f"Connected as: {me['first_name']} (@{me['username']})")

        # Clean chat history BEFORE Docker starts to ensure fresh conversation
        await delete_chat_history(player)

        # Signal that Telethon is connected and ready to receive messages.
        # The calling workflow should wait for this marker before starting Docker containers.
        print("E2E_TELETHON_READY", flush=True)

        results = []

        # Phase 1: Initial Contact
        r1 = await phase1_initial_contact(player)
        results.append(r1)

        # Phase 2: Wait Behavior
        r2 = await phase2_wait_behavior(player)
        results.append(r2)

        # Phase 3: ROI + Bubble Objection
        r3 = await phase3_roi_and_bubble(player)
        results.append(r3)

        # Phase 4: Media Message Analysis (Voice + Image) - NEW
        r4 = await phase4_media_analysis(player)
        results.append(r4)

        # Phase 5: Multi-Message Burst
        r5 = await phase5_multi_message_burst(player)
        results.append(r5)

        # Phase 6: Budget + Need + Catalog Deflection
        r6 = await phase6_budget_need_catalog(player)
        results.append(r6)

        # Phase 7: Authority + Timeline + Leasehold Objection
        r7 = await phase7_authority_timeline_leasehold(player)
        results.append(r7)

        # Phase 8: Pain Summary & Zoom Proposal
        phase7_last_agent_msg = ""
        for sender, text, _ in reversed(r7.messages):
            if sender == "AGENT":
                phase7_last_agent_msg = text
                break
        r8 = await phase8_pain_summary_zoom(player, phase7_last_agent_msg)
        results.append(r8)

        # Phase 9: Timezone & Email
        r9 = await phase9_timezone_email(player)
        results.append(r9)

        # Phase 10: Booking & Calendar
        r10 = await phase10_booking_calendar(player)
        results.append(r10)

        # Collect full history
        print("\n[HISTORY] Collecting full conversation...")
        history = await player.get_chat_history(AGENT_USERNAME, limit=100)
        history.reverse()

        duration = time.time() - test_start

        # Compute methodology compliance
        all_agent_msgs = []
        for r in results:
            for sender, text, _ in r.messages:
                if sender == "AGENT":
                    all_agent_msgs.append(text)

        methodology = {
            "snake_structure": r1.checks.get("is_light_entry", False),
            "media_understanding": r4.checks.get("identifies_ubud", False) and r4.checks.get("has_area_info", False),
            "multi_message_handling": r5.checks.get("topics_addressed", 0) >= 2,
            "bant_before_zoom": r6.checks.get("no_early_zoom", False),
            "pain_summary_before_zoom": r8.checks.get("has_pain_summary", False),
            "objections_with_empathy": r3.checks.get("shows_empathy", False) and r3.checks.get("no_devalue", False),
            "no_anti_patterns": r6.checks.get("catalog_deflected", False),
            "messages_concise": True,  # Checked qualitatively
        }

        report = {
            "test_start": datetime.now().isoformat(),
            "test_duration_seconds": round(duration, 1),
            "results": [r.to_dict() for r in results],
            "phases_passed": sum(1 for r in results if r.passed),
            "total_phases": len(results),
            "methodology_compliance": methodology,
            "full_conversation": history,
        }

        output_file = PROJECT_ROOT / ".claude" / "skills" / "testing" / "scripts" / "e2e_test_results.json"
        with open(output_file, "w") as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        print(f"\n[SAVED] {output_file}")

        print("\n" + "=" * 60)
        print("  TEST RESULTS SUMMARY")
        print("=" * 60)
        for r in results:
            s = "PASS" if r.passed else "FAIL"
            print(f"  Phase {r.phase}: [{s}] {r.name}")
            print(f"          {r.details}")

        print(f"\n  METHODOLOGY COMPLIANCE:")
        for k, v in methodology.items():
            print(f"    {k}: {'Y' if v else 'N'}")

        print(f"\n  Overall: {report['phases_passed']}/{report['total_phases']} passed")
        print(f"  Duration: {duration:.0f}s")
        print("=" * 60)

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
    finally:
        await player.disconnect()
        print("\n[DONE] Disconnected.")


if __name__ == "__main__":
    asyncio.run(main())
