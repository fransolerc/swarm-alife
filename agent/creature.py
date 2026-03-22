# =============================================================================
# agent/creature.py — swarm-alife
# Clase principal de criatura. Orquesta necesidades, movimiento, memoria y LLM.
# Sin Pygame: solo lógica pura.
# =============================================================================

import random
import time
import logging
import os
from typing import Optional

from agent.needs import Needs
from agent.memory.associative_memory import AssociativeMemory
from agent.memory.concept_node import ConceptNode
from config import (
    WINDOW_WIDTH, WINDOW_HEIGHT, UI_PANEL_WIDTH,
    CREATURE_SPEED, WANDER_INTERVAL, INTERACTION_RADIUS,
    LLM_MESSAGE_COOLDOWN, DATA_DIR, CREATURE_RADIUS,
    REPRODUCTION_MIN_AGE, REPRODUCTION_NEED_THRESHOLD,
    REPRODUCTION_COOLDOWN, OFFSPRING_NEED_VARIANCE, OFFSPRING_SPAWN_RADIUS,
    NEED_MIN, NEED_MAX,
)
from utils import clamp, normalize, distance, atomic_write_json, load_json, extract_keywords

logger = logging.getLogger(__name__)

# Área de movimiento: ventana menos el panel UI derecho
_AREA_W = WINDOW_WIDTH - UI_PANEL_WIDTH
_AREA_H = WINDOW_HEIGHT


class Creature:
    """
    Una criatura del swarm.

    Responsabilidades:
    - Mantener posición y movimiento wandering
    - Actualizar necesidades
    - Gestionar memoria asociativa
    - Disparar LLM cuando una necesidad supera umbral (delegado a communication.py)
    - Persistir estado en data/

    No sabe nada de Pygame. El renderer accede a sus atributos para dibujarlo.
    """

    def __init__(self, creature_id: str, x: Optional[float] = None, y: Optional[float] = None):
        self.id = creature_id

        # Posición
        self.x = x if x is not None else random.uniform(CREATURE_RADIUS, _AREA_W - CREATURE_RADIUS)
        self.y = y if y is not None else random.uniform(CREATURE_RADIUS, _AREA_H - CREATURE_RADIUS)

        # Movimiento
        self.dx: float = 0.0
        self.dy: float = 0.0
        self._wander_timer: float = 0.0
        self._wander_interval: float = random.uniform(*WANDER_INTERVAL)
        self._pick_new_direction()

        # Necesidades
        self.needs = Needs()

        # Memoria
        self.memory = AssociativeMemory()

        # Comunicación LLM
        self._last_llm_time: float = 0.0        # timestamp real del último mensaje
        self._pending_need: Optional[str] = None # necesidad que disparó el LLM
        self.current_message: Optional[str] = None  # mensaje visible al usuario
        self._message_timer: float = 0.0        # segundos que lleva visible el mensaje
        self._message_duration: float = 6.0     # segundos que se muestra

        # Estado visual
        self.selected: bool = False
        self.is_eating: bool = False  # animación futura

        # Edad y reproducción
        self.age: float = 0.0                        # segundos reales de vida
        self._reproduction_cooldown: float = 0.0     # segundos restantes de cooldown
        self.generation: int = 0                     # generación (0 = fundadora)

        logger.info(f"Creature {self.id} created at ({self.x:.0f}, {self.y:.0f})")

    # --- Update principal ---

    def update(self, delta: float, is_night: bool = False) -> Optional[str]:
        """
        Actualiza la criatura un tick.

        delta: segundos reales transcurridos.
        is_night: pasado desde SimClock.
        Devuelve:
          - nombre de necesidad urgente ("hunger", etc.) si hay que invocar LLM
          - "reproduce" si la criatura está lista para dividirse
          - None si no hay nada que comunicar
        """
        self.age += delta
        if self._reproduction_cooldown > 0:
            self._reproduction_cooldown -= delta

        self._update_movement(delta)
        triggered_needs = self.needs.update(delta, is_night)
        self._update_message_timer(delta)

        # Reproducción tiene prioridad sobre LLM
        if self.ready_to_reproduce():
            return "reproduce"

        if triggered_needs:
            return self._check_llm_trigger(triggered_needs)
        return None

    # --- Movimiento ---

    def _update_movement(self, delta: float) -> None:
        """Wandering simple: avanza en dirección actual, cambia periódicamente."""
        speed = CREATURE_SPEED

        # Criaturas muy agotadas se mueven más lento
        if self.needs.energy <= 20.0:
            speed *= 0.4
        elif self.needs.energy <= 40.0:
            speed *= 0.7

        self.x += self.dx * speed * delta
        self.y += self.dy * speed * delta

        # Rebote en bordes
        if self.x < CREATURE_RADIUS or self.x > _AREA_W - CREATURE_RADIUS:
            self.dx *= -1
            self.x = clamp(self.x, CREATURE_RADIUS, _AREA_W - CREATURE_RADIUS)
        if self.y < CREATURE_RADIUS or self.y > _AREA_H - CREATURE_RADIUS:
            self.dy *= -1
            self.y = clamp(self.y, CREATURE_RADIUS, _AREA_H - CREATURE_RADIUS)

        # Cambio periódico de dirección
        self._wander_timer += delta
        if self._wander_timer >= self._wander_interval:
            self._pick_new_direction()

    def _pick_new_direction(self) -> None:
        angle = random.uniform(0, 2 * 3.14159)
        import math
        self.dx = math.cos(angle)
        self.dy = math.sin(angle)
        self._wander_timer = 0.0
        self._wander_interval = random.uniform(*WANDER_INTERVAL)

    # --- LLM ---

    def _check_llm_trigger(self, triggered_needs: list[str]) -> Optional[str]:
        """
        Devuelve la necesidad más urgente si se cumple el cooldown.
        La comunicación real (llamada a Ollama) se hace en communication.py.
        """
        now = time.time()
        if now - self._last_llm_time < LLM_MESSAGE_COOLDOWN:
            return None

        # Prioridad: hunger > energy > hygiene > happiness
        priority = ["hunger", "energy", "hygiene", "happiness"]
        for need in priority:
            if need in triggered_needs:
                self._last_llm_time = now
                self._pending_need = need
                return need
        return None

    def set_message(self, message: str, duration: float = 6.0) -> None:
        """Establece el mensaje visible. Llamado desde communication.py."""
        self.current_message = message
        self._message_timer = 0.0
        self._message_duration = duration
        # Memorizar la interacción
        self.memory.add_raw(
            subject="yo",
            predicate="dije",
            object_=message[:50],
            poignancy=4.0,
            keywords=extract_keywords(message),
        )

    def _update_message_timer(self, delta: float) -> None:
        if self.current_message:
            self._message_timer += delta
            if self._message_timer >= self._message_duration:
                self.current_message = None
                self._message_timer = 0.0

    # --- Interacciones del usuario ---

    def feed(self) -> None:
        self.needs.feed()
        self.memory.add_raw("usuario", "me_alimentó", "comida", poignancy=6.0)

    def shower(self) -> None:
        self.needs.shower()
        self.memory.add_raw("usuario", "me_duchó", "agua", poignancy=5.0)

    def play(self) -> None:
        self.needs.play()
        self.memory.add_raw("usuario", "jugó_conmigo", "juego", poignancy=7.0)

    def sleep(self) -> None:
        self.needs.sleep()
        self.memory.add_raw("yo", "dormí", "descanso", poignancy=3.0)

    # --- Reproducción ---

    def ready_to_reproduce(self) -> bool:
        """
        True si la criatura cumple las condiciones para dividirse:
        - Edad mínima alcanzada
        - Cooldown de reproducción expirado
        - Todas las necesidades por encima del umbral (criatura "sana")
        """
        if self.age < REPRODUCTION_MIN_AGE:
            return False
        if self._reproduction_cooldown > 0:
            return False
        n = self.needs
        return (
            n.hunger    <= (100.0 - REPRODUCTION_NEED_THRESHOLD) and  # hunger: bajo es bueno
            n.hygiene   >= REPRODUCTION_NEED_THRESHOLD and
            n.happiness >= REPRODUCTION_NEED_THRESHOLD and
            n.energy    >= REPRODUCTION_NEED_THRESHOLD
        )

    def spawn_offspring(self, offspring_id: str) -> "Creature":
        """
        Crea una cría cerca del padre.
        El padre entra en cooldown de reproducción.
        La cría hereda necesidades con varianza y la generación del padre + 1.
        """
        import math

        # Posición: radio aleatorio alrededor del padre
        angle = random.uniform(0, 2 * math.pi)
        ox = clamp(
            self.x + math.cos(angle) * OFFSPRING_SPAWN_RADIUS,
            CREATURE_RADIUS, _AREA_W - CREATURE_RADIUS
        )
        oy = clamp(
            self.y + math.sin(angle) * OFFSPRING_SPAWN_RADIUS,
            CREATURE_RADIUS, _AREA_H - CREATURE_RADIUS
        )

        offspring = Creature(offspring_id, x=ox, y=oy)
        offspring.generation = self.generation + 1

        # Heredar necesidades con varianza
        offspring.needs.hunger    = clamp(self.needs.hunger    + random.uniform(-OFFSPRING_NEED_VARIANCE, OFFSPRING_NEED_VARIANCE), NEED_MIN, NEED_MAX)
        offspring.needs.hygiene   = clamp(self.needs.hygiene   + random.uniform(-OFFSPRING_NEED_VARIANCE, OFFSPRING_NEED_VARIANCE), NEED_MIN, NEED_MAX)
        offspring.needs.happiness = clamp(self.needs.happiness + random.uniform(-OFFSPRING_NEED_VARIANCE, OFFSPRING_NEED_VARIANCE), NEED_MIN, NEED_MAX)
        offspring.needs.energy    = clamp(self.needs.energy    + random.uniform(-OFFSPRING_NEED_VARIANCE, OFFSPRING_NEED_VARIANCE), NEED_MIN, NEED_MAX)

        # El padre entra en cooldown
        self._reproduction_cooldown = REPRODUCTION_COOLDOWN

        # Memoria del evento
        self.memory.add_raw(
            subject="yo",
            predicate="me_dividí_en",
            object_=offspring_id,
            poignancy=9.0,
            keywords=["división", "reproducción", offspring_id],
        )

        logger.info(
            f"Creature {self.id} (gen {self.generation}) spawned {offspring_id} "
            f"(gen {offspring.generation}) at ({ox:.0f},{oy:.0f})"
        )
        return offspring

    # --- Posición ---

    @property
    def pos(self) -> tuple[float, float]:
        return (self.x, self.y)

    def distance_to(self, other: "Creature") -> float:
        return distance(self.pos, other.pos)

    def is_near(self, other: "Creature") -> bool:
        return self.distance_to(other) <= INTERACTION_RADIUS

    # --- Persistencia ---

    def save(self) -> None:
        path = os.path.join(DATA_DIR, f"{self.id}.json")
        data = {
            "id":         self.id,
            "x":          self.x,
            "y":          self.y,
            "age":        self.age,
            "generation": self.generation,
            "needs":      self.needs.to_dict(),
            "memory":     self.memory.to_list(),
        }
        atomic_write_json(path, data)
        logger.debug(f"Creature {self.id}: saved state")

    def load(self) -> bool:
        path = os.path.join(DATA_DIR, f"{self.id}.json")
        data = load_json(path)
        if not data:
            return False
        self.x          = data.get("x", self.x)
        self.y          = data.get("y", self.y)
        self.age        = data.get("age", 0.0)
        self.generation = data.get("generation", 0)
        self.needs.from_dict(data.get("needs", {}))
        self.memory.from_list(data.get("memory", []))
        logger.info(f"Creature {self.id}: loaded state (gen {self.generation}, age {self.age:.0f}s)")
        return True

    def __repr__(self) -> str:
        return f"Creature(id={self.id!r}, pos=({self.x:.0f},{self.y:.0f}), {self.needs})"
