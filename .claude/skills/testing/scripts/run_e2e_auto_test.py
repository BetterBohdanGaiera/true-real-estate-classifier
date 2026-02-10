#!/usr/bin/env python3
"""
Automated E2E Conversation Test via Real Telegram.

Extended version: Tests 8 critical agent behaviors including Snake methodology,
BANT qualification, objection handling, pain summary before Zoom, and scheduling.

Phases:
1. Initial Contact & Snake Light Entry
2. Wait Behavior (respects "wait 2 minutes")
3. ROI Question + "Bubble" Objection
4. BANT: Budget + Need + "Send Catalog" Objection
5. BANT: Authority + Timeline + "Leasehold" Objection
6. Pain Summary & Zoom Proposal
7. Timezone-Aware Scheduling & Email Collection
8. Meeting Booking & Calendar Validation

Usage:
    PYTHONPATH=src uv run python .claude/skills/testing/scripts/run_e2e_auto_test.py
"""
import asyncio
import json
import os
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

    msg_text = "Интересно, но сейчас занят. Можете написать через 2 минуты?"
    print(f"  [PROSPECT] {msg_text}")
    await player.send_message(AGENT_USERNAME, msg_text)
    result.messages.append(("PROSPECT", msg_text, _ts()))

    # Wait for acknowledgment
    print("  Waiting for acknowledgment (30s)...")
    ack = await player.wait_for_response(AGENT_USERNAME, timeout=30.0, poll_interval=1.0)
    if ack:
        print(f"  [AGENT] {ack}")
        result.messages.append(("AGENT", ack, _ts()))

    # Check silence for 100 seconds
    print("  Timing silence period (need >= 100s)...")
    silence_start = time.time()
    premature = await player.wait_for_response(AGENT_USERNAME, timeout=100.0, poll_interval=2.0)
    silence_duration = time.time() - silence_start

    if premature is not None:
        result.timing["seconds_silent"] = round(silence_duration, 1)
        result.details = f"Agent broke silence after {silence_duration:.0f}s (need >= 100s): {premature[:60]}"
        result.messages.append(("AGENT", premature, _ts()))
        result.passed = False
        print(f"  FAIL: {result.details}")
        return result

    result.timing["seconds_silent"] = round(silence_duration, 1)
    print(f"  Silent for {silence_duration:.0f}s - GOOD")

    # Wait for follow-up within 180s total
    remaining = 180.0 - silence_duration
    if remaining > 0:
        print(f"  Waiting for follow-up ({remaining:.0f}s remaining)...")
        followup = await player.wait_for_response(AGENT_USERNAME, timeout=remaining, poll_interval=2.0)
        total = time.time() - silence_start

        if followup:
            result.timing["seconds_until_followup"] = round(total, 1)
            result.messages.append(("AGENT", followup, _ts()))
            result.passed = True
            result.details = f"Silent for {silence_duration:.0f}s (>= 100s), follow-up at {total:.0f}s (<= 180s)"
            print(f"  [AGENT] {followup}")
            print(f"  PASS: {result.details}")
        else:
            result.timing["seconds_until_followup"] = round(total, 1)
            result.passed = False
            result.details = f"Silent for {silence_duration:.0f}s but no follow-up within 180s"
            print(f"  FAIL: {result.details}")
    else:
        result.passed = False
        result.details = "Silence consumed entire timeout"
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
# PHASE 4: BANT Budget + Need + "Send Catalog" Objection
# =============================================================================
async def phase4_budget_need_catalog(player: E2ETelegramPlayer) -> TestResult:
    result = TestResult(4, "BANT: Budget + Need + Catalog Deflection")
    print("\n" + "=" * 60)
    print("[PHASE 4] Testing budget handling, catalog deflection, no early Zoom...")
    print("=" * 60)

    # 4a: Budget + catalog request
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

    # 4b: Need clarification - pure investment
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
# PHASE 5: BANT Authority + Timeline + Leasehold Objection
# =============================================================================
async def phase5_authority_timeline_leasehold(player: E2ETelegramPlayer) -> TestResult:
    result = TestResult(5, "BANT: Authority + Timeline + Leasehold Objection")
    print("\n" + "=" * 60)
    print("[PHASE 5] Testing authority/timeline collection and leasehold objection...")
    print("=" * 60)

    # 5a: Authority + Leasehold objection
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

    # 5b: Timeline + Guarantees objection
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
# PHASE 6: Pain Summary & Zoom Proposal
# =============================================================================
async def phase6_pain_summary_zoom(player: E2ETelegramPlayer, phase5_last_msg: str) -> TestResult:
    result = TestResult(6, "Pain Summary & Zoom Proposal")
    print("\n" + "=" * 60)
    print("[PHASE 6] Checking pain summary and Zoom proposal quality...")
    print("=" * 60)

    # Check if the agent's last response (from phase 5b) already contained a Zoom proposal
    has_zoom_in_phase5 = _check_zoom_mention(phase5_last_msg)
    has_summary_in_phase5 = _contains_any(phase5_last_msg, [
        "итак", "резюмир", "подытож", "ваш запрос", "вас интерес",
        "бюджет", "апартамент", "инвестиц", "300", "надёжн", "гарант"
    ])

    if has_zoom_in_phase5:
        print(f"  Agent already proposed Zoom in Phase 5 response")
        print(f"  Checking if pain summary was included...")

        result.checks = {
            "zoom_proposed": True,
            "has_pain_summary": has_summary_in_phase5,
            "from_phase5": True,
        }

        if has_summary_in_phase5:
            result.passed = True
            result.details = "Pain summary + Zoom proposal found in Phase 5 response"
        else:
            result.passed = False
            result.details = "Zoom proposed in Phase 5 BUT without pain summary (anti-pattern #5: premature Zoom)"
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
# PHASE 7: Timezone-Aware Scheduling & Email Collection
# =============================================================================
async def phase7_timezone_email(player: E2ETelegramPlayer) -> TestResult:
    result = TestResult(7, "Timezone-Aware Scheduling & Email Collection")
    print("\n" + "=" * 60)
    print("[PHASE 7] Testing timezone & email collection...")
    print("=" * 60)

    # 7a: Accept Zoom, mention Warsaw
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

    # 7b: Send email
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

    # 7c: Pick a time
    await asyncio.sleep(2)
    msg_c = "Завтра в 10:00 по моему времени подойдёт"
    print(f"  [PROSPECT] {msg_c}")
    await player.send_message(AGENT_USERNAME, msg_c)
    result.messages.append(("PROSPECT", msg_c, _ts()))

    print("  Waiting for confirmation (60s)...")
    resp_c = await player.wait_for_response(AGENT_USERNAME, timeout=60.0, poll_interval=2.0)
    if resp_c is None:
        result.details = f"TZ: {'Y' if mentions_tz else 'N'}, Dual TZ: {'Y' if dual_tz else 'N'}, TIMEOUT on confirmation"
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
# PHASE 8: Meeting Booking & Calendar Validation
# =============================================================================
async def phase8_booking_calendar(player: E2ETelegramPlayer) -> TestResult:
    result = TestResult(8, "Meeting Booking & Calendar Validation")
    print("\n" + "=" * 60)
    print("[PHASE 8] Testing meeting booking & calendar...")
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
    print("  8 Phases: Snake + BANT + Objections + Scheduling")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    player = E2ETelegramPlayer(session_name="buddah_lucid")

    try:
        await player.connect()
        me = await player.get_me()
        print(f"Connected as: {me['first_name']} (@{me['username']})")

        results = []

        # NOTE: Chat cleanup and prospect reset must happen BEFORE the daemon
        # Docker container starts. The daemon sends initial outreach immediately
        # on startup, so deleting chat history here would race against the daemon
        # and delete the initial message Phase 1 is waiting for.
        # The calling workflow (telegram_conversation_manual_test) handles pre-cleanup.

        # Phase 1: Initial Contact
        r1 = await phase1_initial_contact(player)
        results.append(r1)

        # Phase 2: Wait Behavior
        r2 = await phase2_wait_behavior(player)
        results.append(r2)

        # Phase 3: ROI + Bubble Objection
        r3 = await phase3_roi_and_bubble(player)
        results.append(r3)

        # Phase 4: Budget + Need + Catalog Deflection
        r4 = await phase4_budget_need_catalog(player)
        results.append(r4)

        # Phase 5: Authority + Timeline + Leasehold Objection
        r5 = await phase5_authority_timeline_leasehold(player)
        results.append(r5)

        # Phase 6: Pain Summary & Zoom Proposal
        # Pass the last agent message from phase 5 to check
        phase5_last_agent_msg = ""
        for sender, text, _ in reversed(r5.messages):
            if sender == "AGENT":
                phase5_last_agent_msg = text
                break
        r6 = await phase6_pain_summary_zoom(player, phase5_last_agent_msg)
        results.append(r6)

        # Phase 7: Timezone & Email
        r7 = await phase7_timezone_email(player)
        results.append(r7)

        # Phase 8: Booking & Calendar
        r8 = await phase8_booking_calendar(player)
        results.append(r8)

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
            "bant_before_zoom": r4.checks.get("no_early_zoom", False),
            "pain_summary_before_zoom": r6.checks.get("has_pain_summary", False),
            "objections_with_empathy": r3.checks.get("shows_empathy", False) and r3.checks.get("no_devalue", False),
            "no_anti_patterns": r4.checks.get("catalog_deflected", False),
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
