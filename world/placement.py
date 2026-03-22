# =============================================================================
# world/placement.py — swarm-alife
# Paleta de objetos siempre visible en el panel lateral.
# Clic izquierdo en mundo = colocar objeto seleccionado (si no hay criatura).
# Clic derecho en mundo  = borrar objeto.
# =============================================================================

from typing import Optional
from world.objects import ObjType, WorldMap
from config import GRID_CELL, WINDOW_WIDTH, WINDOW_HEIGHT, UI_PANEL_WIDTH

_AREA_W = WINDOW_WIDTH - UI_PANEL_WIDTH

PALETTE: list[ObjType] = [
    ObjType.TREE,
    ObjType.BATH,
    ObjType.BALL,
    ObjType.BED,
]


class PlacementMode:
    """
    Estado de la paleta de colocación.
    Siempre activa — no hay modo toggle.
    """

    def __init__(self, world: WorldMap):
        self._world   = world
        self.selected: Optional[ObjType] = None   # None = sin selección (modo inspección)
        self.hover_col = 0
        self.hover_row = 0

    def on_mouse_move(self, mx: int, my: int) -> None:
        if mx >= _AREA_W:
            return
        self.hover_col = max(0, min(mx // GRID_CELL, (_AREA_W // GRID_CELL) - 1))
        self.hover_row = max(0, min(my // GRID_CELL, (WINDOW_HEIGHT // GRID_CELL) - 1))

    def on_left_click(self, mx: int, my: int) -> bool:
        """Coloca el objeto seleccionado. Devuelve True si se colocó."""
        if self.selected is None or mx >= _AREA_W:
            return False
        col = mx // GRID_CELL
        row = my // GRID_CELL
        return self._world.place(self.selected, col, row)

    def on_right_click(self, mx: int, my: int) -> bool:
        """Borra el objeto en la celda. Devuelve True si se borró."""
        if mx >= _AREA_W:
            return False
        col = mx // GRID_CELL
        row = my // GRID_CELL
        return self._world.remove(col, row)

    def select_type(self, obj_type: ObjType) -> None:
        """Selecciona un tipo. Si ya estaba seleccionado, deselection."""
        if self.selected == obj_type:
            self.selected = None
        else:
            self.selected = obj_type

    def select_by_index(self, idx: int) -> None:
        if 0 <= idx < len(PALETTE):
            t = PALETTE[idx]
            self.select_type(t)

    def hover_blocked(self) -> bool:
        return self._world.get_at(self.hover_col, self.hover_row) is not None
