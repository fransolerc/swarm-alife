# =============================================================================
# agent/needs/modifiers.py — Social modifiers for needs
# =============================================================================

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent.needs.needs import Needs


def apply_proximity_bonus(needs: "Needs", delta: float) -> None:
    """Bonus de felicidad por estar cerca de otras criaturas."""
    from config import PROXIMITY_HAPPINESS_BONUS
    needs._happiness.modify(PROXIMITY_HAPPINESS_BONUS * delta)


def apply_hunger_contagion(needs: "Needs", delta: float) -> None:
    """Contagio de ansiedad por proximidad a criatura hambrienta."""
    from config import CONTAGION_ANXIETY_RATE
    needs._happiness.modify(-CONTAGION_ANXIETY_RATE * delta)