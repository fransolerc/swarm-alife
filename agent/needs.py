# =============================================================================
# agent/needs.py — swarm-alife
# Sistema de necesidades. Lógica pura, sin Pygame ni LLM.
# =============================================================================

import random
import logging
from dataclasses import dataclass, field

from config import (
    NEED_MAX, NEED_MIN,
    HUNGER_RATE, HYGIENE_RATE, HAPPINESS_RATE, ENERGY_RATE,
    HUNGER_INITIAL, HYGIENE_INITIAL, HAPPINESS_INITIAL, ENERGY_INITIAL,
    NEED_INITIAL_VARIANCE,
    HUNGER_CRITICAL, HYGIENE_CRITICAL, HAPPINESS_CRITICAL, ENERGY_CRITICAL,
    HUNGER_LLM_THRESHOLD, HYGIENE_LLM_THRESHOLD,
    HAPPINESS_LLM_THRESHOLD, ENERGY_LLM_THRESHOLD,
    FEED_HUNGER_REDUCTION, SHOWER_HYGIENE_RESTORE,
    PLAY_HAPPINESS_BONUS, PLAY_ENERGY_COST, SLEEP_ENERGY_RESTORE,
)
from utils import clamp

logger = logging.getLogger(__name__)


@dataclass
class Needs:
    """
    Estado interno de necesidades de una criatura.

    Convención:
    - hunger:    0 = saciada, 100 = hambrienta al límite
    - hygiene:   0 = sucia, 100 = limpia
    - happiness: 0 = miserable, 100 = muy feliz
    - energy:    0 = agotada, 100 = descansada
    """
    hunger:    float = field(default_factory=lambda: _initial(HUNGER_INITIAL))
    hygiene:   float = field(default_factory=lambda: _initial(HYGIENE_INITIAL))
    happiness: float = field(default_factory=lambda: _initial(HAPPINESS_INITIAL))
    energy:    float = field(default_factory=lambda: _initial(ENERGY_INITIAL))

    def update(self, delta: float, is_night: bool = False) -> list[str]:
        """
        Actualiza todas las necesidades según el tiempo transcurrido.

        delta: segundos reales transcurridos.
        is_night: modifica tasas (de noche aumenta cansancio, baja hambre).

        Devuelve lista de necesidades que han superado su umbral LLM (puede estar vacía).
        """
        night_factor = 1.5 if is_night else 1.0

        self.hunger    = clamp(self.hunger    + HUNGER_RATE    * delta,           NEED_MIN, NEED_MAX)
        self.hygiene   = clamp(self.hygiene   + HYGIENE_RATE   * delta,           NEED_MIN, NEED_MAX)
        self.happiness = clamp(self.happiness + HAPPINESS_RATE * delta,           NEED_MIN, NEED_MAX)
        self.energy    = clamp(self.energy    + ENERGY_RATE    * delta * night_factor, NEED_MIN, NEED_MAX)

        return self._check_llm_thresholds()

    def _check_llm_thresholds(self) -> list[str]:
        """Devuelve las necesidades que han cruzado el umbral LLM."""
        triggered = []
        if self.hunger    >= HUNGER_LLM_THRESHOLD:    triggered.append("hunger")
        if self.hygiene   <= HYGIENE_LLM_THRESHOLD:   triggered.append("hygiene")
        if self.happiness <= HAPPINESS_LLM_THRESHOLD: triggered.append("happiness")
        if self.energy    <= ENERGY_LLM_THRESHOLD:    triggered.append("energy")
        return triggered

    # --- Estado crítico (afecta visualmente) ---

    def is_critical(self) -> bool:
        """True si alguna necesidad está en estado crítico."""
        return (
            self.hunger    >= HUNGER_CRITICAL or
            self.hygiene   <= HYGIENE_CRITICAL or
            self.happiness <= HAPPINESS_CRITICAL or
            self.energy    <= ENERGY_CRITICAL
        )

    def critical_needs(self) -> list[str]:
        """Lista de nombres de necesidades en estado crítico."""
        crit = []
        if self.hunger    >= HUNGER_CRITICAL:    crit.append("hunger")
        if self.hygiene   <= HYGIENE_CRITICAL:   crit.append("hygiene")
        if self.happiness <= HAPPINESS_CRITICAL: crit.append("happiness")
        if self.energy    <= ENERGY_CRITICAL:    crit.append("energy")
        return crit

    def most_urgent(self) -> str | None:
        """Devuelve el nombre de la necesidad más urgente, o None si todo está bien."""
        candidates = []

        # hunger: urgencia = valor (más alto = más urgente)
        candidates.append(("hunger",    self.hunger))
        # hygiene: urgencia = 100 - valor (más bajo = más urgente)
        candidates.append(("hygiene",   NEED_MAX - self.hygiene))
        # happiness: urgencia = 100 - valor
        candidates.append(("happiness", NEED_MAX - self.happiness))
        # energy: urgencia = 100 - valor
        candidates.append(("energy",    NEED_MAX - self.energy))

        most_urgent = max(candidates, key=lambda x: x[1])
        # Solo reportar si supera el umbral LLM
        if most_urgent[0] == "hunger"    and self.hunger    >= HUNGER_LLM_THRESHOLD:
            return "hunger"
        if most_urgent[0] == "hygiene"   and self.hygiene   <= HYGIENE_LLM_THRESHOLD:
            return "hygiene"
        if most_urgent[0] == "happiness" and self.happiness <= HAPPINESS_LLM_THRESHOLD:
            return "happiness"
        if most_urgent[0] == "energy"    and self.energy    <= ENERGY_LLM_THRESHOLD:
            return "energy"
        return None

    # --- Acciones del usuario ---

    def feed(self) -> None:
        self.hunger = clamp(self.hunger - FEED_HUNGER_REDUCTION, NEED_MIN, NEED_MAX)
        logger.debug("Needs: fed → hunger %.1f", self.hunger)

    def shower(self) -> None:
        self.hygiene = clamp(self.hygiene + SHOWER_HYGIENE_RESTORE, NEED_MIN, NEED_MAX)
        logger.debug("Needs: showered → hygiene %.1f", self.hygiene)

    def play(self) -> None:
        self.happiness = clamp(self.happiness + PLAY_HAPPINESS_BONUS, NEED_MIN, NEED_MAX)
        self.energy    = clamp(self.energy    - PLAY_ENERGY_COST,     NEED_MIN, NEED_MAX)
        logger.debug("Needs: played → happiness %.1f, energy %.1f", self.happiness, self.energy)

    def sleep(self) -> None:
        self.energy = clamp(self.energy + SLEEP_ENERGY_RESTORE, NEED_MIN, NEED_MAX)
        logger.debug("Needs: slept → energy %.1f", self.energy)

    # --- Social: modificadores externos ---

    def apply_proximity_bonus(self, delta: float) -> None:
        """Bonus de felicidad por estar cerca de otras criaturas."""
        from config import PROXIMITY_HAPPINESS_BONUS
        self.happiness = clamp(
            self.happiness + PROXIMITY_HAPPINESS_BONUS * delta,
            NEED_MIN, NEED_MAX
        )

    def apply_hunger_contagion(self, delta: float) -> None:
        """Contagio de ansiedad por proximidad a criatura hambrienta."""
        from config import CONTAGION_ANXIETY_RATE
        self.happiness = clamp(
            self.happiness - CONTAGION_ANXIETY_RATE * delta,
            NEED_MIN, NEED_MAX
        )

    # --- Serialización ---

    def to_dict(self) -> dict:
        return {
            "hunger":    self.hunger,
            "hygiene":   self.hygiene,
            "happiness": self.happiness,
            "energy":    self.energy,
        }

    def from_dict(self, data: dict) -> None:
        self.hunger    = data.get("hunger",    HUNGER_INITIAL)
        self.hygiene   = data.get("hygiene",   HYGIENE_INITIAL)
        self.happiness = data.get("happiness", HAPPINESS_INITIAL)
        self.energy    = data.get("energy",    ENERGY_INITIAL)

    def __repr__(self) -> str:
        return (
            f"Needs(hunger={self.hunger:.0f}, hygiene={self.hygiene:.0f}, "
            f"happiness={self.happiness:.0f}, energy={self.energy:.0f})"
        )


def _initial(base: float) -> float:
    """Valor inicial con varianza aleatoria para evitar sincronización entre criaturas."""
    return clamp(
        base + random.uniform(-NEED_INITIAL_VARIANCE, NEED_INITIAL_VARIANCE),
        NEED_MIN, NEED_MAX,
    )
