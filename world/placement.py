# =============================================================================
# world/placement.py — swarm-alife
# Paleta: objetos para colocar (drag & drop) + herramientas (clic directo).
# =============================================================================

from enum import Enum, auto
from typing import Optional
from world.objects import ObjType, WorldMap
from config import GRID_CELL, WINDOW_WIDTH, WINDOW_HEIGHT, TOOLBAR_HEIGHT

_AREA_W  = WINDOW_WIDTH
_WORLD_H = WINDOW_HEIGHT - TOOLBAR_HEIGHT

# X de inicio de la paleta — calculado igual que en renderer
_BTN_BIG_SIZE    = 58
_BTN_GAP         = 6
_PALETTE_N_ITEMS = 5   # 4 objetos + 1 herramienta (hacha)
_PALETTE_TOTAL_W = _PALETTE_N_ITEMS * (_BTN_BIG_SIZE + _BTN_GAP) - _BTN_GAP + 16
_PANEL_X         = WINDOW_WIDTH - _PALETTE_TOTAL_W - 8

PALETTE: list[ObjType] = [
    ObjType.TREE,
    ObjType.BATH,
    ObjType.BALL,
    ObjType.BED,
]


class ToolMode(Enum):
    NONE = auto()
    AXE  = auto()


def get_chip_rects(palette_x: int, y_start: int) -> list[tuple[int,int,int,int]]:
    """
    Devuelve [(x,y,w,h), ...] para cada chip de la paleta.
    Incluye los chips de objetos + el chip de herramienta (hacha).
    """
    from config import TOOLBAR_HEIGHT
    btn_size = 58
    gap      = 6
    h        = TOOLBAR_HEIGHT - 12
    rects    = []
    x = palette_x + 8
    y = y_start
    # Chips de objetos
    for _ in PALETTE:
        rects.append((x, y, btn_size, h))
        x += btn_size + gap
    # Chip de hacha
    rects.append((x, y, btn_size, h))
    return rects


class PlacementMode:
    """Estado de la paleta: drag & drop para objetos, clic para herramientas."""

    def __init__(self, world: WorldMap):
        self._world = world

        # y_start de la paleta: el renderer lo actualiza cada frame
        self.palette_y_start: int = 200

        # Estado drag (objetos)
        self.dragging:  bool             = False
        self.drag_type: Optional[ObjType]= None
        self.drag_x:    int              = 0
        self.drag_y:    int              = 0

        # Hover de celda
        self.hover_col:   int  = 0
        self.hover_row:   int  = 0
        self.hover_valid: bool = False

        # Herramienta activa
        self.tool: ToolMode = ToolMode.NONE

    # ---------------------------------------------------------------
    # Eventos
    # ---------------------------------------------------------------

    def on_mouse_down(self, mx: int, my: int) -> bool:
        """
        Intenta iniciar drag si el clic cae sobre un chip de objeto,
        o activa/desactiva la herramienta si cae sobre el chip de hacha.
        Devuelve True si se consumió el evento.
        """
        rects = get_chip_rects(_PANEL_X, self.palette_y_start)

        # Chips de objetos (0..len(PALETTE)-1)
        for i, (rx, ry, rw, rh) in enumerate(rects[:len(PALETTE)]):
            if rx <= mx <= rx + rw and ry <= my <= ry + rh:
                self.tool      = ToolMode.NONE   # desactivar hacha al coger objeto
                self.dragging  = True
                self.drag_type = PALETTE[i]
                self.drag_x    = mx
                self.drag_y    = my
                self._update_hover(mx, my)
                return True

        # Chip de hacha
        axe_rect = rects[len(PALETTE)]
        rx, ry, rw, rh = axe_rect
        if rx <= mx <= rx + rw and ry <= my <= ry + rh:
            self.tool = ToolMode.NONE if self.tool == ToolMode.AXE else ToolMode.AXE
            return True

        return False

    def on_mouse_move(self, mx: int, my: int) -> None:
        self.drag_x = mx
        self.drag_y = my
        if self.dragging:
            self._update_hover(mx, my)

    def on_mouse_up(self) -> bool:
        """Suelta el objeto. Devuelve True si se colocó."""
        if not self.dragging:
            return False
        placed = self._world.place(self.drag_type, self.hover_col, self.hover_row) \
            if self.hover_valid and self.drag_type is not None else False
        self._cancel()
        return placed

    def cancel(self) -> None:
        self._cancel()

    def on_right_click(self, mx: int, my: int) -> bool:
        """Borra el objeto en la celda."""
        if mx >= _AREA_W:
            return False
        col = mx // GRID_CELL
        row = my // GRID_CELL
        return self._world.remove(col, row)

    # ---------------------------------------------------------------
    # Estado
    # ---------------------------------------------------------------

    def hover_blocked(self) -> bool:
        return self._world.get_at(self.hover_col, self.hover_row) is not None

    def hover_snap_px(self) -> tuple[int, int]:
        return (
            self.hover_col * GRID_CELL + GRID_CELL // 2,
            self.hover_row * GRID_CELL + GRID_CELL // 2,
        )

    # ---------------------------------------------------------------
    # Interno
    # ---------------------------------------------------------------

    def _update_hover(self, mx: int, my: int) -> None:
        self.hover_valid = mx < _AREA_W and my < _WORLD_H
        if self.hover_valid:
            self.hover_col = max(0, min(mx // GRID_CELL, (_AREA_W // GRID_CELL) - 1))
            self.hover_row = max(0, min(my // GRID_CELL, (_WORLD_H // GRID_CELL) - 1))

    def _cancel(self) -> None:
        self.dragging    = False
        self.drag_type   = None
        self.hover_valid = False
