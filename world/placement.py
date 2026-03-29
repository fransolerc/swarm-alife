# =============================================================================
# world/placement.py — swarm-alife
# =============================================================================

from enum import Enum, auto
from typing import Optional
from world.objects import ObjType, OBJ_SIZE, WorldMap
from config import GRID_CELL, WINDOW_WIDTH, WINDOW_HEIGHT, TOOLBAR_HEIGHT

_AREA_W  = WINDOW_WIDTH
_WORLD_H = WINDOW_HEIGHT - TOOLBAR_HEIGHT

PALETTE: list[ObjType] = [
    ObjType.TREE,
    ObjType.BATH,
    ObjType.BALL,
    ObjType.BED,
    ObjType.STORE,
]


class ToolMode(Enum):
    NONE = auto()
    AXE  = auto()


class PlacementMode:
    """Estado de la paleta: drag & drop para objetos, clic para herramientas."""

    def __init__(self, world: WorldMap):
        self._world = world

        # Geometría de la paleta — el renderer los escribe cada frame
        # Los defaults son seguros aunque el renderer no haya corrido aún
        self.palette_x:     int = WINDOW_WIDTH - 400
        self.palette_y_start: int = WINDOW_HEIGHT - TOOLBAR_HEIGHT + 6
        self.btn_size:      int = 52
        self.btn_gap:       int = 5

        # Estado drag (objetos)
        self.dragging:  bool              = False
        self.drag_type: Optional[ObjType] = None
        self.drag_x:    int               = 0
        self.drag_y:    int               = 0

        # Hover de celda
        self.hover_col:   int  = 0
        self.hover_row:   int  = 0
        self.hover_valid: bool = False

        # Herramienta activa
        self.tool: ToolMode = ToolMode.NONE

    # ---------------------------------------------------------------
    # Geometría — calculada a partir de los valores que escribe el renderer
    # ---------------------------------------------------------------

    def _chip_rects(self) -> list[tuple[int,int,int,int]]:
        """
        Devuelve [(x, y, w, h), ...] para cada chip de la paleta.
        Orden: objetos de PALETTE seguidos del chip de hacha.
        """
        rects = []
        x = self.palette_x + 6
        y = self.palette_y_start
        h = TOOLBAR_HEIGHT - 12
        for _ in PALETTE:
            rects.append((x, y, self.btn_size, h))
            x += self.btn_size + self.btn_gap
        # Chip de hacha
        rects.append((x, y, self.btn_size, h))
        return rects

    # ---------------------------------------------------------------
    # Eventos
    # ---------------------------------------------------------------

    def on_mouse_down(self, mx: int, my: int) -> bool:
        rects = self._chip_rects()

        # Chips de objetos
        for i, (rx, ry, rw, rh) in enumerate(rects[:len(PALETTE)]):
            if rx <= mx <= rx+rw and ry <= my <= ry+rh:
                self.tool      = ToolMode.NONE
                self.dragging  = True
                self.drag_type = PALETTE[i]
                self.drag_x    = mx
                self.drag_y    = my
                self._update_hover(mx, my)
                return True

        # Chip de hacha
        rx, ry, rw, rh = rects[len(PALETTE)]
        if rx <= mx <= rx+rw and ry <= my <= ry+rh:
            self.tool = ToolMode.NONE if self.tool == ToolMode.AXE else ToolMode.AXE
            return True

        return False

    def on_mouse_move(self, mx: int, my: int) -> None:
        self.drag_x = mx
        self.drag_y = my
        if self.dragging:
            self._update_hover(mx, my)

    def on_mouse_up(self) -> bool:
        if not self.dragging:
            return False
        placed = (
            self._world.place(self.drag_type, self.hover_col, self.hover_row)
            if self.hover_valid and self.drag_type is not None
            else False
        )
        self._cancel()
        return placed

    def cancel(self) -> None:
        self._cancel()

    def on_right_click(self, mx: int, my: int) -> bool:
        if mx >= _AREA_W:
            return False
        col = mx // GRID_CELL
        row = my // GRID_CELL
        return self._world.remove(col, row)

    # ---------------------------------------------------------------
    # Estado
    # ---------------------------------------------------------------

    def drag_size(self) -> int:
        if self.drag_type is None:
            return 1
        return OBJ_SIZE.get(self.drag_type, 1)

    def hover_blocked(self) -> bool:
        size = self.drag_size()
        for dc in range(size):
            for dr in range(size):
                if self._world.get_at_any_cell(self.hover_col+dc, self.hover_row+dr) is not None:
                    return True
        return False

    def hover_snap_px(self) -> tuple[int,int]:
        return (
            self.hover_col * GRID_CELL + GRID_CELL // 2,
            self.hover_row * GRID_CELL + GRID_CELL // 2,
        )

    # ---------------------------------------------------------------
    # Interno
    # ---------------------------------------------------------------

    def _update_hover(self, mx: int, my: int) -> None:
        self.hover_valid = mx < _AREA_W and my < _WORLD_H
        if not self.hover_valid:
            return
        col = max(0, min(mx // GRID_CELL, (_AREA_W // GRID_CELL) - 1))
        row = max(0, min(my // GRID_CELL, (_WORLD_H // GRID_CELL) - 1))
        # Para objetos multi-celda: centrar el footprint en el cursor
        size = self.drag_size()
        if size > 1:
            half = size // 2
            col = max(0, col - half + 1)
            row = max(0, row - half + 1)
        self.hover_col = col
        self.hover_row = row

    def _cancel(self) -> None:
        self.dragging    = False
        self.drag_type   = None
        self.hover_valid = False
