# =============================================================================
# agent/creature.py — swarm-alife
# =============================================================================

import random
import math
import time
import logging
import os
from typing import Optional

from agent.needs import Needs
from agent.memory.associative_memory import AssociativeMemory
from config import (
    WINDOW_WIDTH, WINDOW_HEIGHT, TOOLBAR_HEIGHT,
    CREATURE_SPEED, WANDER_INTERVAL, INTERACTION_RADIUS,
    LLM_MESSAGE_COOLDOWN, DATA_DIR, CREATURE_RADIUS,
    REPRODUCTION_MIN_AGE, REPRODUCTION_NEED_THRESHOLD,
    REPRODUCTION_COOLDOWN, OFFSPRING_NEED_VARIANCE, OFFSPRING_SPAWN_RADIUS,
    NEED_MIN, NEED_MAX,
)
from utils import clamp, normalize, distance, atomic_write_json, load_json, extract_keywords


logger = logging.getLogger(__name__)

_AREA_W = WINDOW_WIDTH
_AREA_H = WINDOW_HEIGHT - TOOLBAR_HEIGHT


class Creature:
    def __init__(self, creature_id: str, x: Optional[float] = None, y: Optional[float] = None):
        self.id = creature_id
        self.x  = x if x is not None else random.uniform(CREATURE_RADIUS, _AREA_W - CREATURE_RADIUS)
        self.y  = y if y is not None else random.uniform(CREATURE_RADIUS, _AREA_H - CREATURE_RADIUS)

        self.dx: float = 0.0
        self.dy: float = 0.0
        self._wander_timer: float    = 0.0
        self._wander_interval: float = random.uniform(*WANDER_INTERVAL)
        self._pick_new_direction()

        self.needs  = Needs()
        self.memory = AssociativeMemory()

        self._last_llm_time: float       = 0.0
        self._pending_need: Optional[str]= None
        self.current_message: Optional[str] = None
        self._message_timer: float       = 0.0
        self._message_duration: float    = 6.0

        self.selected: bool  = False

        self.age: float                  = 0.0
        self._reproduction_cooldown: float = 0.0
        self.generation: int             = 0

        # Seeking de objetos
        self._target_obj                 = None   # WorldObject | None
        self._using_obj: bool            = False
        self._use_timer: float           = 0.0   # segundos que lleva usando el objeto

        # Animación — leídos por el renderer, nunca afectan la lógica
        self.anim_t: float     = random.uniform(0, 6.28)  # fase inicial aleatoria
        self.speed_real: float = 0.0   # velocidad actual en px/s (para walk vs idle)

        logger.info(f"Creature {self.id} created at ({self.x:.0f}, {self.y:.0f})")

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(self, delta: float, is_night: bool = False, world=None) -> Optional[str]:
        self.age += delta
        if self._reproduction_cooldown > 0:
            self._reproduction_cooldown -= delta

        if world is not None:
            self._update_seeking(delta, world)

        self._update_movement(delta, world=world)
        triggered = self.needs.update(delta, is_night)
        self._update_message_timer(delta)

        if self.ready_to_reproduce():
            return "reproduce"
        if triggered:
            return self._check_llm_trigger(triggered)
        return None

    # ------------------------------------------------------------------
    # Seeking de objetos del mundo
    # ------------------------------------------------------------------

    def _update_seeking(self, delta: float, world) -> None:
        from config import HUNGER_SEEK_THRESHOLD, OBJ_USE_DURATION

        # Si está en uso activo, completar la duración antes de cualquier otra lógica
        if self._using_obj and self._target_obj is not None:
            self._use_timer += delta
            duration = OBJ_USE_DURATION.get(self._target_obj.type.name, 3.0)
            if self._use_timer < duration:
                # Frenar: quedarse junto al objeto hasta que expire el timer
                self.dx *= 0.1
                self.dy *= 0.1
                return
            else:
                # Timer expirado: liberar
                self._using_obj  = False
                self._use_timer  = 0.0
                self._target_obj = None
                return

        urgent = self.needs.most_urgent()

        # Buscar manzanas del suelo si hay hambre
        if urgent == "hunger" or self.needs.hunger >= HUNGER_SEEK_THRESHOLD:
            apple = world.nearest_apple(self.x, self.y)
            if apple is not None:
                if apple.in_range(self.x, self.y):
                    world.pick_apple(apple, self.needs)
                    self.memory.add_raw("yo", "comí", "manzana", poignancy=5.0,
                                        keywords=["manzana", "hambre"])
                    self._target_obj = None
                    self._using_obj  = False
                    return
                else:
                    self._steer_toward(apple.x, apple.y)
                    return

        if urgent is None:
            self._target_obj = None
            self._using_obj  = False
            self._use_timer  = 0.0
            return

        # Buscar nuevo target si no hay o ya no es válido
        if (self._target_obj is None
                or self._target_obj.need != urgent
                or not self._target_obj.can_use(self.id)):
            self._target_obj = world.nearest_for_need(urgent, self.x, self.y, self.id)
            self._use_timer  = 0.0

        if self._target_obj is None:
            return

        if self._target_obj.in_range(self.x, self.y):
            # Iniciar uso: aplicar efecto y empezar timer
            used = self._target_obj.use(self.id, self.needs)
            if used:
                self._using_obj = True
                self._use_timer = 0.0
                self.memory.add_raw(
                    subject="yo", predicate="usé",
                    object_=self._target_obj.type.name.lower(),
                    poignancy=5.0,
                    keywords=[urgent, self._target_obj.type.name.lower()],
                )
        else:
            self._steer_toward(self._target_obj.px, self._target_obj.py)

    def _steer_toward(self, tx: float, ty: float) -> None:
        dx, dy = normalize(tx - self.x, ty - self.y)
        self.dx = self.dx * 0.3 + dx * 0.7
        self.dy = self.dy * 0.3 + dy * 0.7

    # ------------------------------------------------------------------
    # Movimiento
    # ------------------------------------------------------------------

    def _update_movement(self, delta: float, world=None) -> None:
        speed = CREATURE_SPEED
        if self.needs.energy <= 20.0:   speed *= 0.4
        elif self.needs.energy <= 40.0: speed *= 0.7

        nx = self.x + self.dx * speed * delta
        ny = self.y + self.dy * speed * delta

        # Colisión con árboles: comprobar celda destino
        if world is not None and world.cell_blocked(nx, ny):
            # Intentar deslizarse en X o Y por separado
            if not world.cell_blocked(nx, self.y):
                ny = self.y
            elif not world.cell_blocked(self.x, ny):
                nx = self.x
            else:
                # Bloqueado en ambos ejes: rebotar y cambiar dirección
                self.dx *= -1
                self.dy *= -1
                nx = self.x
                ny = self.y
                self._pick_new_direction()

        self.x = nx
        self.y = ny

        if self.x < CREATURE_RADIUS or self.x > _AREA_W - CREATURE_RADIUS:
            self.dx *= -1
            self.x = clamp(self.x, CREATURE_RADIUS, _AREA_W - CREATURE_RADIUS)
        if self.y < CREATURE_RADIUS or self.y > _AREA_H - CREATURE_RADIUS:
            self.dy *= -1
            self.y = clamp(self.y, CREATURE_RADIUS, _AREA_H - CREATURE_RADIUS)

        self._wander_timer += delta
        if self._wander_timer >= self._wander_interval:
            self._pick_new_direction()

        # Actualizar estado de animación
        self.speed_real = speed * math.hypot(self.dx, self.dy)
        self.anim_t    += delta

    def _pick_new_direction(self) -> None:
        angle = random.uniform(0, 2 * math.pi)
        self.dx = math.cos(angle)
        self.dy = math.sin(angle)
        self._wander_timer    = 0.0
        self._wander_interval = random.uniform(*WANDER_INTERVAL)

    # ------------------------------------------------------------------
    # LLM
    # ------------------------------------------------------------------

    def _check_llm_trigger(self, triggered: list[str]) -> Optional[str]:
        now = time.time()
        if now - self._last_llm_time < LLM_MESSAGE_COOLDOWN:
            return None
        for need in ["hunger", "energy", "hygiene", "happiness"]:
            if need in triggered:
                self._last_llm_time = now
                self._pending_need  = need
                return need
        return None

    def set_message(self, message: str, duration: float = 6.0) -> None:
        self.current_message   = message
        self._message_timer    = 0.0
        self._message_duration = duration
        self.memory.add_raw(
            subject="yo", predicate="dije", object_=message[:50],
            poignancy=4.0, keywords=extract_keywords(message),
        )

    def _update_message_timer(self, delta: float) -> None:
        if self.current_message:
            self._message_timer += delta
            if self._message_timer >= self._message_duration:
                self.current_message = None
                self._message_timer  = 0.0

    # ------------------------------------------------------------------
    # Interacciones del usuario (teclado)
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Reproducción
    # ------------------------------------------------------------------

    def ready_to_reproduce(self) -> bool:
        if self.age < REPRODUCTION_MIN_AGE:        return False
        if self._reproduction_cooldown > 0:         return False
        n = self.needs
        return (
            n.hunger    <= (100.0 - REPRODUCTION_NEED_THRESHOLD) and
            n.hygiene   >= REPRODUCTION_NEED_THRESHOLD and
            n.happiness >= REPRODUCTION_NEED_THRESHOLD and
            n.energy    >= REPRODUCTION_NEED_THRESHOLD
        )

    def spawn_offspring(self, offspring_id: str) -> "Creature":
        angle = random.uniform(0, 2 * math.pi)
        ox = clamp(self.x + math.cos(angle) * OFFSPRING_SPAWN_RADIUS,
                   CREATURE_RADIUS, _AREA_W - CREATURE_RADIUS)
        oy = clamp(self.y + math.sin(angle) * OFFSPRING_SPAWN_RADIUS,
                   CREATURE_RADIUS, _AREA_H - CREATURE_RADIUS)

        offspring = Creature(offspring_id, x=ox, y=oy)
        offspring.generation = self.generation + 1

        for attr in ["hunger", "hygiene", "happiness", "energy"]:
            base = getattr(self.needs, attr)
            setattr(offspring.needs, attr,
                    clamp(base + random.uniform(-OFFSPRING_NEED_VARIANCE, OFFSPRING_NEED_VARIANCE),
                          NEED_MIN, NEED_MAX))

        self._reproduction_cooldown = REPRODUCTION_COOLDOWN
        self.memory.add_raw("yo", "me_dividí_en", offspring_id, poignancy=9.0,
                            keywords=["división", offspring_id])
        logger.info(f"Creature {self.id} (g{self.generation}) → {offspring_id} (g{offspring.generation})")
        return offspring

    # ------------------------------------------------------------------
    # Posición
    # ------------------------------------------------------------------

    @property
    def target_obj(self):
        """World object the creature is currently heading towards."""
        return self._target_obj

    @property
    def using_obj(self) -> bool:
        """True while the creature is actively using an object."""
        return self._using_obj

    @property
    def pos(self) -> tuple[float, float]:
        return self.x, self.y

    def distance_to(self, other: "Creature") -> float:
        return distance(self.pos, other.pos)

    def is_near(self, other: "Creature") -> bool:
        return self.distance_to(other) <= INTERACTION_RADIUS

    # ------------------------------------------------------------------
    # Persistencia
    # ------------------------------------------------------------------

    def save(self) -> None:
        path = os.path.join(DATA_DIR, f"{self.id}.json")
        atomic_write_json(path, {
            "id": self.id, "x": self.x, "y": self.y,
            "age": self.age, "generation": self.generation,
            "needs": self.needs.to_dict(), "memory": self.memory.to_list(),
        })

    def load(self) -> bool:
        data = load_json(os.path.join(DATA_DIR, f"{self.id}.json"))
        if not data:
            return False
        self.x          = data.get("x", self.x)
        self.y          = data.get("y", self.y)
        self.age        = data.get("age", 0.0)
        self.generation = data.get("generation", 0)
        self.needs.from_dict(data.get("needs", {}))
        self.memory.from_list(data.get("memory", []))
        return True

    def __repr__(self) -> str:
        return f"Creature({self.id!r}, pos=({self.x:.0f},{self.y:.0f}), {self.needs})"
