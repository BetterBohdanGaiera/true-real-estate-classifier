"""
Behavior Tests Package for Telegram Agent.

Tests for specific agent behaviors:
1. Message Batching - verifies 3 client messages result in 1 agent response
2. Wait Handling - verifies agent pauses when client asks to wait
3. Zoom Scheduling - verifies conversation ends with meeting booking and email invite

Usage:
    PYTHONPATH=src uv run python .claude/skills/testing/scripts/behavior_tests/run_behavior_tests.py --all --verbose
"""

from .behavior_scenarios import (
    BEHAVIOR_SCENARIOS,
    BATCHING_SCENARIO,
    WAIT_HANDLING_SCENARIO,
    ZOOM_SCHEDULING_SCENARIO,
    get_behavior_scenario_by_name,
)

from .behavior_verifiers import (
    BatchingVerifier,
    BatchingVerificationResult,
    WaitHandlingVerifier,
    WaitHandlingVerificationResult,
    ZoomSchedulingVerifier,
    ZoomSchedulingVerificationResult,
)

__all__ = [
    # Scenarios
    "BEHAVIOR_SCENARIOS",
    "BATCHING_SCENARIO",
    "WAIT_HANDLING_SCENARIO",
    "ZOOM_SCHEDULING_SCENARIO",
    "get_behavior_scenario_by_name",
    # Verifiers
    "BatchingVerifier",
    "BatchingVerificationResult",
    "WaitHandlingVerifier",
    "WaitHandlingVerificationResult",
    "ZoomSchedulingVerifier",
    "ZoomSchedulingVerificationResult",
]
