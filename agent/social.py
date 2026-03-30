# =============================================================================
# agent/social.py — swarm-alife
# Comportamiento social emergente. Python puro, sin Pygame ni LLM.
# Se ejecuta cada tick sobre todas las criaturas.
# =============================================================================

import logging
from typing import TYPE_CHECKING

from config import HUNGER_CRITICAL

if TYPE_CHECKING:
    from agent.creature import Creature

logger = logging.getLogger(__name__)


def update_social(creatures: list["Creature"], delta: float) -> None:
    """
    Aplica todos los mecanismos sociales a la lista de criaturas.
    Llamar una vez por tick, después de actualizar necesidades individuales.
    """
    _proximity_effects(creatures, delta)


def _proximity_effects(creatures: list["Creature"], delta: float) -> None:
    """
    Para cada criatura, examina sus vecinos dentro de INTERACTION_RADIUS y aplica:

    1. Confort por proximidad: +happiness si hay al menos un vecino cerca.
    2. Contagio de hambre: si un vecino tiene hambre crítica, sube la ansiedad
       (baja happiness) de las criaturas cercanas.
    3. Contagio de agotamiento: similar para energy crítica.
    """
    n = len(creatures)
    for i in range(n):
        c = creatures[i]
        neighbors = []
        hungry_neighbors = 0
        tired_neighbors  = 0

        for j in range(n):
            if i == j:
                continue
            other = creatures[j]
            if c.is_near(other):
                neighbors.append(other)
                if other.needs.hunger >= HUNGER_CRITICAL:
                    hungry_neighbors += 1

        # 1. Confort: al menos un vecino cerca → bonus de felicidad
        if neighbors:
            c.needs.apply_proximity_bonus(delta)

        # 2. Contagio de hambre: cada vecino hambriento añade ansiedad
        for _ in range(hungry_neighbors):
            c.needs.apply_hunger_contagion(delta)

        # 3. Contagio de agotamiento (misma mecánica, umbral distinto)
        #    Implementación mínima: reduce happiness ligeramente
        if tired_neighbors > 0:
            c.needs.apply_hunger_contagion(delta * 0.5 * tired_neighbors)
