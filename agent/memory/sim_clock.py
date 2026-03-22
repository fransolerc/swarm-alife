# =============================================================================
# agent/memory/sim_clock.py — swarm-alife
# Reloj de tiempo simulado. Desacoplado de UE5: avanza por tiempo real * factor.
# Portado de digimon-alife, eliminada sincronización con pitch_rotation de UE5.
# =============================================================================

import time
import logging
from config import SIM_MINUTES_PER_REAL_MINUTE, LANGUAGE

logger = logging.getLogger(__name__)

_PERIODS = {
    "es": {
        "morning":   "mañana",      # 06:00 – 12:00
        "afternoon": "tarde",       # 12:00 – 20:00
        "evening":   "noche",       # 20:00 – 00:00
        "night":     "madrugada",   # 00:00 – 06:00
    },
    "en": {
        "morning":   "morning",
        "afternoon": "afternoon",
        "evening":   "evening",
        "night":     "night",
    },
}


class SimClock:
    """
    Reloj de tiempo simulado.

    El tiempo simulado avanza a SIM_MINUTES_PER_REAL_MINUTE × la velocidad real.
    Por defecto: 1 minuto real = 60 minutos simulados (1 día = 24 minutos reales).

    Uso:
        clock = SimClock()
        clock.update()       # llamar cada frame
        clock.time_str()     # → "14:32"
        clock.period()       # → "tarde"
        clock.sim_seconds    # segundos totales simulados transcurridos
    """

    def __init__(self, start_hour: float = 8.0):
        """
        start_hour: hora simulada inicial (0–24). Por defecto arranca a las 8:00.
        """
        self._real_start = time.time()
        self._sim_offset_seconds = start_hour * 3600.0  # horas → segundos simulados
        self.sim_seconds: float = self._sim_offset_seconds

    def update(self, delta: float) -> None:
        """
        Avanza el reloj.
        delta: segundos reales transcurridos desde el último frame.
        """
        sim_delta = delta * SIM_MINUTES_PER_REAL_MINUTE
        self.sim_seconds += sim_delta

    @property
    def sim_hour(self) -> float:
        """Hora simulada actual (0.0 – 24.0, cíclica)."""
        return (self.sim_seconds / 3600.0) % 24.0

    @property
    def sim_minute(self) -> int:
        return int((self.sim_seconds % 3600) / 60)

    def time_str(self) -> str:
        """Devuelve la hora simulada formateada: 'HH:MM'."""
        h = int(self.sim_hour)
        m = self.sim_minute
        return f"{h:02d}:{m:02d}"

    def period(self) -> str:
        """Devuelve el período del día en el idioma configurado."""
        h = self.sim_hour
        periods = _PERIODS.get(LANGUAGE, _PERIODS["es"])
        if 6.0 <= h < 12.0:
            return periods["morning"]
        elif 12.0 <= h < 20.0:
            return periods["afternoon"]
        elif 20.0 <= h < 24.0:
            return periods["evening"]
        else:
            return periods["night"]

    def is_night(self) -> bool:
        """True si es madrugada o noche (útil para modificar tasas de necesidades)."""
        h = self.sim_hour
        return h >= 22.0 or h < 6.0

    def to_dict(self) -> dict:
        """Serialización para persistencia."""
        return {"sim_seconds": self.sim_seconds}

    def from_dict(self, data: dict) -> None:
        """Restaura estado desde dict."""
        self.sim_seconds = data.get("sim_seconds", self._sim_offset_seconds)

    def __repr__(self) -> str:
        return f"SimClock({self.time_str()}, {self.period()})"
