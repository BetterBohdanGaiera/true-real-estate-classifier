"""
Testing skill module - Conversation simulation and evaluation infrastructure.

This module provides tools for testing sales agent conversation behavior
through simulated personas, structured quality evaluation, and stress testing.

Components:
    - ConversationSimulator: Orchestrates multi-turn conversations with mock personas
    - ConversationEvaluator: Assesses conversation quality against tone-of-voice principles
    - test_scenarios: Predefined challenging test personas and scenarios
    - stress_scenarios: Stress test scenarios for batching, delays, and urgency testing
    - split_response_naturally: Utility to split long responses into natural message chunks
    - TestPatternIterator: Helper for pattern-driven test orchestration
    - StressTestRunner: Runs stress tests with mock or real Telegram
    - MockTelegramDaemon: Production-like daemon for mock testing
    - E2ETelegramPlayer: Real Telegram integration for E2E tests
    - reset_test_prospect: Manual testing helper
    - save_test_result: Database operations for test results

Usage:
    from conversation_simulator import ConversationSimulator
    from conversation_evaluator import ConversationEvaluator
    import test_scenarios
    import stress_scenarios
    from message_splitter import split_response_naturally
    from stress_test_runner import StressTestRunner, TestPatternIterator
    from mock_telegram_daemon import MockTelegramDaemon
    from e2e_telegram_player import E2ETelegramPlayer
    from manual_test import reset_test_prospect
    from test_result_manager import save_test_result, get_score_trends

    # Run a conversation simulation
    simulator = ConversationSimulator()
    result = await simulator.run_scenario(test_scenarios.SCENARIOS[0])

    # Evaluate the conversation quality
    evaluator = ConversationEvaluator()
    assessment = await evaluator.evaluate(result)

    # Use message splitter
    messages = split_response_naturally("Long text here. Multiple sentences.")

    # Run stress tests
    runner = StressTestRunner()
    stress_result = await runner.run_mock_stress_test(stress_scenarios.STRESS_SCENARIOS[0])
"""
# Support both package import and direct execution
try:
    from .conversation_simulator import (
        ConversationSimulator,
        ConversationResult,
        ConversationTurn,
        ConversationOutcome,
        PersonaDefinition,
        ConversationScenario,
    )
    from .conversation_evaluator import ConversationEvaluator, ConversationAssessment
    from .message_splitter import split_response_naturally
    from .stress_test_runner import StressTestRunner, StressTestResult, TestPatternIterator
    from .mock_telegram_daemon import MockTelegramDaemon, MockTelegramService, CapturedMessage
    from .e2e_telegram_player import E2ETelegramPlayer, create_test_prospect_session
    from .manual_test import reset_test_prospect
    from .test_result_manager import (
        save_test_result,
        get_test_results,
        get_score_trends,
        get_scenario_analytics,
        close_pool,
        TestResult,
        DailyScoreSummary,
        ScenarioAnalytics,
    )
    from . import test_scenarios
    from . import stress_scenarios
except ImportError:
    from conversation_simulator import (
        ConversationSimulator,
        ConversationResult,
        ConversationTurn,
        ConversationOutcome,
        PersonaDefinition,
        ConversationScenario,
    )
    from conversation_evaluator import ConversationEvaluator, ConversationAssessment
    from message_splitter import split_response_naturally
    from stress_test_runner import StressTestRunner, StressTestResult, TestPatternIterator
    from mock_telegram_daemon import MockTelegramDaemon, MockTelegramService, CapturedMessage
    from e2e_telegram_player import E2ETelegramPlayer, create_test_prospect_session
    from manual_test import reset_test_prospect
    from test_result_manager import (
        save_test_result,
        get_test_results,
        get_score_trends,
        get_scenario_analytics,
        close_pool,
        TestResult,
        DailyScoreSummary,
        ScenarioAnalytics,
    )
    import test_scenarios
    import stress_scenarios

__all__ = [
    # Conversation simulation
    "ConversationSimulator",
    "ConversationResult",
    "ConversationTurn",
    "ConversationOutcome",
    "PersonaDefinition",
    "ConversationScenario",
    # Evaluation
    "ConversationEvaluator",
    "ConversationAssessment",
    # Message utilities
    "split_response_naturally",
    # Stress testing
    "StressTestRunner",
    "StressTestResult",
    "TestPatternIterator",
    "MockTelegramDaemon",
    "MockTelegramService",
    "CapturedMessage",
    "E2ETelegramPlayer",
    "create_test_prospect_session",
    # Manual testing
    "reset_test_prospect",
    # Test result persistence
    "save_test_result",
    "get_test_results",
    "get_score_trends",
    "get_scenario_analytics",
    "close_pool",
    "TestResult",
    "DailyScoreSummary",
    "ScenarioAnalytics",
    # Scenario modules
    "test_scenarios",
    "stress_scenarios",
]
