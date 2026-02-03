# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "asyncpg>=0.29.0",
#   "python-dotenv>=1.0.0",
#   "pydantic>=2.0.0",
# ]
# ///
"""
Test Result Manager - Database operations for stress test results and assessments.

Provides CRUD operations and analytics queries for the test_results and test_assessments
tables using asyncpg connection pool pattern.

Usage:
    from test_result_manager import (
        save_test_result,
        get_test_results,
        get_score_trends,
        get_scenario_analytics,
        close_pool,
    )
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import asyncpg
from dotenv import load_dotenv
from pydantic import BaseModel

# Setup paths for imports
SCRIPTS_DIR = Path(__file__).parent
SKILLS_BASE = SCRIPTS_DIR.parent.parent
PROJECT_ROOT = SKILLS_BASE.parent.parent

load_dotenv(PROJECT_ROOT / ".env")
load_dotenv()

# Support both package import and direct execution
try:
    from .conversation_simulator import ConversationResult
    from .conversation_evaluator import ConversationAssessment
except ImportError:
    from conversation_simulator import ConversationResult
    from conversation_evaluator import ConversationAssessment


# =============================================================================
# DATA MODELS
# =============================================================================


class TestResult(BaseModel):
    """A stored test result with assessment."""
    id: str  # UUID as string
    scenario_name: str
    persona_id: str
    outcome: str  # ConversationOutcome value
    overall_score: int
    total_turns: int
    duration_seconds: float
    email_collected: bool
    call_scheduled: bool
    agent_actions_used: dict
    timestamp: datetime
    created_at: datetime
    # Embedded assessment (from join)
    assessment: Optional[ConversationAssessment] = None


class DailyScoreSummary(BaseModel):
    """Daily aggregate scores for trend analysis."""
    date: str  # YYYY-MM-DD
    avg_score: float
    min_score: int
    max_score: int
    test_count: int
    pass_rate: float  # % with call_scheduled=true


class ScenarioAnalytics(BaseModel):
    """Analytics for a specific scenario."""
    scenario_name: str
    total_runs: int
    avg_score: float
    avg_duration: float
    pass_rate: float  # % with call_scheduled=true
    recent_trend: str  # "improving", "declining", "stable"


# =============================================================================
# CONNECTION POOL
# =============================================================================

_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    """
    Get or create the database connection pool.

    Returns:
        asyncpg.Pool: Database connection pool.

    Raises:
        RuntimeError: If DATABASE_URL environment variable is not set.
    """
    global _pool
    if _pool is None:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise RuntimeError("DATABASE_URL environment variable is not set")
        _pool = await asyncpg.create_pool(database_url, min_size=1, max_size=5)
    return _pool


async def close_pool() -> None:
    """Close the database connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


@asynccontextmanager
async def get_connection():
    """
    Get a database connection from the pool.

    Yields:
        asyncpg.Connection: Database connection.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield conn


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _row_to_test_result(row: asyncpg.Record, assessment: Optional[ConversationAssessment] = None) -> TestResult:
    """
    Convert a database row to a TestResult model.

    Args:
        row: Database record from asyncpg.
        assessment: Optional embedded ConversationAssessment.

    Returns:
        TestResult: Pydantic model instance.
    """
    result = dict(row)

    # Convert UUID to string
    if result.get("id") is not None:
        result["id"] = str(result["id"])

    # Parse JSONB agent_actions_used field
    if isinstance(result.get("agent_actions_used"), str):
        result["agent_actions_used"] = json.loads(result["agent_actions_used"])
    elif result.get("agent_actions_used") is None:
        result["agent_actions_used"] = {}

    # Add assessment if provided
    result["assessment"] = assessment

    return TestResult(**result)


def _row_to_assessment(row: asyncpg.Record) -> ConversationAssessment:
    """
    Convert a database row to a ConversationAssessment model.

    Args:
        row: Database record from asyncpg.

    Returns:
        ConversationAssessment: Pydantic model instance.
    """
    result = dict(row)

    # Parse JSONB bant_coverage field
    if isinstance(result.get("bant_coverage"), str):
        result["bant_coverage"] = json.loads(result["bant_coverage"])
    elif result.get("bant_coverage") is None:
        result["bant_coverage"] = {
            "budget": False,
            "authority": False,
            "need": False,
            "timeline": False,
        }

    # Convert TEXT[] arrays to Python lists
    for field in ["what_went_well", "areas_for_improvement", "critical_issues", "recommended_actions"]:
        if result.get(field) is None:
            result[field] = []
        elif isinstance(result.get(field), list):
            # Already a list from asyncpg
            pass

    return ConversationAssessment(**result)


def _row_to_daily_summary(row: asyncpg.Record) -> DailyScoreSummary:
    """
    Convert a database row to a DailyScoreSummary model.

    Args:
        row: Database record from asyncpg.

    Returns:
        DailyScoreSummary: Pydantic model instance.
    """
    result = dict(row)

    # Convert date to string if it's a date object
    if isinstance(result.get("date"), datetime):
        result["date"] = result["date"].strftime("%Y-%m-%d")
    elif hasattr(result.get("date"), "isoformat"):
        result["date"] = result["date"].isoformat()

    # Ensure pass_rate is a percentage (0-100)
    if result.get("pass_rate") is not None:
        result["pass_rate"] = float(result["pass_rate"]) * 100

    return DailyScoreSummary(**result)


# =============================================================================
# CRUD OPERATIONS
# =============================================================================


async def save_test_result(
    result: ConversationResult,
    assessment: ConversationAssessment
) -> str:
    """
    Save test result and assessment to database.

    Inserts a record into test_results and a linked record into test_assessments
    within a single transaction.

    Args:
        result: ConversationResult from test run.
        assessment: ConversationAssessment from evaluator.

    Returns:
        UUID string of created test_result record.

    Example:
        >>> from conversation_simulator import ConversationResult
        >>> from conversation_evaluator import ConversationAssessment
        >>> result_id = await save_test_result(result, assessment)
        >>> print(f"Saved as {result_id}")
    """
    async with get_connection() as conn:
        # Start transaction
        async with conn.transaction():
            # Insert test_result
            test_result_row = await conn.fetchrow(
                """
                INSERT INTO test_results (
                    scenario_name, persona_id, outcome, overall_score,
                    total_turns, duration_seconds, email_collected, call_scheduled,
                    agent_actions_used, timestamp, created_at
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, NOW(), NOW()
                )
                RETURNING id
                """,
                result.scenario_name,
                result.persona.name,
                result.outcome.value,
                assessment.overall_score,
                result.total_turns,
                result.duration_seconds,
                result.email_collected,
                assessment.zoom_close_attempt and result.email_collected,  # call_scheduled = zoom attempt + email
                json.dumps(result.agent_actions_used),
            )

            test_result_id = test_result_row["id"]

            # Insert test_assessment
            await conn.execute(
                """
                INSERT INTO test_assessments (
                    test_result_id, overall_score, what_went_well,
                    areas_for_improvement, critical_issues,
                    personalization_score, questions_score, value_first_score,
                    bant_coverage, zmeyka_adherence, objection_handling,
                    zoom_close_attempt, message_length_appropriate,
                    formal_language, no_forbidden_topics, recommended_actions,
                    created_at
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, NOW()
                )
                """,
                test_result_id,
                assessment.overall_score,
                assessment.what_went_well,
                assessment.areas_for_improvement,
                assessment.critical_issues,
                assessment.personalization_score,
                assessment.questions_score,
                assessment.value_first_score,
                json.dumps(assessment.bant_coverage),
                assessment.zmeyka_adherence,
                assessment.objection_handling,
                assessment.zoom_close_attempt,
                assessment.message_length_appropriate,
                assessment.formal_language,
                assessment.no_forbidden_topics,
                assessment.recommended_actions,
            )

            return str(test_result_id)


async def get_test_results(
    scenario_name: Optional[str] = None,
    limit: int = 100
) -> list[TestResult]:
    """
    Get test results, optionally filtered by scenario name.

    Results are returned with embedded assessments from a JOIN query.

    Args:
        scenario_name: Optional filter by scenario name.
        limit: Maximum number of results to return (default 100).

    Returns:
        List of TestResult objects with embedded assessments, ordered by timestamp descending.

    Example:
        >>> # Get all recent test results
        >>> results = await get_test_results()
        >>>
        >>> # Get results for a specific scenario
        >>> results = await get_test_results(scenario_name="Rapid Fire Burst")
        >>> for r in results:
        ...     print(f"{r.scenario_name}: {r.overall_score}/100")
    """
    async with get_connection() as conn:
        if scenario_name is not None:
            rows = await conn.fetch(
                """
                SELECT
                    tr.id, tr.scenario_name, tr.persona_id, tr.outcome,
                    tr.overall_score, tr.total_turns, tr.duration_seconds,
                    tr.email_collected, tr.call_scheduled, tr.agent_actions_used,
                    tr.timestamp, tr.created_at,
                    ta.overall_score as a_overall_score,
                    ta.what_went_well, ta.areas_for_improvement, ta.critical_issues,
                    ta.personalization_score, ta.questions_score, ta.value_first_score,
                    ta.bant_coverage, ta.zmeyka_adherence, ta.objection_handling,
                    ta.zoom_close_attempt, ta.message_length_appropriate,
                    ta.formal_language, ta.no_forbidden_topics, ta.recommended_actions
                FROM test_results tr
                LEFT JOIN test_assessments ta ON tr.id = ta.test_result_id
                WHERE tr.scenario_name = $1
                ORDER BY tr.timestamp DESC
                LIMIT $2
                """,
                scenario_name,
                limit,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT
                    tr.id, tr.scenario_name, tr.persona_id, tr.outcome,
                    tr.overall_score, tr.total_turns, tr.duration_seconds,
                    tr.email_collected, tr.call_scheduled, tr.agent_actions_used,
                    tr.timestamp, tr.created_at,
                    ta.overall_score as a_overall_score,
                    ta.what_went_well, ta.areas_for_improvement, ta.critical_issues,
                    ta.personalization_score, ta.questions_score, ta.value_first_score,
                    ta.bant_coverage, ta.zmeyka_adherence, ta.objection_handling,
                    ta.zoom_close_attempt, ta.message_length_appropriate,
                    ta.formal_language, ta.no_forbidden_topics, ta.recommended_actions
                FROM test_results tr
                LEFT JOIN test_assessments ta ON tr.id = ta.test_result_id
                ORDER BY tr.timestamp DESC
                LIMIT $1
                """,
                limit,
            )

        results = []
        for row in rows:
            # Extract assessment data if present
            assessment = None
            if row.get("a_overall_score") is not None:
                assessment = ConversationAssessment(
                    overall_score=row["a_overall_score"],
                    what_went_well=row["what_went_well"] or [],
                    areas_for_improvement=row["areas_for_improvement"] or [],
                    critical_issues=row["critical_issues"] or [],
                    personalization_score=row["personalization_score"],
                    questions_score=row["questions_score"],
                    value_first_score=row["value_first_score"],
                    bant_coverage=json.loads(row["bant_coverage"]) if isinstance(row["bant_coverage"], str) else row["bant_coverage"],
                    zmeyka_adherence=row["zmeyka_adherence"],
                    objection_handling=row["objection_handling"],
                    zoom_close_attempt=row["zoom_close_attempt"],
                    message_length_appropriate=row["message_length_appropriate"],
                    formal_language=row["formal_language"],
                    no_forbidden_topics=row["no_forbidden_topics"],
                    recommended_actions=row["recommended_actions"] or [],
                )

            # Build TestResult from the row
            test_result = TestResult(
                id=str(row["id"]),
                scenario_name=row["scenario_name"],
                persona_id=row["persona_id"],
                outcome=row["outcome"],
                overall_score=row["overall_score"],
                total_turns=row["total_turns"],
                duration_seconds=row["duration_seconds"],
                email_collected=row["email_collected"],
                call_scheduled=row["call_scheduled"],
                agent_actions_used=json.loads(row["agent_actions_used"]) if isinstance(row["agent_actions_used"], str) else row["agent_actions_used"] or {},
                timestamp=row["timestamp"],
                created_at=row["created_at"],
                assessment=assessment,
            )
            results.append(test_result)

        return results


async def get_score_trends(days: int = 30) -> list[DailyScoreSummary]:
    """
    Get daily score trends for the last N days.

    Aggregates test results by day to show score trends over time.

    Args:
        days: Number of days to look back (default 30).

    Returns:
        List of DailyScoreSummary objects, ordered by date descending.

    Example:
        >>> trends = await get_score_trends(days=7)
        >>> for day in trends:
        ...     print(f"{day.date}: avg={day.avg_score:.1f}, tests={day.test_count}")
    """
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT
                DATE(timestamp) as date,
                AVG(overall_score)::FLOAT as avg_score,
                MIN(overall_score) as min_score,
                MAX(overall_score) as max_score,
                COUNT(*) as test_count,
                AVG(CASE WHEN call_scheduled THEN 1.0 ELSE 0.0 END)::FLOAT as pass_rate
            FROM test_results
            WHERE timestamp >= NOW() - INTERVAL '%s days'
            GROUP BY DATE(timestamp)
            ORDER BY date DESC
            """ % days,
        )

        results = []
        for row in rows:
            summary = DailyScoreSummary(
                date=row["date"].isoformat() if hasattr(row["date"], "isoformat") else str(row["date"]),
                avg_score=round(row["avg_score"], 2),
                min_score=row["min_score"],
                max_score=row["max_score"],
                test_count=row["test_count"],
                pass_rate=round(row["pass_rate"] * 100, 2),  # Convert to percentage
            )
            results.append(summary)

        return results


async def get_scenario_analytics(scenario_name: str) -> ScenarioAnalytics:
    """
    Get analytics for a specific scenario.

    Calculates aggregate statistics and determines recent trend (improving/declining/stable).

    Args:
        scenario_name: Name of the scenario to analyze.

    Returns:
        ScenarioAnalytics with aggregate statistics and trend analysis.

    Raises:
        ValueError: If no test results exist for the specified scenario.

    Example:
        >>> analytics = await get_scenario_analytics("Rapid Fire Burst")
        >>> print(f"Scenario: {analytics.scenario_name}")
        >>> print(f"Total runs: {analytics.total_runs}")
        >>> print(f"Avg score: {analytics.avg_score:.1f}")
        >>> print(f"Trend: {analytics.recent_trend}")
    """
    async with get_connection() as conn:
        # Get aggregate stats
        stats_row = await conn.fetchrow(
            """
            SELECT
                COUNT(*) as total_runs,
                AVG(overall_score)::FLOAT as avg_score,
                AVG(duration_seconds)::FLOAT as avg_duration,
                AVG(CASE WHEN call_scheduled THEN 1.0 ELSE 0.0 END)::FLOAT as pass_rate
            FROM test_results
            WHERE scenario_name = $1
            """,
            scenario_name,
        )

        if stats_row["total_runs"] == 0:
            raise ValueError(f"No test results found for scenario: {scenario_name}")

        # Calculate trend by comparing recent vs older results
        # Recent = last 7 days, older = 8-30 days ago
        trend_row = await conn.fetchrow(
            """
            WITH recent AS (
                SELECT AVG(overall_score)::FLOAT as avg_score
                FROM test_results
                WHERE scenario_name = $1
                  AND timestamp >= NOW() - INTERVAL '7 days'
            ),
            older AS (
                SELECT AVG(overall_score)::FLOAT as avg_score
                FROM test_results
                WHERE scenario_name = $1
                  AND timestamp >= NOW() - INTERVAL '30 days'
                  AND timestamp < NOW() - INTERVAL '7 days'
            )
            SELECT
                recent.avg_score as recent_avg,
                older.avg_score as older_avg
            FROM recent, older
            """,
            scenario_name,
        )

        # Determine trend
        recent_avg = trend_row["recent_avg"]
        older_avg = trend_row["older_avg"]

        if recent_avg is None or older_avg is None:
            # Not enough data to determine trend
            trend = "stable"
        else:
            diff = recent_avg - older_avg
            if diff > 5:  # More than 5 points improvement
                trend = "improving"
            elif diff < -5:  # More than 5 points decline
                trend = "declining"
            else:
                trend = "stable"

        return ScenarioAnalytics(
            scenario_name=scenario_name,
            total_runs=stats_row["total_runs"],
            avg_score=round(stats_row["avg_score"], 2),
            avg_duration=round(stats_row["avg_duration"], 2),
            pass_rate=round(stats_row["pass_rate"] * 100, 2),  # Convert to percentage
            recent_trend=trend,
        )


async def get_all_scenario_names() -> list[str]:
    """
    Get all unique scenario names from test results.

    Returns:
        List of scenario names, ordered alphabetically.

    Example:
        >>> scenarios = await get_all_scenario_names()
        >>> for name in scenarios:
        ...     print(name)
    """
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT scenario_name
            FROM test_results
            ORDER BY scenario_name
            """
        )

        return [row["scenario_name"] for row in rows]


async def delete_old_test_results(days: int = 90) -> int:
    """
    Delete old test results for cleanup.

    Also deletes associated assessments due to CASCADE delete.

    Args:
        days: Delete results older than this many days (default 90).

    Returns:
        Number of test results deleted.

    Example:
        >>> deleted = await delete_old_test_results(days=90)
        >>> print(f"Deleted {deleted} old test results")
    """
    async with get_connection() as conn:
        result = await conn.execute(
            """
            DELETE FROM test_results
            WHERE timestamp < NOW() - INTERVAL '%s days'
            """ % days,
        )

        # Parse "DELETE N" result string to get count
        if result:
            parts = result.split()
            if len(parts) >= 2:
                return int(parts[1])
        return 0


async def get_test_result_by_id(result_id: str) -> Optional[TestResult]:
    """
    Get a single test result by ID with its assessment.

    Args:
        result_id: UUID of the test result (as string).

    Returns:
        TestResult if found, None otherwise.

    Example:
        >>> result = await get_test_result_by_id("550e8400-e29b-41d4-a716-446655440000")
        >>> if result:
        ...     print(f"Score: {result.overall_score}")
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                tr.id, tr.scenario_name, tr.persona_id, tr.outcome,
                tr.overall_score, tr.total_turns, tr.duration_seconds,
                tr.email_collected, tr.call_scheduled, tr.agent_actions_used,
                tr.timestamp, tr.created_at,
                ta.overall_score as a_overall_score,
                ta.what_went_well, ta.areas_for_improvement, ta.critical_issues,
                ta.personalization_score, ta.questions_score, ta.value_first_score,
                ta.bant_coverage, ta.zmeyka_adherence, ta.objection_handling,
                ta.zoom_close_attempt, ta.message_length_appropriate,
                ta.formal_language, ta.no_forbidden_topics, ta.recommended_actions
            FROM test_results tr
            LEFT JOIN test_assessments ta ON tr.id = ta.test_result_id
            WHERE tr.id = $1
            """,
            uuid.UUID(result_id),
        )

        if not row:
            return None

        # Extract assessment data if present
        assessment = None
        if row.get("a_overall_score") is not None:
            assessment = ConversationAssessment(
                overall_score=row["a_overall_score"],
                what_went_well=row["what_went_well"] or [],
                areas_for_improvement=row["areas_for_improvement"] or [],
                critical_issues=row["critical_issues"] or [],
                personalization_score=row["personalization_score"],
                questions_score=row["questions_score"],
                value_first_score=row["value_first_score"],
                bant_coverage=json.loads(row["bant_coverage"]) if isinstance(row["bant_coverage"], str) else row["bant_coverage"],
                zmeyka_adherence=row["zmeyka_adherence"],
                objection_handling=row["objection_handling"],
                zoom_close_attempt=row["zoom_close_attempt"],
                message_length_appropriate=row["message_length_appropriate"],
                formal_language=row["formal_language"],
                no_forbidden_topics=row["no_forbidden_topics"],
                recommended_actions=row["recommended_actions"] or [],
            )

        return TestResult(
            id=str(row["id"]),
            scenario_name=row["scenario_name"],
            persona_id=row["persona_id"],
            outcome=row["outcome"],
            overall_score=row["overall_score"],
            total_turns=row["total_turns"],
            duration_seconds=row["duration_seconds"],
            email_collected=row["email_collected"],
            call_scheduled=row["call_scheduled"],
            agent_actions_used=json.loads(row["agent_actions_used"]) if isinstance(row["agent_actions_used"], str) else row["agent_actions_used"] or {},
            timestamp=row["timestamp"],
            created_at=row["created_at"],
            assessment=assessment,
        )
