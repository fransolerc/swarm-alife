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
    STUMP_DURATION, WOOD_PER_TREE, STORE_SIZE,
    APPLE_MAX_PER_TREE, APPLE_REGROW_TIME, APPLE_ROT_TIME, APPLE_PICK_RANGE,
    APPLE_HUNGER_VALUE, SHAKE_COOLDOWN, APPLE_TREE_CHANCE, APPLE_SHAKE_RANGE,
)
from utils import distance, clamp

logger = logging.getLogger(__name__)

_AREA_W = WINDOW_WIDTH - UI_PANEL_WIDTH
_COLS   = _AREA_W      // GRID_CELL
_ROWS   = WINDOW_HEIGHT // GRID_CELL


class ObjType(Enum):
    TREE  = auto()
    BATH  = auto()
    BALL  = auto()
    BED   = auto()
    STORE = auto()


OBJ_NEED: dict[ObjType, Optional[str]] = {
    ObjType.TREE:  None,
    ObjType.BATH:  "hygiene",
    ObjType.BALL:  "happiness",
    ObjType.BED:   "energy",
    ObjType.STORE: None,
}

OBJ_LABEL: dict[ObjType, str] = {
    ObjType.TREE:  "árbol",
    ObjType.BATH:  "bañera",
    ObjType.BALL:  "pelota",
    ObjType.BED:   "cama",
    ObjType.STORE: "almacén",
}

OBJ_SIZE: dict[ObjType, int] = {
    ObjType.TREE:  1,
    ObjType.BATH:  1,
    ObjType.BALL:  1,
    ObjType.BED:   1,
    ObjType.STORE: STORE_SIZE,   # 2×2
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
    size: int = field(default=1, repr=False)

    _cooldowns:    dict          = field(default_factory=dict,  repr=False)
    # Mutex: solo una criatura puede usar el objeto a la vez
    _occupant:     Optional[str] = field(default=None,          repr=False)

    has_apples:    bool  = field(default=False, repr=False)
    apple_count:   int   = field(default=0,     repr=False)
    _regrow_timer: float = field(default=0.0,   repr=False)
    _shake_cd:     float = field(default=0.0,   repr=False)
    shake_t:       float = field(default=0.0,   repr=False)

    chopped:     bool  = field(default=False, repr=False)
    stump_timer: float = field(default=0.0,  repr=False)

    stored_apples: int = field(default=0, repr=False)
    stored_wood:   int = field(default=0, repr=False)

    def __post_init__(self):
        if self.size == 1 and self.type in OBJ_SIZE:
            self.size = OBJ_SIZE[self.type]

    # --- Geometría ---

    @property
    def footprint(self) -> list[tuple[int, int]]:
        return [
            (self.col + dc, self.row + dr)
            for dc in range(self.size)
            for dr in range(self.size)
        ]

    @property
    def px(self) -> float:
        return self.col * GRID_CELL + (self.size * GRID_CELL) / 2

    @property
    def py(self) -> float:
        return self.row * GRID_CELL + (self.size * GRID_CELL) / 2

    @property
    def pos(self) -> tuple[float, float]:
        return self.px, self.py

    @property
    def blocks_path(self) -> bool:
        return self.type in (ObjType.TREE, ObjType.STORE)

    @property
    def need(self) -> Optional[str]:
        return OBJ_NEED[self.type]

    def in_range(self, cx: float, cy: float) -> bool:
        """Rango de uso general (bañera, pelota, cama, almacén)."""
        half      = (self.size * GRID_CELL) / 2
        effective = OBJECT_USE_RANGE + half - GRID_CELL / 2
        return distance((cx, cy), self.pos) <= effective

    def in_shake_range(self, cx: float, cy: float) -> bool:
        """Rango específico para sacudir árboles."""
        return distance((cx, cy), self.pos) <= APPLE_SHAKE_RANGE

    # --- Mutex de uso ---

    def can_use(self, creature_id: str) -> bool:
        """
        Devuelve True si la criatura puede usar el objeto.
        Requiere cooldown expirado Y que no haya otra criatura ocupando el objeto.
        """
        if self._cooldowns.get(creature_id, 0) > 0:
            return False
        if self._occupant is not None and self._occupant != creature_id:
            return False
        return True

    def use(self, creature_id: str, needs) -> bool:
        """Aplica el efecto del objeto y marca la criatura como ocupante."""
        if not self.can_use(creature_id):
            return False
        if self.type in (ObjType.TREE, ObjType.STORE):
            return False
        if self.type == ObjType.BATH:
            needs.shower_amount(BATH_HYGIENE_RESTORE)
        elif self.type == ObjType.BALL:
            needs.play_amount(BALL_HAPPINESS_BONUS, BALL_ENERGY_COST)
        elif self.type == ObjType.BED:
            needs.sleep_amount(BED_ENERGY_RESTORE)
        self._cooldowns[creature_id] = OBJECT_USE_COOLDOWN
        self._occupant = creature_id
        return True

    def release(self, creature_id: str) -> None:
        """Libera el objeto cuando la criatura termina o abandona el uso."""
        if self._occupant == creature_id:
            self._occupant = None
            logger.debug(f"{self.type.name} ({self.col},{self.row}): released by {creature_id}")

    # --- Almacén ---

    def deposit_apple(self, count: int = 1) -> None:
        self.stored_apples += count
        logger.debug(f"Store ({self.col},{self.row}): +{count} apple(s) → {self.stored_apples}")

    def deposit_wood(self, count: int = 1) -> None:
        self.stored_wood += count
        logger.debug(f"Store ({self.col},{self.row}): +{count} wood → {self.stored_wood}")

    def take_apple(self) -> bool:
        if self.type == ObjType.STORE and self.stored_apples > 0:
            self.stored_apples -= 1
            return True
        return False

    # --- Árbol: zarandear ---

    def can_shake(self) -> bool:
        return (
                self.type == ObjType.TREE
                and self.has_apples
                and self.apple_count > 0 >= self._shake_cd
                and not self.chopped
        )

    def shake(self) -> list[GroundItem]:
        """Sacudida: cae exactamente 1 manzana. Repetir para vaciar el árbol."""
        self.shake_t = 0.4
        if not self.can_shake():
            return []
        self.apple_count -= 1
        self._shake_cd = SHAKE_COOLDOWN
        angle = random.uniform(0, 2 * math.pi)
        dist  = random.uniform(GRID_CELL * 0.6, GRID_CELL * 1.2)
        ix    = clamp(self.px + math.cos(angle) * dist, 8, _AREA_W - 8)
        iy    = clamp(self.py + math.sin(angle) * dist, 8, WINDOW_HEIGHT - 8)
        logger.info(f"Tree ({self.col},{self.row}) shaken: 1 apple dropped "
                    f"({self.apple_count} remaining)")
        return [GroundItem(x=ix, y=iy)]

    def consume_apple(self) -> bool:
        """Consume una manzana directamente del árbol (sin aparecer en el suelo)."""
        self.shake_t = 0.4
        if not self.can_shake():
            return False
        self.apple_count -= 1
        self._shake_cd = SHAKE_COOLDOWN
        logger.info(f"Tree ({self.col},{self.row}) harvested: 1 apple consumed directly "
                    f"({self.apple_count} remaining)")
        return True

    # --- Árbol: talar ---

    def chop(self) -> bool:
        if self.type != ObjType.TREE or self.chopped:
            return False
        self.chopped     = True
        self.stump_timer = 0.0
        self.has_apples  = False
        self.apple_count = 0
        logger.info(f"Tree ({self.col},{self.row}) chopped")
        return True

    def update(self, delta: float) -> None:
        for cid in self._cooldowns:
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
        if self.type == ObjType.STORE:
            d["stored_apples"] = self.stored_apples
            d["stored_wood"]   = self.stored_wood
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "WorldObject":
        obj_type = ObjType[d["type"]]
        obj = cls(
            type=obj_type,
            col=d["col"],
            row=d["row"],
            size=OBJ_SIZE.get(obj_type, 1),
        )
        if obj.type == ObjType.TREE:
            if "has_apples" in d:
                obj.has_apples  = d["has_apples"]
                obj.apple_count = d.get("apple_count", 0)
            else:
                obj.has_apples  = random.random() < APPLE_TREE_CHANCE
                obj.apple_count = APPLE_MAX_PER_TREE if obj.has_apples else 0
            obj.chopped = d.get("chopped", False)
        if obj.type == ObjType.STORE:
            obj.stored_apples = d.get("stored_apples", 0)
            obj.stored_wood   = d.get("stored_wood", 0)
        return obj


# =============================================================================
# WorldMap
# =============================================================================

class WorldMap:
    def __init__(self):
        self._objects:      list[WorldObject] = []
        self._ground_items: list[GroundItem]  = []
        self.wood: int = 0

    # --- Consulta de celdas ---

    def get_at(self, col: int, row: int) -> Optional[WorldObject]:
        for obj in self._objects:
            if obj.col == col and obj.row == row:
                return obj
        return None

    def get_at_any_cell(self, col: int, row: int) -> Optional[WorldObject]:
        for obj in self._objects:
            for oc, or_ in obj.footprint:
                if oc == col and or_ == row:
                    return obj
        return None

    def get_at_px(self, px: float, py: float) -> Optional[WorldObject]:
        return self.get_at_any_cell(int(px // GRID_CELL), int(py // GRID_CELL))

    def is_blocked(self, col: int, row: int) -> bool:
        for obj in self._objects:
            if obj.blocks_path:
                for oc, or_ in obj.footprint:
                    if oc == col and or_ == row:
                        return True
        return False

    def cell_blocked(self, px: float, py: float) -> bool:
        return self.is_blocked(int(px // GRID_CELL), int(py // GRID_CELL))

    # --- Colocación ---

    def place(self, obj_type: ObjType, col: int, row: int) -> bool:
        size = OBJ_SIZE.get(obj_type, 1)
        for dc in range(size):
            for dr in range(size):
                if not self._in_bounds(col+dc, row+dr):
                    return False
                if self.get_at_any_cell(col+dc, row+dr) is not None:
                    return False
        obj = WorldObject(type=obj_type, col=col, row=row, size=size)
        if obj_type == ObjType.TREE:
            obj.has_apples  = random.random() < APPLE_TREE_CHANCE
            obj.apple_count = APPLE_MAX_PER_TREE if obj.has_apples else 0
        self._objects.append(obj)
        logger.info(f"Placed {obj_type.name} ({size}×{size}) at ({col},{row})"
                    + (" [apples]" if obj_type == ObjType.TREE and obj.has_apples else ""))
        return True

    def remove(self, col: int, row: int) -> bool:
        obj = self.get_at_any_cell(col, row)
        if obj is not None:
            self._objects.remove(obj)
            return True
        return False

    # --- Tala ---

    def chop_tree_at(self, px: float, py: float) -> bool:
        obj = self.get_at_px(px, py)
        if obj is None or obj.type != ObjType.TREE or obj.chopped:
            return False
        if obj.chop():
            self.wood += WOOD_PER_TREE
            logger.info(f"Wood total: {self.wood}")
            return True
        return False

    # --- Árboles: zarandear (solo criaturas) ---

    def shake_tree_at(self, px: float, py: float) -> list[GroundItem]:
        obj = self.get_at_px(px, py)
        if obj is None or obj.type != ObjType.TREE:
            return []
        items = obj.shake()
        self._ground_items.extend(items)
        return items

    def eat_from_tree(self, px: float, py: float, needs) -> bool:
        """Cosecha y consume una manzana directamente para satisfacer el hambre."""
        obj = self.get_at_px(px, py)
        if obj is None or obj.type != ObjType.TREE:
            return False
        if obj.consume_apple():
            needs.feed_amount(APPLE_HUNGER_VALUE)
            return True
        return False

    def harvest_from_tree(self, px: float, py: float) -> bool:
        """Extrae una manzana del árbol (para transportarla)."""
        obj = self.get_at_px(px, py)
        if obj is None or obj.type != ObjType.TREE:
            return False
        return obj.consume_apple()

    def nearest_shakeable_tree(self, cx: float, cy: float) -> Optional[WorldObject]:
        """Árbol más cercano con manzanas disponibles y sin cooldown de sacudida."""
        candidates = [o for o in self._objects if o.type == ObjType.TREE and o.can_shake()]
        if not candidates:
            return None
        return min(candidates, key=lambda o: distance((cx, cy), o.pos))

    def nearest_stump(self, cx: float, cy: float) -> Optional[WorldObject]:
        """Tocón más cercano (árbol talado que aún no ha desaparecido)."""
        stumps = [o for o in self._objects if o.type == ObjType.TREE and o.chopped]
        if not stumps:
            return None
        return min(stumps, key=lambda o: distance((cx, cy), o.pos))

    # --- Manzanas en el suelo ---

    def nearest_apple(self, cx: float, cy: float) -> Optional[GroundItem]:
        available = [i for i in self._ground_items if not i.rotten]
        if not available:
            return None
        return min(available, key=lambda i: distance((cx, cy), (i.x, i.y)))

    def pick_apple(self, item: GroundItem, needs) -> bool:
        """Recoge manzana para comer."""
        if item not in self._ground_items:
            return False
        needs.feed_amount(APPLE_HUNGER_VALUE)
        self._ground_items.remove(item)
        return True

    def pick_apple_to_carry(self, item: GroundItem) -> bool:
        """Recoge manzana para acarrear al almacén (sin beneficio de hambre)."""
        if item not in self._ground_items:
            return False
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
            if o.need == need and o.can_use(creature_id) and not getattr(o, "chopped", False)
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda o: distance((cx, cy), o.pos))

    def nearest_store(self, cx: float, cy: float) -> Optional[WorldObject]:
        stores = [o for o in self._objects if o.type == ObjType.STORE]
        if not stores:
            return None
        return min(stores, key=lambda o: distance((cx, cy), o.pos))

    def nearest_store_with_apples(self, cx: float, cy: float) -> Optional[WorldObject]:
        stores = [o for o in self._objects if o.type == ObjType.STORE and o.stored_apples > 0]
        if not stores:
            return None
        return min(stores, key=lambda o: distance((cx, cy), o.pos))

    # --- Update ---

    def update(self, delta: float) -> None:
        for obj in self._objects:
            obj.update(delta)
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
