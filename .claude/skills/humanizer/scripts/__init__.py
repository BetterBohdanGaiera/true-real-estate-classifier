"""
Humanizer module - Make agent communication more natural.

This module provides utilities to make automated messages appear more
human-like through natural timing and optional typo injection.

Provides:
- NaturalTiming: More human-like response timing using statistical distributions
- calculate_natural_delay: Function to calculate delays based on message type
- ResponseType: Enum for classifying response types
- TypoInjector: Optional typo generation (experimental, disabled by default)

Example usage:
    from natural_timing import NaturalTiming, calculate_natural_delay

    # Using NaturalTiming class
    timing = NaturalTiming(mode="natural")
    delay = timing.get_delay(incoming_message, outgoing_message)
    typing_duration = timing.get_typing_duration(len(outgoing_message))

    # Using function directly
    delay = calculate_natural_delay(incoming, outgoing, mode="natural")

    # Using TypoInjector (experimental)
    from typo_injector import TypoInjector
    injector = TypoInjector(probability=0.05)
    text_with_typo, correction = injector.inject_typo("Привет, как дела?")
"""
from .natural_timing import (
    NaturalTiming,
    calculate_natural_delay,
    classify_response_type,
    ResponseType,
    TIMING_PROFILES,
)
from .typo_injector import TypoInjector, COMMON_TYPOS

__all__ = [
    # Main timing class
    "NaturalTiming",
    # Timing functions
    "calculate_natural_delay",
    "classify_response_type",
    # Timing enums and constants
    "ResponseType",
    "TIMING_PROFILES",
    # Typo injection (experimental)
    "TypoInjector",
    "COMMON_TYPOS",
]
