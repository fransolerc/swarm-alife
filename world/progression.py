# =============================================================================
# world/progression.py — swarm-alife
# Progresión de nivel. Singleton de módulo: importar game_progress directamente.
#
# Nivel 1 (inicio): el jugador puede soltar manzanas individuales desde la paleta.
# Nivel 2 (población ≥ 3): los árboles crecen manzanas; las criaturas los zarandean.
# =============================================================================

import logging
from typing import Optional

from config import LANGUAGE

logger = logging.getLogger(__name__)

_LEVEL_UP_MESSAGES = {
    "es": "¡Nivel 2 — los árboles ahora crecen manzanas!",
    "en": "Level 2 unlocked — trees now grow apples!",
}

LEVEL_2_POPULATION = 3    # criaturas vivas necesarias para desbloquear nivel 2
_LEVEL_UP_DURATION = 4.0  # segundos que permanece el mensaje flotante


class GameProgress:
    """
    Rastrea el nivel del juego y dispara los desbloqueos de progresión.
    No instanciar directamente — usar el singleton `game_progress`.
    """

    def __init__(self):
        self.level: int              = 1
        self._level_up_msg: Optional[str] = None
        self._level_up_timer: float  = 0.0

    def update(self, population: int, delta: float) -> None:
        """Llamar una vez por frame desde main._update()."""
        if self.level == 1 and population >= LEVEL_2_POPULATION:
            self.level = 2
            self._level_up_msg   = _LEVEL_UP_MESSAGES.get(LANGUAGE, _LEVEL_UP_MESSAGES["es"])
            self._level_up_timer = 0.0
            logger.info(f"Level 2 unlocked (population={population})")

        if self._level_up_msg is not None:
            self._level_up_timer += delta
            if self._level_up_timer >= _LEVEL_UP_DURATION:
                self._level_up_msg = None

    @property
    def trees_have_apples(self) -> bool:
        return self.level >= 2

    @property
    def level_up_message(self) -> Optional[str]:
        """Mensaje de nivel activo, o None si ya expiró."""
        return self._level_up_msg

    def __repr__(self) -> str:
        return f"GameProgress(level={self.level})"


# Singleton de módulo
game_progress = GameProgress()
