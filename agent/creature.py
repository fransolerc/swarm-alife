# =============================================================================
# agent/creature.py — Creature orchestrator (refactored)
# =============================================================================

import random
import time
import logging
import os
from typing import Optional

from agent.needs import Needs
from agent.memory.associative_memory import AssociativeMemory
from agent.navigation import Navigator, cell_center
from agent.inventory import Inventory
from agent.behavior.seek_food import SeekFoodBehavior

from config import (
    WINDOW_WIDTH, WINDOW_HEIGHT, TOOLBAR_HEIGHT,
    INTERACTION_RADIUS, LLM_MESSAGE_COOLDOWN, DATA_DIR,
    REPRODUCTION_MIN_AGE, REPRODUCTION_NEED_THRESHOLD,
    REPRODUCTION_COOLDOWN, OFFSPRING_NEED_VARIANCE,
    NEED_MIN, NEED_MAX, GRID_CELL,
    HUNGER_SEEK_THRESHOLD, WRITING_GEM_COST, WRITING_COOLDOWN,
)
from utils import clamp, distance, atomic_write_json, load_json, extract_keywords

logger = logging.getLogger(__name__)

_AREA_W = WINDOW_WIDTH
_AREA_H = WINDOW_HEIGHT - TOOLBAR_HEIGHT
_MAX_COL = _AREA_W // GRID_CELL - 1
_MAX_ROW = _AREA_H // GRID_CELL - 1


class Creature:
    def __init__(self, creature_id: str, x: Optional[float] = None, y: Optional[float] = None):
        self.id = creature_id

        # Grid positioning
        if x is not None and y is not None:
            self.grid_col = int(clamp(x // GRID_CELL, 1, _MAX_COL - 1))
            self.grid_row = int(clamp(y // GRID_CELL, 1, _MAX_ROW - 1))
        else:
            self.grid_col = random.randint(1, _MAX_COL - 1)
            self.grid_row = random.randint(1, _MAX_ROW - 1)

        self.x, self.y = cell_center(self.grid_col, self.grid_row)

        # Core systems
        self.needs = Needs()
        self.memory = AssociativeMemory()
        self.navigator = Navigator(self)
        self.inventory = Inventory(self.memory)

        # Behaviors
        self._food_behavior = SeekFoodBehavior(self)
        self._target_obj = None
        self._using_obj = False

        # State
        self.selected = False
        self.age = 0.0
        self.generation = 0
        self._reproduction_cooldown = 0.0
        self._writing_cooldown = 0.0

        # Messaging
        self._last_llm_time = 0.0
        self._pending_need: Optional[str] = None
        self.current_message: Optional[str] = None
        self._message_timer = 0.0
        self._message_duration = 6.0

        # Animation
        self.anim_t = random.uniform(0, 6.28)

        logger.info(f"Creature {self.id} created at cell ({self.grid_col},{self.grid_row})")

    # ------------------------------------------------------------------
    # Main update
    # ------------------------------------------------------------------

    def update(self, delta: float, world=None) -> Optional[str]:
        self.age += delta
        self._reproduction_cooldown = max(0.0, self._reproduction_cooldown - delta)
        self._writing_cooldown = max(0.0, self._writing_cooldown - delta)

        # Update systems
        if world is not None:
            self._update_seeking(delta, world)
            self._check_writing(world)

        self.navigator.update(delta, world, self._using_obj)
        triggered = self.needs.update(delta)
        self._update_message_timer(delta)

        # Check reproduction
        if self.ready_to_reproduce():
            return "reproduce"

        # Check LLM triggers
        if triggered:
            return self._check_llm_trigger(triggered)
        return None

    # ------------------------------------------------------------------
    # Seeking logic
    # ------------------------------------------------------------------

    def _update_seeking(self, delta: float, world) -> None:
        urgent = self.needs.most_urgent()

        # Hunger first
        if urgent == "hunger" or self.needs.hunger >= HUNGER_SEEK_THRESHOLD:
            self._food_behavior.execute(delta, world)
            return

        # No urgent needs - try carrying
        if urgent is None and self.inventory.can_carry(self.needs):
            from agent.behavior.carry_resource import CarryResourceBehavior
            carry = CarryResourceBehavior(self)
            carry.execute(delta, world)
            return

        # Urgent non-hunger needs
        if urgent:
            self._cancel_carrying()
            self._refresh_target(urgent, world)

            if self._target_obj is not None:
                if self._target_obj.in_range(self.x, self.y):
                    self._try_use_target(urgent)
                else:
                    self.navigator.navigate_to(world, self._target_obj.px, self._target_obj.py)

    def _refresh_target(self, urgent: str, world) -> None:
        if (self._target_obj is None
                or self._target_obj.need != urgent
                or not self._target_obj.can_use(self.id)):
            self._release_target()
            self._target_obj = world.nearest_for_need(urgent, self.x, self.y, self.id)
            self.navigator.clear_path()

    def _try_use_target(self, urgent: str) -> None:
        used = self._target_obj.use(self.id, self.needs)
        if used:
            self._using_obj = True
            self.navigator.clear_path()
            self.memory.add_raw(
                subject="yo", predicate="use",
                object_=self._target_obj.type.name.lower(),
                poignancy=5.0,
                keywords=[urgent, self._target_obj.type.name.lower()],
            )

    def _release_target(self) -> None:
        if self._target_obj is not None:
            self._target_obj.release(self.id)
        self._target_obj = None
        self._using_obj = False

    def _cancel_carrying(self) -> None:
        self.inventory.cancel()

    # ------------------------------------------------------------------
    # Diary writing
    # ------------------------------------------------------------------

    def _check_writing(self, world) -> None:
        if not self.inventory.can_carry(self.needs) or self._writing_cooldown > 0:
            return

        store = world.nearest_store(self.x, self.y)
        if store is None or store.stored_gems < WRITING_GEM_COST:
            return

        store.stored_gems -= WRITING_GEM_COST
        self._writing_cooldown = WRITING_COOLDOWN
        from agent.writing import trigger_writing
        trigger_writing(self, WRITING_GEM_COST)

    # ------------------------------------------------------------------
    # LLM communication
    # ------------------------------------------------------------------

    def _check_llm_trigger(self, triggered: list[str]) -> Optional[str]:
        now = time.time()
        if now - self._last_llm_time < LLM_MESSAGE_COOLDOWN:
            return None
        for need in ["hunger", "hygiene", "happiness"]:
            if need in triggered:
                self._last_llm_time = now
                self._pending_need = need
                return need
        return None

    def set_message(self, message: str, duration: float = 6.0) -> None:
        self.current_message = message
        self._message_timer = 0.0
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
                self._message_timer = 0.0

    # ------------------------------------------------------------------
    # User interactions
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

    # ------------------------------------------------------------------
    # Reproduction
    # ------------------------------------------------------------------

    def ready_to_reproduce(self) -> bool:
        if self.age < REPRODUCTION_MIN_AGE:
            return False
        if self._reproduction_cooldown > 0:
            return False
        n = self.needs
        return (
            n.hunger <= (100.0 - REPRODUCTION_NEED_THRESHOLD)
            and n.hygiene >= REPRODUCTION_NEED_THRESHOLD
            and n.happiness >= REPRODUCTION_NEED_THRESHOLD
        )

    def spawn_offspring(self, offspring_id: str) -> "Creature":
        nc, nr = self.navigator.find_empty_neighbor()
        ox, oy = cell_center(nc, nr)
        offspring = Creature(offspring_id, x=ox, y=oy)
        offspring.generation = self.generation + 1

        for attr in ["hunger", "hygiene", "happiness"]:
            base = getattr(self.needs, attr)
            setattr(offspring.needs, attr,
                    clamp(base + random.uniform(-OFFSPRING_NEED_VARIANCE, OFFSPRING_NEED_VARIANCE),
                          NEED_MIN, NEED_MAX))

        self._reproduction_cooldown = REPRODUCTION_COOLDOWN
        self.memory.add_raw("yo", "me_dividi_en", offspring_id, poignancy=9.0,
                            keywords=["division", offspring_id])
        logger.info(f"Creature {self.id} (g{self.generation}) → {offspring_id} (g{offspring.generation})")
        return offspring

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def speed_real(self) -> float:
        return self.navigator.speed_real

    @property
    def target_obj(self):
        return self._target_obj

    @property
    def using_obj(self) -> bool:
        return self._using_obj

    @property
    def carrying(self) -> Optional[str]:
        return self.inventory.resource

    @property
    def shake_target(self):
        return self._food_behavior.shake_target

    @property
    def pos(self) -> tuple[float, float]:
        return self.x, self.y

    def distance_to(self, other: "Creature") -> float:
        return distance(self.pos, other.pos)

    def is_near(self, other: "Creature") -> bool:
        return self.distance_to(other) <= INTERACTION_RADIUS

    # ------------------------------------------------------------------
    # Persistence
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

        self.x, self.y = cell_center(self.grid_col, self.grid_row)
        self.navigator.reset_to(self.grid_col, self.grid_row)
        self.age = data.get("age", 0.0)
        self.generation = data.get("generation", 0)
        self.needs.from_dict(data.get("needs", {}))
        self.memory.from_list(data.get("memory", []))
        return True

    def __repr__(self) -> str:
        carry = f", carrying={self.inventory.resource}" if self.inventory.is_carrying else ""
        path = f", path={len(self.navigator._path)}steps" if self.navigator.has_path else ""
        return (
            f"Creature({self.id!r}, cell=({self.grid_col},{self.grid_row}), "
            f"pos=({self.x:.0f},{self.y:.0f}), {self.needs}{carry}{path})"
        )
