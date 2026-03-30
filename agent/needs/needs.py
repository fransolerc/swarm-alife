# =============================================================================
# agent/needs/needs.py — Creature needs container
# =============================================================================

import random
import logging

from agent.needs.core import Need
from agent.needs.modifiers import apply_proximity_bonus, apply_hunger_contagion
from config import (
    NEED_MAX, NEED_MIN,
    HUNGER_RATE, HYGIENE_RATE, HAPPINESS_RATE,
    HUNGER_INITIAL, HYGIENE_INITIAL, HAPPINESS_INITIAL,
    NEED_INITIAL_VARIANCE,
    HUNGER_CRITICAL, HYGIENE_CRITICAL, HAPPINESS_CRITICAL,
    HUNGER_LLM_THRESHOLD, HYGIENE_LLM_THRESHOLD,
    HAPPINESS_LLM_THRESHOLD,
    HUNGER_SEEK_THRESHOLD, HYGIENE_SEEK_THRESHOLD,
    HAPPINESS_SEEK_THRESHOLD,
    FEED_HUNGER_REDUCTION, SHOWER_HYGIENE_RESTORE,
    PLAY_HAPPINESS_BONUS,
)
from utils import clamp

logger = logging.getLogger(__name__)


class Needs:
    """
    Container for all creature needs.

    Convention:
    - hunger: 0 = satiated, 100 = starving
    - hygiene: 0 = dirty, 100 = clean
    - happiness: 0 = miserable, 100 = very happy
    """

    def __init__(self):
        self._hunger = Need(
            name="hunger",
            initial=_initial(HUNGER_INITIAL),
            rate=HUNGER_RATE,
            direction=1,  # increases over time
            llm_threshold=HUNGER_LLM_THRESHOLD,
            critical_threshold=HUNGER_CRITICAL,
            seek_threshold=HUNGER_SEEK_THRESHOLD,
            min_val=NEED_MIN,
            max_val=NEED_MAX,
        )
        self._hygiene = Need(
            name="hygiene",
            initial=_initial(HYGIENE_INITIAL),
            rate=HYGIENE_RATE,
            direction=-1,  # decreases over time
            llm_threshold=HYGIENE_LLM_THRESHOLD,
            critical_threshold=HYGIENE_CRITICAL,
            seek_threshold=HYGIENE_SEEK_THRESHOLD,
            min_val=NEED_MIN,
            max_val=NEED_MAX,
        )
        self._happiness = Need(
            name="happiness",
            initial=_initial(HAPPINESS_INITIAL),
            rate=HAPPINESS_RATE,
            direction=-1,  # decreases over time
            llm_threshold=HAPPINESS_LLM_THRESHOLD,
            critical_threshold=HAPPINESS_CRITICAL,
            seek_threshold=HAPPINESS_SEEK_THRESHOLD,
            min_val=NEED_MIN,
            max_val=NEED_MAX,
        )

    # --- Proxy properties ---

    @property
    def hunger(self) -> float:
        return self._hunger.value

    @hunger.setter
    def hunger(self, v: float) -> None:
        self._hunger.value = v

    @property
    def hygiene(self) -> float:
        return self._hygiene.value

    @hygiene.setter
    def hygiene(self, v: float) -> None:
        self._hygiene.value = v

    @property
    def happiness(self) -> float:
        return self._happiness.value

    @happiness.setter
    def happiness(self, v: float) -> None:
        self._happiness.value = v

    # --- Update cycle ---

    def update(self, delta: float) -> list[str]:
        """Update all needs. Returns list of triggered needs."""
        self._hunger.update(delta)
        self._hygiene.update(delta)
        self._happiness.update(delta)
        return self._check_llm_thresholds()

    def _check_llm_thresholds(self) -> list[str]:
        """Check which needs crossed LLM threshold."""
        triggered = []
        if self._hunger.is_llm_triggered():
            triggered.append("hunger")
        if self._hygiene.is_llm_triggered():
            triggered.append("hygiene")
        if self._happiness.is_llm_triggered():
            triggered.append("happiness")
        return triggered

    # --- Status checks ---

    def is_critical(self) -> bool:
        """True if any need is critical."""
        return (
            self._hunger.is_critical() or
            self._hygiene.is_critical() or
            self._happiness.is_critical()
        )

    def critical_needs(self) -> list[str]:
        """List of critical need names."""
        crit = []
        if self._hunger.is_critical():
            crit.append("hunger")
        if self._hygiene.is_critical():
            crit.append("hygiene")
        if self._happiness.is_critical():
            crit.append("happiness")
        return crit

    def most_urgent(self) -> str | None:
        """Most urgent need for seeking behavior."""
        urgencies = [
            ("hunger", self._hunger.urgency()),
            ("hygiene", self._hygiene.urgency()),
            ("happiness", self._happiness.urgency()),
        ]
        active = [(n, u) for n, u in urgencies if u > 0]
        if not active:
            return None
        return max(active, key=lambda x: x[1])[0]

    # --- User actions ---

    def feed(self) -> None:
        self._hunger.modify(-FEED_HUNGER_REDUCTION)

    def feed_amount(self, amount: float) -> None:
        self._hunger.modify(-amount)

    def shower(self) -> None:
        self._hygiene.modify(SHOWER_HYGIENE_RESTORE)

    def shower_amount(self, amount: float) -> None:
        self._hygiene.modify(amount)

    def play(self) -> None:
        self._happiness.modify(PLAY_HAPPINESS_BONUS)

    def play_amount(self, amount: float) -> None:
        self._happiness.modify(amount)

    # --- Social modifiers ---

    def apply_proximity_bonus(self, delta: float) -> None:
        apply_proximity_bonus(self, delta)

    def apply_hunger_contagion(self, delta: float) -> None:
        apply_hunger_contagion(self, delta)

    # --- Serialization ---

    def to_dict(self) -> dict:
        return {
            "hunger": self._hunger.value,
            "hygiene": self._hygiene.value,
            "happiness": self._happiness.value,
        }

    def from_dict(self, data: dict) -> None:
        self._hunger.from_dict({"value": data.get("hunger", HUNGER_INITIAL)})
        self._hygiene.from_dict({"value": data.get("hygiene", HYGIENE_INITIAL)})
        self._happiness.from_dict({"value": data.get("happiness", HAPPINESS_INITIAL)})

    def __repr__(self) -> str:
        return (
            f"Needs(hunger={self._hunger.value:.0f}, "
            f"hygiene={self._hygiene.value:.0f}, "
            f"happiness={self._happiness.value:.0f})"
        )


def _initial(base: float) -> float:
    """Initial value with random variance."""
    return clamp(
        base + random.uniform(-NEED_INITIAL_VARIANCE, NEED_INITIAL_VARIANCE),
        NEED_MIN, NEED_MAX,
    )