# =============================================================================
# world/objects.py — swarm-alife
# =============================================================================

import random
import logging
import math
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

from config import (
    GRID_CELL, OBJECT_USE_RANGE, OBJECT_USE_COOLDOWN,
    BATH_HYGIENE_RESTORE, BALL_HAPPINESS_BONUS, BALL_ENERGY_COST, BED_ENERGY_RESTORE,
    WINDOW_WIDTH, WINDOW_HEIGHT, UI_PANEL_WIDTH,
    STUMP_DURATION, WOOD_PER_TREE,
)
from utils import distance, clamp

logger = logging.getLogger(__name__)

_AREA_W = WINDOW_WIDTH - UI_PANEL_WIDTH
_COLS   = _AREA_W      // GRID_CELL
_ROWS   = WINDOW_HEIGHT // GRID_CELL

# Manzanas
APPLE_MAX_PER_TREE  = 3
APPLE_REGROW_TIME   = 45.0
APPLE_ROT_TIME      = 30.0
APPLE_PICK_RANGE    = 28.0
APPLE_HUNGER_VALUE  = 30.0
SHAKE_COOLDOWN      = 8.0
APPLE_TREE_CHANCE   = 0.6


class ObjType(Enum):
    TREE  = auto()
    BATH  = auto()
    BALL  = auto()
    BED   = auto()


OBJ_NEED: dict[ObjType, Optional[str]] = {
    ObjType.TREE:  None,
    ObjType.BATH:  "hygiene",
    ObjType.BALL:  "happiness",
    ObjType.BED:   "energy",
}

OBJ_LABEL: dict[ObjType, str] = {
    ObjType.TREE:  "árbol",
    ObjType.BATH:  "bañera",
    ObjType.BALL:  "pelota",
    ObjType.BED:   "cama",
}


# =============================================================================
# GroundItem — manzana en el suelo
# =============================================================================

@dataclass
class GroundItem:
    x:   float
    y:   float
    age: float = 0.0

    @property
    def rotten(self) -> bool:
        return self.age >= APPLE_ROT_TIME

    def update(self, delta: float) -> None:
        self.age += delta

    def in_range(self, cx: float, cy: float) -> bool:
        return distance((cx, cy), (self.x, self.y)) <= APPLE_PICK_RANGE


# =============================================================================
# WorldObject
# =============================================================================

@dataclass
class WorldObject:
    type: ObjType
    col:  int
    row:  int

    _cooldowns:    dict  = field(default_factory=dict,  repr=False)
    has_apples:    bool  = field(default=False,          repr=False)
    apple_count:   int   = field(default=0,              repr=False)
    _regrow_timer: float = field(default=0.0,            repr=False)
    _shake_cd:     float = field(default=0.0,            repr=False)
    shake_t:       float = field(default=0.0,            repr=False)

    # Tala
    chopped:       bool  = field(default=False,          repr=False)
    stump_timer:   float = field(default=0.0,            repr=False)

    def __post_init__(self):
        if self.type == ObjType.TREE and self.has_apples:
            self.apple_count = APPLE_MAX_PER_TREE

    @property
    def px(self) -> float:
        return self.col * GRID_CELL + GRID_CELL / 2

    @property
    def py(self) -> float:
        return self.row * GRID_CELL + GRID_CELL / 2

    @property
    def pos(self) -> tuple[float, float]:
        return self.px, self.py

    @property
    def blocks_path(self) -> bool:
        return self.type == ObjType.TREE  # tocón también bloquea mientras existe

    @property
    def need(self) -> Optional[str]:
        return OBJ_NEED[self.type]

    def in_range(self, cx: float, cy: float) -> bool:
        return distance((cx, cy), self.pos) <= OBJECT_USE_RANGE

    def can_use(self, creature_id: str) -> bool:
        return self._cooldowns.get(creature_id, 0) <= 0

    def use(self, creature_id: str, needs) -> bool:
        if not self.can_use(creature_id):
            return False
        if self.type == ObjType.TREE:
            return False
        if self.type == ObjType.BATH:
            needs.shower_amount(BATH_HYGIENE_RESTORE)
        elif self.type == ObjType.BALL:
            needs.play_amount(BALL_HAPPINESS_BONUS, BALL_ENERGY_COST)
        elif self.type == ObjType.BED:
            needs.sleep_amount(BED_ENERGY_RESTORE)
        self._cooldowns[creature_id] = OBJECT_USE_COOLDOWN
        return True

    # --- Árbol: zarandear ---

    def can_shake(self) -> bool:
        return (self.type == ObjType.TREE and self.has_apples
                and self._shake_cd <= 0 and not self.chopped)

    def shake(self) -> list[GroundItem]:
        self.shake_t = 0.4
        if not self.has_apples or self.apple_count == 0 or self.chopped:
            return []
        n_fall = random.randint(1, min(2, self.apple_count))
        self.apple_count -= n_fall
        self._shake_cd    = SHAKE_COOLDOWN
        items = []
        for _ in range(n_fall):
            angle = random.uniform(0, 2 * math.pi)
            dist  = random.uniform(GRID_CELL * 0.6, GRID_CELL * 1.2)
            ix    = clamp(self.px + math.cos(angle) * dist, 8, _AREA_W - 8)
            iy    = clamp(self.py + math.sin(angle) * dist, 8, WINDOW_HEIGHT - 8)
            items.append(GroundItem(x=ix, y=iy))
        logger.info(f"Tree ({self.col},{self.row}) shaken: {n_fall} apple(s)")
        return items

    # --- Árbol: talar ---

    def chop(self) -> bool:
        """Tala el árbol. Devuelve True si se taló."""
        if self.type != ObjType.TREE or self.chopped:
            return False
        self.chopped      = True
        self.stump_timer  = 0.0
        self.has_apples   = False
        self.apple_count  = 0
        logger.info(f"Tree ({self.col},{self.row}) chopped")
        return True

    def update(self, delta: float) -> None:
        for cid in self._cooldowns.copy():
            self._cooldowns[cid] = max(0.0, self._cooldowns[cid] - delta)
        if self.type == ObjType.TREE:
            if not self.chopped:
                if self._shake_cd > 0:
                    self._shake_cd = max(0.0, self._shake_cd - delta)
                if self.shake_t > 0:
                    self.shake_t = max(0.0, self.shake_t - delta)
                if self.has_apples and self.apple_count < APPLE_MAX_PER_TREE:
                    self._regrow_timer += delta
                    if self._regrow_timer >= APPLE_REGROW_TIME:
                        self.apple_count  += 1
                        self._regrow_timer = 0.0
            else:
                self.stump_timer += delta

    @property
    def stump_expired(self) -> bool:
        return self.chopped and self.stump_timer >= STUMP_DURATION

    def to_dict(self) -> dict:
        d = {"type": self.type.name, "col": self.col, "row": self.row}
        if self.type == ObjType.TREE:
            d["has_apples"]  = self.has_apples
            d["apple_count"] = self.apple_count
            d["chopped"]     = self.chopped
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "WorldObject":
        obj = cls(type=ObjType[d["type"]], col=d["col"], row=d["row"])
        if obj.type == ObjType.TREE:
            obj.has_apples  = d.get("has_apples", False)
            obj.apple_count = d.get("apple_count", 0)
            obj.chopped     = d.get("chopped", False)
        return obj


# =============================================================================
# WorldMap
# =============================================================================

class WorldMap:
    def __init__(self):
        self._objects:      list[WorldObject] = []
        self._ground_items: list[GroundItem]  = []
        self.wood: int = 0   # madera recolectada (recurso global)

    # --- Colocación ---

    def place(self, obj_type: ObjType, col: int, row: int) -> bool:
        if not self._in_bounds(col, row):
            return False
        if self.get_at(col, row) is not None:
            return False
        obj = WorldObject(type=obj_type, col=col, row=row)
        if obj_type == ObjType.TREE:
            obj.has_apples  = random.random() < APPLE_TREE_CHANCE
            obj.apple_count = APPLE_MAX_PER_TREE if obj.has_apples else 0
        self._objects.append(obj)
        logger.info(f"Placed {obj_type.name} at ({col},{row})"
                    + (" [apples]" if obj_type == ObjType.TREE and obj.has_apples else ""))
        return True

    def remove(self, col: int, row: int) -> bool:
        for i, obj in enumerate(self._objects):
            if obj.col == col and obj.row == row:
                self._objects.pop(i)
                return True
        return False

    def get_at(self, col: int, row: int) -> Optional[WorldObject]:
        for obj in self._objects:
            if obj.col == col and obj.row == row:
                return obj
        return None

    def get_at_px(self, px: float, py: float) -> Optional[WorldObject]:
        return self.get_at(int(px // GRID_CELL), int(py // GRID_CELL))

    def is_blocked(self, col: int, row: int) -> bool:
        obj = self.get_at(col, row)
        return obj is not None and obj.blocks_path

    def cell_blocked(self, px: float, py: float) -> bool:
        return self.is_blocked(int(px // GRID_CELL), int(py // GRID_CELL))

    # --- Tala ---

    def chop_tree_at(self, px: float, py: float) -> bool:
        """Tala el árbol en (px,py). Devuelve True si se taló."""
        obj = self.get_at_px(px, py)
        if obj is None or obj.type != ObjType.TREE or obj.chopped:
            return False
        if obj.chop():
            self.wood += WOOD_PER_TREE
            logger.info(f"Wood collected: {self.wood} total")
            return True
        return False

    # --- Árboles: zarandear ---

    def shake_tree_at(self, px: float, py: float) -> list[GroundItem]:
        obj = self.get_at_px(px, py)
        if obj is None or obj.type != ObjType.TREE:
            return []
        items = obj.shake()
        self._ground_items.extend(items)
        return items

    # --- Manzanas en el suelo ---

    def nearest_apple(self, cx: float, cy: float) -> Optional[GroundItem]:
        available = [i for i in self._ground_items if not i.rotten]
        if not available:
            return None
        return min(available, key=lambda i: distance((cx, cy), (i.x, i.y)))

    def pick_apple(self, item: GroundItem, needs) -> bool:
        if item not in self._ground_items:
            return False
        needs.feed_amount(APPLE_HUNGER_VALUE)
        self._ground_items.remove(item)
        return True

    def ground_items(self) -> list[GroundItem]:
        return self._ground_items.copy()

    # --- Búsqueda para criaturas ---

    def nearest_for_need(
        self, need: str, cx: float, cy: float, creature_id: str
    ) -> Optional[WorldObject]:
        candidates = [
            o for o in self._objects
            if o.need == need and o.can_use(creature_id) and not getattr(o, 'chopped', False)
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda o: distance((cx, cy), o.pos))

    # --- Update ---

    def update(self, delta: float) -> None:
        for obj in self._objects:
            obj.update(delta)
        # Eliminar tocones expirados
        self._objects = [o for o in self._objects if not o.stump_expired]
        for item in self._ground_items:
            item.update(delta)
        self._ground_items = [i for i in self._ground_items if not i.rotten]

    # --- Persistencia ---

    def to_list(self) -> list[dict]:
        return [o.to_dict() for o in self._objects]

    def from_list(self, data: list[dict]) -> None:
        self._objects = [WorldObject.from_dict(d) for d in data]

    def all_objects(self) -> list[WorldObject]:
        return self._objects.copy()

    @staticmethod
    def _in_bounds(col: int, row: int) -> bool:
        return 0 <= col < _COLS and 0 <= row < _ROWS

    def __len__(self) -> int:
        return len(self._objects)
