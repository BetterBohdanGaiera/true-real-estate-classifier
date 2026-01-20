"""
Testing module - Conversation simulation and evaluation infrastructure.

This module provides tools for testing sales agent conversation behavior
through simulated personas and structured quality evaluation.

Components:
    - ConversationSimulator: Orchestrates multi-turn conversations with mock personas
    - ConversationEvaluator: Assesses conversation quality against tone-of-voice principles
    - test_scenarios: Predefined challenging test personas and scenarios

Usage:
    from sales_agent.testing import ConversationSimulator, ConversationEvaluator
    from sales_agent.testing import test_scenarios

    # Run a conversation simulation
    simulator = ConversationSimulator()
    result = await simulator.run_scenario(test_scenarios.SCENARIOS[0])

    # Evaluate the conversation quality
    evaluator = ConversationEvaluator()
    assessment = await evaluator.evaluate(result)
"""
from .conversation_simulator import ConversationSimulator
from .conversation_evaluator import ConversationEvaluator
from . import test_scenarios

__all__ = [
    "ConversationSimulator",
    "ConversationEvaluator",
    "test_scenarios",
]
