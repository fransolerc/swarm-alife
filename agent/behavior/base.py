# =============================================================================
# agent/behavior/base.py — Base behavior class
# =============================================================================

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from agent.creature import Creature


class Behavior(ABC):
    """Base class for creature behaviors."""

    def __init__(self, creature: "Creature"):
        self._creature = creature

    @abstractmethod
    def can_execute(self, world) -> bool:
        """Check if this behavior can execute given current state."""
        pass

    @abstractmethod
    def execute(self, delta: float, world) -> bool:
        """Execute behavior. Returns True if still executing, False if done."""
        pass

    @abstractmethod
    def reset(self) -> None:
        """Reset behavior state."""
        pass
