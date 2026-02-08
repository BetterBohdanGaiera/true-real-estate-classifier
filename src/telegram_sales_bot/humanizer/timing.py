"""
Natural timing distribution for human-like response delays.

This module provides timing calculations that mimic human response patterns
using statistical distributions rather than simple uniform randomness.
Human responses tend to cluster around a typical time with occasional
longer pauses (thinking, distraction) and rare quick responses.
"""
import random
import math
from typing import Optional
from enum import Enum

class ResponseType(str, Enum):
    """Type of response affecting timing calculation."""
    QUICK_ACK = "quick_ack"      # "ok", "da", short confirmations
    NORMAL = "normal"            # Standard responses
    THOUGHTFUL = "thoughtful"    # Complex questions, needs thinking
    LONG_READ = "long_read"      # Reading long incoming message

# Timing profiles (in seconds) for each response type
# base: typical delay for this type
# variance: how much variation is normal
# max: hard maximum to prevent excessive delays
TIMING_PROFILES = {
    ResponseType.QUICK_ACK: {
        "base": 1.5,
        "variance": 1.0,
        "max": 4.0,
    },
    ResponseType.NORMAL: {
        "base": 3.0,
        "variance": 3.0,
        "max": 10.0,
    },
    ResponseType.THOUGHTFUL: {
        "base": 5.0,
        "variance": 5.0,
        "max": 15.0,
    },
    ResponseType.LONG_READ: {
        "base": 8.0,
        "variance": 7.0,
        "max": 20.0,
    },
}

def classify_response_type(
    incoming_message: str,
    outgoing_message: str
) -> ResponseType:
    """
    Classify the type of response for timing purposes.

    Args:
        incoming_message: The message being responded to
        outgoing_message: The response being sent

    Returns:
        ResponseType based on message characteristics
    """
    incoming_len = len(incoming_message) if incoming_message else 0
    outgoing_len = len(outgoing_message) if outgoing_message else 0

    # Long incoming message = need time to read
    if incoming_len > 200:
        return ResponseType.LONG_READ

    # Short outgoing = quick acknowledgment
    if outgoing_len < 50:
        return ResponseType.QUICK_ACK

    # Long outgoing = thoughtful response
    if outgoing_len > 200:
        return ResponseType.THOUGHTFUL

    return ResponseType.NORMAL

def calculate_natural_delay(
    incoming_message: str,
    outgoing_message: str,
    mode: str = "natural"
) -> float:
    """
    Calculate a natural-feeling delay for response.

    Uses a log-normal distribution for more human-like variation:
    - Most responses cluster around a typical time
    - Occasional longer pauses (thinking, distracted)
    - Rare very quick responses

    Args:
        incoming_message: The message being responded to
        outgoing_message: The response being sent
        mode: Timing mode - "uniform" (simple), "natural" (log-normal),
              "variable" (context-based with distraction)

    Returns:
        Delay in seconds (always >= 1.0)
    """
    response_type = classify_response_type(incoming_message, outgoing_message)
    profile = TIMING_PROFILES[response_type]

    if mode == "uniform":
        # Simple uniform distribution - less realistic but predictable
        return random.uniform(profile["base"] - 1, profile["base"] + 2)

    elif mode == "natural":
        # Log-normal distribution - more realistic human-like timing
        # Most values cluster around base, with occasional longer delays
        mu = math.log(profile["base"])
        sigma = 0.5  # Controls spread of distribution

        delay = random.lognormvariate(mu, sigma)

        # Add small random jitter to avoid patterns
        delay += random.uniform(-0.5, 0.5)

        # Clamp to reasonable range
        return max(1.0, min(delay, profile["max"]))

    elif mode == "variable":
        # Context-based with more variation and occasional distractions
        base = profile["base"]
        variance = profile["variance"]

        # Triangular distribution - peaks at base, tapers to edges
        delay = random.triangular(
            base - variance / 2,
            base + variance,
            base
        )

        # 10% chance of "distracted" extra delay (human got distracted)
        if random.random() < 0.1:
            delay += random.uniform(2, 5)

        return max(1.0, min(delay, profile["max"]))

    # Fallback to simple uniform if unknown mode
    return random.uniform(2.0, 5.0)

class NaturalTiming:
    """
    Service for natural response timing.

    Provides human-like delays based on message characteristics
    and avoids repeating similar delay values.
    """

    def __init__(self, mode: str = "natural"):
        """
        Initialize timing service.

        Args:
            mode: Timing mode - "uniform", "natural", or "variable"
        """
        self.mode = mode
        self._last_delay: Optional[float] = None

    def get_delay(
        self,
        incoming_message: str,
        outgoing_message: str
    ) -> float:
        """
        Get delay for this response.

        Args:
            incoming_message: The message being responded to
            outgoing_message: The response being sent

        Returns:
            Delay in seconds
        """
        delay = calculate_natural_delay(
            incoming_message,
            outgoing_message,
            self.mode
        )

        # Avoid repeating exact same delay (looks robotic)
        if self._last_delay is not None and abs(delay - self._last_delay) < 0.5:
            delay += random.uniform(-1, 1)

        self._last_delay = delay
        return max(1.0, delay)

    def get_typing_duration(self, message_length: int) -> float:
        """
        Get realistic typing indicator duration.

        Simulates how long it takes a human to type the message.
        Assumes ~30 chars per second for a fast typist with variation.

        Args:
            message_length: Length of the message in characters

        Returns:
            Typing duration in seconds (1.0 - 8.0)
        """
        # ~30 chars per second for fast typist, with variation
        chars_per_second = random.uniform(20, 40)
        duration = message_length / chars_per_second

        # Add thinking pauses for longer messages
        if message_length > 100:
            duration += random.uniform(0.5, 2)

        return max(1.0, min(duration, 8.0))
