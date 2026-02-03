"""
Conversation Evaluator for assessing conversation quality against
tone-of-voice principles and how-to-communicate methodology.

Uses Anthropic Agent SDK to provide structured feedback with detailed scoring.
"""

import sys
from pathlib import Path
from typing import Optional
import json

from pydantic import BaseModel

# Add ADW modules to path for Agent SDK access
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "adws"))

from adw_modules.adw_agent_sdk import (
    quick_prompt,
    AdhocPrompt,
    ModelName,
    SystemPromptConfig,
    SystemPromptMode,
)

# Support both package import and direct execution
try:
    from .conversation_simulator import ConversationResult, ConversationTurn
except ImportError:
    from conversation_simulator import ConversationResult, ConversationTurn


# =============================================================================
# Data Models
# =============================================================================


class ConversationAssessment(BaseModel):
    """
    Structured assessment of a conversation's quality.

    Based on tone-of-voice principles and how-to-communicate methodology
    for Bali real estate sales.
    """

    # Overall assessment
    overall_score: int  # 0-100
    what_went_well: list[str]  # 3-5 specific positives
    areas_for_improvement: list[str]  # 3-5 specific suggestions
    critical_issues: list[str]  # Empty if none

    # Detailed scores (0-10 each)
    personalization_score: int  # Used client name
    questions_score: int  # Ended with open questions
    value_first_score: int  # Explained value before asking
    bant_coverage: dict  # {"budget": bool, "authority": bool, "need": bool, "timeline": bool}
    zmeyka_adherence: int  # Followed Zmeyka methodology
    objection_handling: int  # Addressed objections properly

    # Binary checks
    zoom_close_attempt: bool  # Attempted to schedule
    message_length_appropriate: bool  # 2-5 sentences
    formal_language: bool  # Used "Вы"
    no_forbidden_topics: bool  # Didn't mention freehold for foreigners

    # Actions
    recommended_actions: list[str]  # Concrete next steps


# =============================================================================
# ConversationEvaluator - Uses Agent SDK for Quality Assessment
# =============================================================================


class ConversationEvaluator:
    """
    Uses Anthropic Agent SDK to evaluate conversation quality.

    Evaluates against:
    - 7 communication principles from tone-of-voice
    - BANT methodology (Budget, Authority, Need, Timeline)
    - Zmeyka methodology (Easy question, Reflect, Show expertise, Ask next)
    - Forbidden topics (freehold for foreigners)
    """

    def __init__(self) -> None:
        """Initialize evaluator with system prompt."""
        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        """Build evaluation criteria system prompt."""
        return """You are an expert sales coach evaluating conversations for a Bali real estate company.

EVALUATION CRITERIA (based on company guidelines):

1. PERSONALIZATION (0-10): Did agent use client's name? Personalize responses?

2. OPEN QUESTIONS (0-10): Did messages end with questions that advance dialogue?

3. VALUE-FIRST (0-10): Did agent explain value before asking for information?

4. BANT COVERAGE: Did agent discover Budget, Authority, Need, Timeline?
   - Budget: Did agent learn client's investment budget?
   - Authority: Did agent identify who makes the decision?
   - Need: Did agent understand if it's for living or investment?
   - Timeline: Did agent learn when client plans to purchase?

5. ZMEYKA METHODOLOGY (0-10):
   - Easy question first (establish rapport)
   - Reflect client's answer (show listening)
   - Show expertise with facts (not empty claims)
   - Ask next question (advance dialogue)

6. OBJECTION HANDLING (0-10): How well were objections addressed?
   - Did agent acknowledge concerns?
   - Did agent provide facts/data to address objections?
   - Did agent avoid being defensive?

7. ZOOM CLOSE: Did agent attempt to schedule a Zoom meeting?
   - Proposed specific times (not "when convenient")?
   - Explained value of the meeting?

8. MESSAGE LENGTH: Were messages 2-5 sentences (not too long)?

9. FORMAL LANGUAGE: Used "Вы" (formal you) in Russian?

10. FORBIDDEN TOPICS: Did NOT mention "freehold for foreigners" (legally impossible)?

KEY COMPANY USPs TO LOOK FOR:
- 140-point due diligence protocol
- Estate Market analytics software
- British capital management standards
- Positioning as "investment consultant" (not "realtor")

SCORING GUIDE:
- 90-100: Excellent - followed all principles, achieved goal
- 70-89: Good - minor issues, mostly effective
- 50-69: Average - several areas need improvement
- 30-49: Below average - significant issues
- 0-29: Poor - fundamental problems

Return ONLY valid JSON matching the ConversationAssessment schema."""

    async def evaluate(self, result: ConversationResult) -> ConversationAssessment:
        """
        Evaluate a conversation using Agent SDK quick_prompt.

        Args:
            result: ConversationResult from the simulator

        Returns:
            ConversationAssessment with detailed scoring
        """
        conversation_text = self._format_conversation(result.turns)

        user_prompt = f"""Analyze this sales conversation:

SCENARIO: {result.scenario_name}
PERSONA TYPE: {result.persona.name} ({result.persona.difficulty} difficulty)
OUTCOME: {result.outcome.value}
TOTAL TURNS: {result.total_turns}
ACTIONS USED: {result.agent_actions_used}
EMAIL COLLECTED: {result.email_collected}

CONVERSATION:
{conversation_text}

Evaluate against all criteria and return JSON with:
{{
  "overall_score": 0-100,
  "what_went_well": ["...", "...", "..."],
  "areas_for_improvement": ["...", "...", "..."],
  "critical_issues": ["..."],
  "personalization_score": 0-10,
  "questions_score": 0-10,
  "value_first_score": 0-10,
  "bant_coverage": {{"budget": bool, "authority": bool, "need": bool, "timeline": bool}},
  "zmeyka_adherence": 0-10,
  "objection_handling": 0-10,
  "zoom_close_attempt": bool,
  "message_length_appropriate": bool,
  "formal_language": bool,
  "no_forbidden_topics": bool,
  "recommended_actions": ["..."]
}}"""

        result_text = await quick_prompt(AdhocPrompt(
            prompt=user_prompt,
            model=ModelName.SONNET,
            system_prompt=SystemPromptConfig(
                mode=SystemPromptMode.OVERWRITE,
                system_prompt=self.system_prompt,
            ),
        ))

        # Parse JSON from response
        try:
            start = result_text.find('{')
            end = result_text.rfind('}') + 1
            if start != -1 and end > start:
                json_str = result_text[start:end]
                data = json.loads(json_str)
                return ConversationAssessment(**data)
            else:
                # No JSON found in response
                return self._default_assessment(
                    error="No JSON found in LLM response"
                )
        except json.JSONDecodeError as e:
            return self._default_assessment(
                error=f"JSON parse error: {str(e)}"
            )
        except ValueError as e:
            return self._default_assessment(
                error=f"Validation error: {str(e)}"
            )

    def _format_conversation(self, turns: list[ConversationTurn]) -> str:
        """Format conversation for evaluation."""
        lines = []
        for turn in turns:
            speaker = "AGENT" if turn.speaker == "agent" else "CLIENT"
            action = f" [{turn.action}]" if turn.action else ""
            lines.append(f"{speaker}{action}: {turn.message}")
        return "\n\n".join(lines)

    def _default_assessment(self, error: str) -> ConversationAssessment:
        """Return default assessment when parsing fails."""
        return ConversationAssessment(
            overall_score=0,
            what_went_well=[],
            areas_for_improvement=[],
            critical_issues=[f"Evaluation failed: {error}"],
            personalization_score=0,
            questions_score=0,
            value_first_score=0,
            bant_coverage={
                "budget": False,
                "authority": False,
                "need": False,
                "timeline": False,
            },
            zmeyka_adherence=0,
            objection_handling=0,
            zoom_close_attempt=False,
            message_length_appropriate=False,
            formal_language=False,
            no_forbidden_topics=True,
            recommended_actions=["Re-run evaluation after fixing errors"],
        )


# =============================================================================
# Test Entry Point
# =============================================================================

if __name__ == "__main__":
    import asyncio
    from datetime import datetime
    try:
        from .conversation_simulator import (
            PersonaDefinition,
            ConversationTurn,
            ConversationResult,
            ConversationOutcome,
        )
    except ImportError:
        from conversation_simulator import (
            PersonaDefinition,
            ConversationTurn,
            ConversationResult,
            ConversationOutcome,
        )

    async def test_evaluator():
        """Quick test of the conversation evaluator."""
        # Create a sample conversation result
        test_persona = PersonaDefinition(
            name="Test Persona",
            description="Test persona for evaluation",
            difficulty="medium",
            traits=["curious", "skeptical"],
            objections=["What about guarantees?"],
            goal="Test evaluation",
            language="ru",
        )

        test_turns = [
            ConversationTurn(
                turn_number=1,
                speaker="agent",
                message="Здравствуйте, Иван! Рад, что Вы заинтересовались недвижимостью на Бали. Какой тип инвестиции Вас интересует больше - для личного проживания или как инвестиция?",
                action="respond",
            ),
            ConversationTurn(
                turn_number=2,
                speaker="persona",
                message="Здравствуйте! Рассматриваю как инвестицию, но пока изучаю рынок.",
            ),
            ConversationTurn(
                turn_number=3,
                speaker="agent",
                message="Иван, понимаю Вас - изучение рынка это правильный подход. Наша компания использует собственную аналитическую систему Estate Market, которая показывает реальную заполняемость объектов. Какой бюджет Вы рассматриваете для инвестиции?",
                action="respond",
            ),
            ConversationTurn(
                turn_number=4,
                speaker="persona",
                message="Пока думаю в районе 200-300 тысяч долларов. А какая реальная доходность?",
            ),
        ]

        test_result = ConversationResult(
            scenario_name="Test Scenario",
            persona=test_persona,
            turns=test_turns,
            outcome=ConversationOutcome.INCONCLUSIVE,
            total_turns=4,
            duration_seconds=120.0,
            agent_actions_used={"respond": 2},
            email_collected=False,
            escalation_triggered=False,
        )

        evaluator = ConversationEvaluator()
        print("Evaluating test conversation...")
        assessment = await evaluator.evaluate(test_result)

        print(f"\nOverall Score: {assessment.overall_score}/100")
        print(f"\nWhat went well:")
        for item in assessment.what_went_well:
            print(f"  - {item}")
        print(f"\nAreas for improvement:")
        for item in assessment.areas_for_improvement:
            print(f"  - {item}")
        print(f"\nCritical issues: {assessment.critical_issues}")
        print(f"\nDetailed scores:")
        print(f"  Personalization: {assessment.personalization_score}/10")
        print(f"  Questions: {assessment.questions_score}/10")
        print(f"  Value First: {assessment.value_first_score}/10")
        print(f"  Zmeyka Adherence: {assessment.zmeyka_adherence}/10")
        print(f"  Objection Handling: {assessment.objection_handling}/10")
        print(f"\nBANT Coverage: {assessment.bant_coverage}")
        print(f"\nBinary checks:")
        print(f"  Zoom close attempt: {assessment.zoom_close_attempt}")
        print(f"  Message length appropriate: {assessment.message_length_appropriate}")
        print(f"  Formal language: {assessment.formal_language}")
        print(f"  No forbidden topics: {assessment.no_forbidden_topics}")

    asyncio.run(test_evaluator())
