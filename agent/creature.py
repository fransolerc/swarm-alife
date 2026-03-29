# =============================================================================
# agent/creature.py — swarm-alife
# =============================================================================

import heapq
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
    CARRY_NEED_THRESHOLD,
)
from utils import clamp, distance, atomic_write_json, load_json, extract_keywords

logger = logging.getLogger(__name__)

_AREA_W  = WINDOW_WIDTH
_AREA_H  = WINDOW_HEIGHT - TOOLBAR_HEIGHT
_MAX_COL = _AREA_W // GRID_CELL - 1
_MAX_ROW = _AREA_H // GRID_CELL - 1

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

        self._target_col: int      = self.grid_col
        self._target_row: int      = self.grid_row
        self._move_progress: float = 1.0
        self._src_x: float         = self.x
        self._src_y: float         = self.y

        self._wander_timer: float    = 0.0
        self._wander_interval: float = random.uniform(*WANDER_INTERVAL)

        # --- Navegacion A* ---
        # _path: lista de celdas (col, row) pendientes de recorrer (no incluye celda actual)
        # _path_goal: goal para el que se calculó el path, para evitar recomputos innecesarios
        self._path: list[tuple[int, int]]          = []
        self._path_goal: Optional[tuple[int, int]] = None

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

        self._target_obj  = None
        self._using_obj: bool  = False
        self._use_timer: float = 0.0

        self._shake_target = None

        self._carrying: Optional[str] = None
        self._carry_store              = None

        self.anim_t: float     = random.uniform(0, 6.28)
        self.speed_real: float = 0.0

        logger.info(f"Creature {self.id} created at cell ({self.grid_col},{self.grid_row})")

    # ------------------------------------------------------------------
    # Navegacion A*
    # ------------------------------------------------------------------

    def _astar(self, goal_col: int, goal_row: int, world) -> list[tuple[int, int]]:
        """
        A* desde la celda actual hasta (goal_col, goal_row).
        Si el goal está bloqueado (arbol, almacen), acepta cualquier celda
        libre adyacente al goal como destino valido.
        Devuelve la lista de celdas a recorrer, sin incluir la celda de inicio.
        """
        start = (self.grid_col, self.grid_row)
        goal  = (goal_col, goal_row)

        if start == goal:
            return []

        goal_blocked = (
            world is not None
            and not self._cell_valid(goal_col, goal_row, world)
        )

        def is_terminal(col: int, row: int) -> bool:
            if (col, row) == goal:
                return True
            if goal_blocked:
                return abs(col - goal_col) + abs(row - goal_row) == 1
            return False

        def h(col: int, row: int) -> int:
            return abs(col - goal_col) + abs(row - goal_row)

        open_set: list = [(h(*start), 0, start[0], start[1])]
        came_from: dict = {}
        g_score: dict   = {start: 0}

        while open_set:
            _, g, col, row = heapq.heappop(open_set)

            if is_terminal(col, row):
                path: list[tuple[int, int]] = []
                cur = (col, row)
                while cur in came_from:
                    path.append(cur)
                    cur = came_from[cur]
                path.reverse()
                return path

            for dc, dr in _DIRECTIONS:
                nc, nr   = col + dc, row + dr
                neighbor = (nc, nr)
                if not self._cell_valid(nc, nr, world):
                    continue
                new_g = g + 1
                if new_g < g_score.get(neighbor, 10_000):
                    g_score[neighbor]   = new_g
                    came_from[neighbor] = (col, row)
                    heapq.heappush(open_set, (new_g + h(nc, nr), new_g, nc, nr))

        return []

    def _navigate_to(self, tx: float, ty: float, world) -> None:
        """
        Establece navegacion A* hacia la posicion en pixeles (tx, ty).
        Solo recalcula el path si el goal de cuadricula cambio o el path
        quedo vacio o su primer paso esta bloqueado.
        """
        goal = (int(tx // GRID_CELL), int(ty // GRID_CELL))

        # Invalidar si el proximo paso del path esta bloqueado
        if self._path and not self._cell_valid(self._path[0][0], self._path[0][1], world):
            self._path      = []
            self._path_goal = None

        if self._path_goal != goal or not self._path:
            self._path_goal = goal
            self._path      = self._astar(goal[0], goal[1], world)

    def _clear_path(self) -> None:
        """Cancela la navegacion activa."""
        self._path      = []
        self._path_goal = None

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
    # Seeking principal
    # ------------------------------------------------------------------

    def _update_seeking(self, delta: float, world) -> None:
        from config import HUNGER_SEEK_THRESHOLD

        if self._handle_active_use(delta):
            return

        urgent = self.needs.most_urgent()

        if urgent == "hunger" or self.needs.hunger >= HUNGER_SEEK_THRESHOLD:
            if self._seek_food(world):
                return

        if urgent is None:
            if not self._update_carrying(world):
                self._reset_seeking()
            return

        self._cancel_carrying()
        self._shake_target = None

        self._refresh_target(urgent, world)

        if self._target_obj is None:
            self._clear_path()
            return

        if self._target_obj.in_range(self.x, self.y):
            self._try_use_target(urgent)
        else:
            self._navigate_to(self._target_obj.px, self._target_obj.py, world)

    def _handle_active_use(self, delta: float) -> bool:
        from config import OBJ_USE_DURATION
        if not (self._using_obj and self._target_obj is not None):
            return False
        self._use_timer += delta
        duration = OBJ_USE_DURATION.get(self._target_obj.type.name, 3.0)
        if self._use_timer < duration:
            self._clear_path()
        else:
            self._using_obj  = False
            self._use_timer  = 0.0
            self._target_obj = None
        return True

    # ------------------------------------------------------------------
    # Alimentacion: manzanas en suelo -> sacudir arbol
    # ------------------------------------------------------------------

    def _seek_food(self, world) -> bool:
        apple = world.nearest_apple(self.x, self.y)
        if apple is not None:
            self._shake_target = None
            if apple.in_range(self.x, self.y):
                world.pick_apple(apple, self.needs)
                self.memory.add_raw("yo", "comi", "manzana", poignancy=5.0,
                                    keywords=["manzana", "hambre"])
                self._target_obj = None
                self._using_obj  = False
                self._clear_path()
                logger.debug(f"{self.id}: ate apple")
            else:
                self._navigate_to(apple.x, apple.y, world)
            return True

        tree = world.nearest_shakeable_tree(self.x, self.y)
        if tree is not None:
            self._shake_target = tree
            if tree.in_shake_range(self.x, self.y):
                items = world.shake_tree_at(tree.px, tree.py)
                self._shake_target = None
                self._clear_path()
                if items:
                    self.memory.add_raw("yo", "sacudi", "arbol", poignancy=4.0,
                                        keywords=["arbol", "manzana", "hambre"])
                    logger.debug(f"{self.id}: shook tree ({tree.col},{tree.row}), "
                                 f"{len(items)} apple(s)")
            else:
                self._navigate_to(tree.px, tree.py, world)
            return True

        return False

    def _reset_seeking(self) -> None:
        self._target_obj   = None
        self._using_obj    = False
        self._use_timer    = 0.0
        self._shake_target = None
        self._clear_path()

    def _refresh_target(self, urgent: str, world) -> None:
        if (self._target_obj is None
                or self._target_obj.need != urgent
                or not self._target_obj.can_use(self.id)):
            self._target_obj = world.nearest_for_need(urgent, self.x, self.y, self.id)
            self._use_timer  = 0.0
            self._clear_path()

    def _try_use_target(self, urgent: str) -> None:
        used = self._target_obj.use(self.id, self.needs)
        if used:
            self._using_obj = True
            self._use_timer = 0.0
            self._clear_path()
            self.memory.add_raw(
                subject="yo", predicate="use",
                object_=self._target_obj.type.name.lower(),
                poignancy=5.0,
                keywords=[urgent, self._target_obj.type.name.lower()],
            )

    # ------------------------------------------------------------------
    # Acarreo autonomo al almacen
    # ------------------------------------------------------------------

    def _needs_comfortable(self) -> bool:
        n = self.needs
        return (
            n.hunger    <= (NEED_MAX - CARRY_NEED_THRESHOLD)
            and n.hygiene   >= CARRY_NEED_THRESHOLD
            and n.happiness >= CARRY_NEED_THRESHOLD
            and n.energy    >= CARRY_NEED_THRESHOLD
        )

    def _update_carrying(self, world) -> bool:
        if not self._needs_comfortable():
            self._cancel_carrying()
            return False

        store = world.nearest_store(self.x, self.y)
        if store is None:
            return False

        if self._carrying is None:
            return self._try_pick_resource(world, store)

        return self._deliver_to_store(store, world)

    def _try_pick_resource(self, world, store) -> bool:
        apple = world.nearest_apple(self.x, self.y)
        if apple is not None:
            if apple.in_range(self.x, self.y):
                if world.pick_apple_to_carry(apple):
                    self._carrying    = "apple"
                    self._carry_store = store
                    self._clear_path()
                    self.memory.add_raw("yo", "recogi_para_almacen", "manzana",
                                        poignancy=4.0, keywords=["manzana", "almacen"])
                    logger.info(f"{self.id}: picked apple to carry → "
                                f"store ({store.col},{store.row})")
            else:
                self._navigate_to(apple.x, apple.y, world)
            return True

        if world.wood > 0:
            world.wood -= 1
            self._carrying    = "wood"
            self._carry_store = store
            self._clear_path()
            self.memory.add_raw("yo", "recogi_para_almacen", "madera",
                                poignancy=4.0, keywords=["madera", "almacen"])
            logger.info(f"{self.id}: picked wood → store ({store.col},{store.row}), "
                        f"world.wood={world.wood}")
            return True

        return False

    def _deliver_to_store(self, store, world) -> bool:
        self._carry_store = store

        if store.in_range(self.x, self.y):
            if self._carrying == "apple":
                store.deposit_apple(1)
                self.memory.add_raw("yo", "deposite", "manzana",
                                    poignancy=3.0, keywords=["manzana", "almacen"])
                logger.info(f"{self.id}: deposited apple → "
                            f"store ({store.col},{store.row}) "
                            f"[apples={store.stored_apples} wood={store.stored_wood}]")
            elif self._carrying == "wood":
                store.deposit_wood(1)
                self.memory.add_raw("yo", "deposite", "madera",
                                    poignancy=3.0, keywords=["madera", "almacen"])
                logger.info(f"{self.id}: deposited wood → "
                            f"store ({store.col},{store.row}) "
                            f"[apples={store.stored_apples} wood={store.stored_wood}]")
            self._cancel_carrying()
            return False  # tarea completada: ya no hay carga activa

        self._navigate_to(store.px, store.py, world)
        return True  # aún navegando hacia el almacén

    def _cancel_carrying(self) -> None:
        self._carrying    = None
        self._carry_store = None

    # ------------------------------------------------------------------
    # Movimiento por cuadricula — sigue el path A*
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
        Siguiente celda a la que moverse.
        Prioridad: seguir path A* > deambular al expirar el timer.
        """
        if self._path:
            next_col, next_row = self._path[0]
            if self._cell_valid(next_col, next_row, world):
                self._path.pop(0)
                return next_col, next_row
            else:
                # Celda del path bloqueada: limpiar, el siguiente tick de seeking
                # llamara a _navigate_to y recomputara el path.
                self._path      = []
                self._path_goal = None
                # Intentar avanzar en cualquier direccion libre como fallback inmediato
                dirs = list(_DIRECTIONS)
                random.shuffle(dirs)
                result = self._try_directions(dirs, world)
                if result is not None:
                    return result

        # Deambulacion aleatoria cuando no hay path activo
        if self._wander_timer >= self._wander_interval:
            self._wander_timer    = 0.0
            self._wander_interval = random.uniform(*WANDER_INTERVAL)
            dirs = list(_DIRECTIONS)
            random.shuffle(dirs)
            result = self._try_directions(dirs, world)
            if result is not None:
                return result

        return self.grid_col, self.grid_row

    def _try_directions(self, dirs: list, world) -> Optional[tuple[int, int]]:
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
        if self.age < REPRODUCTION_MIN_AGE:   return False
        if self._reproduction_cooldown > 0:    return False
        n = self.needs
        return (
            n.hunger    <= (100.0 - REPRODUCTION_NEED_THRESHOLD)
            and n.hygiene   >= REPRODUCTION_NEED_THRESHOLD
            and n.happiness >= REPRODUCTION_NEED_THRESHOLD
            and n.energy    >= REPRODUCTION_NEED_THRESHOLD
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
        logger.info(f"Creature {self.id} (g{self.generation}) → "
                    f"{offspring_id} (g{offspring.generation})")
        return offspring

    # ------------------------------------------------------------------
    # Propiedades publicas
    # ------------------------------------------------------------------

    @property
    def target_obj(self):
        return self._target_obj

    @property
    def using_obj(self) -> bool:
        return self._using_obj

    @property
    def carrying(self) -> Optional[str]:
        return self._carrying

    @property
    def shake_target(self):
        return self._shake_target

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
        self.x, self.y = _cell_center(self.grid_col, self.grid_row)
        self._target_col    = self.grid_col
        self._target_row    = self.grid_row
        self._move_progress = 1.0
        self.age        = data.get("age", 0.0)
        self.generation = data.get("generation", 0)
        self.needs.from_dict(data.get("needs", {}))
        self.memory.from_list(data.get("memory", []))
        return True

    def __repr__(self) -> str:
        carry = f", carrying={self._carrying}" if self._carrying else ""
        path  = f", path={len(self._path)}steps" if self._path else ""
        return (
            f"Creature({self.id!r}, cell=({self.grid_col},{self.grid_row}), "
            f"pos=({self.x:.0f},{self.y:.0f}), {self.needs}{carry}{path})"
        )
