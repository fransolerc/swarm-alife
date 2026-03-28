# =============================================================================
# agent/creature.py — swarm-alife
# =============================================================================

import random
import time
import logging
import os
from typing import Optional

from agent.needs import Needs
from agent.memory.associative_memory import AssociativeMemory
from config import (
    WINDOW_WIDTH, WINDOW_HEIGHT, TOOLBAR_HEIGHT,
    CREATURE_SPEED, WANDER_INTERVAL, INTERACTION_RADIUS,
    LLM_MESSAGE_COOLDOWN, DATA_DIR,
    REPRODUCTION_MIN_AGE, REPRODUCTION_NEED_THRESHOLD,
    REPRODUCTION_COOLDOWN, OFFSPRING_NEED_VARIANCE,
    NEED_MIN, NEED_MAX, GRID_CELL,
)
from utils import clamp, distance, atomic_write_json, load_json, extract_keywords


logger = logging.getLogger(__name__)

_AREA_W  = WINDOW_WIDTH
_AREA_H  = WINDOW_HEIGHT - TOOLBAR_HEIGHT
_MAX_COL = _AREA_W // GRID_CELL - 1
_MAX_ROW = _AREA_H // GRID_CELL - 1

# Cuatro direcciones cardinales (dc, dr)
_DIRECTIONS = [(1, 0), (-1, 0), (0, 1), (0, -1)]


def _cell_center(col: int, row: int) -> tuple[float, float]:
    return col * GRID_CELL + GRID_CELL / 2, row * GRID_CELL + GRID_CELL / 2


class Creature:
    def __init__(self, creature_id: str, x: Optional[float] = None, y: Optional[float] = None):
        self.id = creature_id

        if x is not None and y is not None:
            self.grid_col = int(clamp(x // GRID_CELL, 1, _MAX_COL - 1))
            self.grid_row = int(clamp(y // GRID_CELL, 1, _MAX_ROW - 1))
        else:
            self.grid_col = random.randint(1, _MAX_COL - 1)
            self.grid_row = random.randint(1, _MAX_ROW - 1)

        self.x, self.y = _cell_center(self.grid_col, self.grid_row)

        # Estado de movimiento por celda
        self._target_col: int      = self.grid_col
        self._target_row: int      = self.grid_row
        self._move_progress: float = 1.0   # 1.0 = en celda actual, listo para moverse
        self._src_x: float         = self.x
        self._src_y: float         = self.y

        # Deambulacion
        self._wander_timer: float    = 0.0
        self._wander_interval: float = random.uniform(*WANDER_INTERVAL)

        # Direccion preferida desde seeking (0,0 = libre)
        self._seek_dir: tuple[int, int] = (0, 0)

        self.needs  = Needs()
        self.memory = AssociativeMemory()

        self._last_llm_time: float          = 0.0
        self._pending_need: Optional[str]   = None
        self.current_message: Optional[str] = None
        self._message_timer: float          = 0.0
        self._message_duration: float       = 6.0

        self.selected: bool = False

        self.age: float                    = 0.0
        self._reproduction_cooldown: float = 0.0
        self.generation: int               = 0

        # Seeking de objetos
        self._target_obj               = None   # WorldObject | None
        self._using_obj: bool          = False
        self._use_timer: float         = 0.0

        # Animacion — leidos por el renderer, nunca afectan la logica
        self.anim_t: float     = random.uniform(0, 6.28)
        self.speed_real: float = 0.0

        logger.info(f"Creature {self.id} created at cell ({self.grid_col},{self.grid_row})")

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
    # Liberacion centralizada de target
    # ------------------------------------------------------------------

    def _release_target(self) -> None:
        """Libera el objeto actualmente en target y resetea estado de uso."""
        if self._target_obj is not None:
            self._target_obj.release(self.id)
        self._target_obj = None
        self._using_obj  = False
        self._use_timer  = 0.0
        self._seek_dir   = (0, 0)

    # ------------------------------------------------------------------
    # Seeking de objetos del mundo
    # ------------------------------------------------------------------

    def _update_seeking(self, delta: float, world) -> None:
        from config import HUNGER_SEEK_THRESHOLD, OBJ_USE_DURATION
        from world.progression import game_progress

        # En uso activo: completar la duracion antes de cualquier otra logica
        if self._using_obj and self._target_obj is not None:
            self._use_timer += delta
            duration = OBJ_USE_DURATION.get(self._target_obj.type.name, 3.0)
            if self._use_timer < duration:
                self._seek_dir = (0, 0)   # no moverse mientras usa
            else:
                self._release_target()
            return

        urgent = self.needs.most_urgent()

        # --- Hambre: manzanas en el suelo primero ---
        if urgent == "hunger" or self.needs.hunger >= HUNGER_SEEK_THRESHOLD:
            apple = world.nearest_apple(self.x, self.y)
            if apple is not None:
                if apple.in_range(self.x, self.y):
                    world.pick_apple(apple, self.needs)
                    self.memory.add_raw("yo", "comi", "manzana", poignancy=5.0,
                                        keywords=["manzana", "hambre"])
                    self._release_target()
                else:
                    self._steer_toward(apple.x, apple.y)
                return

            # No hay manzanas en el suelo: zarandear arbol (nivel 2+)
            if game_progress.trees_have_apples:
                tree = world.nearest_shakeable_tree(self.x, self.y)
                if tree is not None:
                    if tree.in_range(self.x, self.y):
                        world.shake_tree_obj(tree)
                        self.memory.add_raw("yo", "zarandee", "arbol", poignancy=4.0,
                                            keywords=["arbol", "manzana", "hambre"])
                        self._seek_dir = (0, 0)
                    else:
                        self._steer_toward(tree.px, tree.py)
                    return

        if urgent is None:
            self._release_target()
            return

        # --- Buscar nuevo target si el actual no es valido ---
        if (self._target_obj is None
                or self._target_obj.need != urgent
                or not self._target_obj.can_use(self.id)):
            self._release_target()
            self._target_obj = world.nearest_for_need(urgent, self.x, self.y, self.id)

        if self._target_obj is None:
            self._seek_dir = (0, 0)
            return

        if self._target_obj.in_range(self.x, self.y):
            used = self._target_obj.use(self.id, self.needs)
            if used:
                self._using_obj = True
                self._use_timer = 0.0
                self._seek_dir  = (0, 0)
                self.memory.add_raw(
                    subject="yo", predicate="use",
                    object_=self._target_obj.type.name.lower(),
                    poignancy=5.0,
                    keywords=[urgent, self._target_obj.type.name.lower()],
                )
            else:
                # Objeto ocupado por otra criatura
                self._release_target()
        else:
            self._steer_toward(self._target_obj.px, self._target_obj.py)

    def _steer_toward(self, tx: float, ty: float) -> None:
        """Establece la direccion cardinal mas cercana al destino."""
        dx = tx - self.x
        dy = ty - self.y
        if abs(dx) >= abs(dy):
            self._seek_dir = (1 if dx > 0 else -1, 0)
        else:
            self._seek_dir = (0, 1 if dy > 0 else -1)

    # ------------------------------------------------------------------
    # Movimiento por cuadricula
    # ------------------------------------------------------------------

    def _update_movement(self, delta: float, world=None) -> None:
        speed = CREATURE_SPEED
        if self.needs.energy <= 20.0:   speed *= 0.4
        elif self.needs.energy <= 40.0: speed *= 0.7

        progress_rate = speed / GRID_CELL

        if self._move_progress < 1.0:
            self._move_progress = min(1.0, self._move_progress + progress_rate * delta)
            t = self._move_progress
            dst_x, dst_y = _cell_center(self._target_col, self._target_row)
            self.x = self._src_x + (dst_x - self._src_x) * t
            self.y = self._src_y + (dst_y - self._src_y) * t
            self.speed_real = speed

            if self._move_progress >= 1.0:
                self.grid_col = self._target_col
                self.grid_row = self._target_row
                self.x, self.y = _cell_center(self.grid_col, self.grid_row)
                self.speed_real = 0.0

        if self._move_progress >= 1.0:
            if self._using_obj:
                self.speed_real = 0.0
                self.anim_t += delta
                return

            self._wander_timer += delta
            nc, nr = self._pick_next_cell(world)
            if nc != self.grid_col or nr != self.grid_row:
                self._src_x, self._src_y = self.x, self.y
                self._target_col    = nc
                self._target_row    = nr
                self._move_progress = 0.0
            else:
                self.speed_real = 0.0

        self.anim_t += delta

    def _pick_next_cell(self, world) -> tuple[int, int]:
        """
        Devuelve la celda adyacente a la que moverse.
        Si hay seek_dir, prioriza esa direccion con fallback a perpendiculares.
        Si no, deambula cuando expira el timer.
        """
        if self._seek_dir != (0, 0):
            dc, dr = self._seek_dir
            nc, nr = self.grid_col + dc, self.grid_row + dr
            if self._cell_valid(nc, nr, world):
                return nc, nr
            perp = [(-dr, dc), (dr, -dc)]
            random.shuffle(perp)
            result = self._try_directions(perp, world)
            return result if result is not None else (self.grid_col, self.grid_row)

        if self._wander_timer >= self._wander_interval:
            self._wander_timer    = 0.0
            self._wander_interval = random.uniform(*WANDER_INTERVAL)
            dirs = list(_DIRECTIONS)
            random.shuffle(dirs)
            result = self._try_directions(dirs, world)
            if result is not None:
                return result

        return self.grid_col, self.grid_row

    def _try_directions(self, dirs: list, world) -> tuple[int, int] | None:
        for dc, dr in dirs:
            nc, nr = self.grid_col + dc, self.grid_row + dr
            if self._cell_valid(nc, nr, world):
                return nc, nr
        return None

    @staticmethod
    def _cell_valid(col: int, row: int, world) -> bool:
        if col < 0 or col > _MAX_COL or row < 0 or row > _MAX_ROW:
            return False
        if world is not None and world.is_blocked(col, row):
            return False
        return True

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
    # Interacciones del usuario
    # ------------------------------------------------------------------

    def feed(self) -> None:
        self.needs.feed()
        self.memory.add_raw("usuario", "me_alimento", "comida", poignancy=6.0)

    def shower(self) -> None:
        self.needs.shower()
        self.memory.add_raw("usuario", "me_ducho", "agua", poignancy=5.0)

    def play(self) -> None:
        self.needs.play()
        self.memory.add_raw("usuario", "jugo_conmigo", "juego", poignancy=7.0)

    def sleep(self) -> None:
        self.needs.sleep()
        self.memory.add_raw("yo", "dormi", "descanso", poignancy=3.0)

    # ------------------------------------------------------------------
    # Reproduccion
    # ------------------------------------------------------------------

    def ready_to_reproduce(self) -> bool:
        if self.age < REPRODUCTION_MIN_AGE:       return False
        if self._reproduction_cooldown > 0:        return False
        n = self.needs
        return (
            n.hunger    <= (100.0 - REPRODUCTION_NEED_THRESHOLD) and
            n.hygiene   >= REPRODUCTION_NEED_THRESHOLD and
            n.happiness >= REPRODUCTION_NEED_THRESHOLD and
            n.energy    >= REPRODUCTION_NEED_THRESHOLD
        )

    def spawn_offspring(self, offspring_id: str) -> "Creature":
        dirs = list(_DIRECTIONS)
        random.shuffle(dirs)
        oc, or_ = self.grid_col, self.grid_row
        for dc, dr in dirs:
            nc, nr = self.grid_col + dc, self.grid_row + dr
            if 0 <= nc <= _MAX_COL and 0 <= nr <= _MAX_ROW:
                oc, or_ = nc, nr
                break

        ox, oy = _cell_center(oc, or_)
        offspring = Creature(offspring_id, x=ox, y=oy)
        offspring.generation = self.generation + 1

        for attr in ["hunger", "hygiene", "happiness", "energy"]:
            base = getattr(self.needs, attr)
            setattr(offspring.needs, attr,
                    clamp(base + random.uniform(-OFFSPRING_NEED_VARIANCE, OFFSPRING_NEED_VARIANCE),
                          NEED_MIN, NEED_MAX))

        self._reproduction_cooldown = REPRODUCTION_COOLDOWN
        self.memory.add_raw("yo", "me_dividi_en", offspring_id, poignancy=9.0,
                            keywords=["division", offspring_id])
        logger.info(f"Creature {self.id} (g{self.generation}) -> {offspring_id} (g{offspring.generation})")
        return offspring

    # ------------------------------------------------------------------
    # Propiedades
    # ------------------------------------------------------------------

    @property
    def target_obj(self):
        return self._target_obj

    @property
    def using_obj(self) -> bool:
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
            "grid_col": self.grid_col, "grid_row": self.grid_row,
            "age": self.age, "generation": self.generation,
            "needs": self.needs.to_dict(), "memory": self.memory.to_list(),
        })

    def load(self) -> bool:
        data = load_json(os.path.join(DATA_DIR, f"{self.id}.json"))
        if not data:
            return False
        if "grid_col" in data and "grid_row" in data:
            self.grid_col = int(clamp(data["grid_col"], 0, _MAX_COL))
            self.grid_row = int(clamp(data["grid_row"], 0, _MAX_ROW))
        else:
            sx = data.get("x", self.x)
            sy = data.get("y", self.y)
            self.grid_col = int(clamp(sx // GRID_CELL, 0, _MAX_COL))
            self.grid_row = int(clamp(sy // GRID_CELL, 0, _MAX_ROW))
        self.x, self.y      = _cell_center(self.grid_col, self.grid_row)
        self._target_col    = self.grid_col
        self._target_row    = self.grid_row
        self._move_progress = 1.0
        self.age        = data.get("age", 0.0)
        self.generation = data.get("generation", 0)
        self.needs.from_dict(data.get("needs", {}))
        self.memory.from_list(data.get("memory", []))
        return True

    def __repr__(self) -> str:
        return (
            f"Creature({self.id!r}, cell=({self.grid_col},{self.grid_row}), "
            f"pos=({self.x:.0f},{self.y:.0f}), {self.needs})"
        )
