# =============================================================================
# agent/needs/core.py — Single need with thresholds
# =============================================================================

from typing import Callable
from utils import clamp


class Need:
    """
    A single need with value, rate of change, and thresholds.

    direction:
        1 = increases over time (hunger)
        -1 = decreases over time (hygiene, happiness)
    """

    def __init__(
        self,
        name: str,
        initial: float,
        rate: float,
        direction: int,
        llm_threshold: float,
        critical_threshold: float,
        seek_threshold: float,
        min_val: float = 0.0,
        max_val: float = 100.0,
    ):
        self.name = name
        self._value = initial
        self._rate = rate
        self._direction = direction
        self._llm_threshold = llm_threshold
        self._critical_threshold = critical_threshold
        self._seek_threshold = seek_threshold
        self._min = min_val
        self._max = max_val

    @property
    def value(self) -> float:
        return self._value

    @value.setter
    def value(self, v: float) -> None:
        self._value = clamp(v, self._min, self._max)

    def update(self, delta: float) -> None:
        """Update need based on elapsed time."""
        change = self._rate * delta * self._direction
        self.value = self._value + change

    def modify(self, amount: float) -> None:
        """Modify need by amount (can be positive or negative)."""
        self.value = self._value + amount

    def is_llm_triggered(self) -> bool:
        """Check if need crossed LLM threshold."""
        if self._direction == 1:
            return self._value >= self._llm_threshold
        return self._value <= self._llm_threshold

    def is_critical(self) -> bool:
        """Check if need is in critical state."""
        if self._direction == 1:
            return self._value >= self._critical_threshold
        return self._value <= self._critical_threshold

    def is_seeking(self) -> bool:
        """Check if need should trigger seeking behavior."""
        if self._direction == 1:
            return self._value >= self._seek_threshold
        return self._value <= self._seek_threshold

    def urgency(self) -> float:
        """Calculate urgency for seeking priority."""
        if not self.is_seeking():
            return 0.0
        if self._direction == 1:
            return self._value - self._seek_threshold
        return self._seek_threshold - self._value

    def to_dict(self) -> dict:
        return {"value": self._value}

    def from_dict(self, data: dict) -> None:
        self._value = clamp(data.get("value", 50.0), self._min, self._max)