# =============================================================================
# world/placement.py — swarm-alife
# Drag & drop desde la paleta del panel lateral al mundo.
#
# Flujo:
#   1. MOUSEBUTTONDOWN sobre un chip de la paleta → inicia drag
#   2. MOUSEMOTION → actualiza posición del ghost + celda hover
#   3. MOUSEBUTTONUP sobre el mundo → coloca el objeto
#   4. MOUSEBUTTONUP fuera del mundo (o ESC) → cancela
#
# Clic derecho en mundo → borra objeto
# =============================================================================

from typing import Optional
from world.objects import ObjType, WorldMap
from config import GRID_CELL, WINDOW_WIDTH, WINDOW_HEIGHT, TOOLBAR_HEIGHT

_AREA_W  = WINDOW_WIDTH
_WORLD_H = WINDOW_HEIGHT - TOOLBAR_HEIGHT

# X de inicio de la paleta — calculado igual que en renderer
_BTN_BIG_SIZE = 58
_BTN_GAP      = 6
_PALETTE_TOTAL_W = len([1,2,3,4]) * (_BTN_BIG_SIZE + _BTN_GAP) - _BTN_GAP + 16
_PANEL_X = WINDOW_WIDTH - _PALETTE_TOTAL_W - 8

PALETTE: list[ObjType] = [
    ObjType.TREE,
    ObjType.BATH,
    ObjType.BALL,
    ObjType.BED,
]

# Geometría de los chips en el panel (calculada igual que en renderer)
_CHIP_H   = 32
_CHIP_GAP = 4
_CHIP_Y0  = 0   # se calcula en runtime — ver get_chip_rects()


def get_chip_rects(palette_x: int, y_start: int) -> list[tuple[int,int,int,int]]:
    """
    Devuelve [(x, y, w, h), ...] para cada chip de la paleta.
    Los chips ahora son horizontales en la barra inferior.
    """
    from config import TOOLBAR_HEIGHT
    btn_size = 58
    gap      = 6
    h        = TOOLBAR_HEIGHT - 12
    rects    = []
    x = palette_x + 8
    y = y_start
    for _ in PALETTE:
        rects.append((x, y, btn_size, h))
        x += btn_size + gap
    return rects


class PlacementMode:
    """Estado del drag & drop de objetos."""

    def __init__(self, world: WorldMap):
        self._world = world

        # Chip y_start: el renderer lo actualiza cada frame
        self.palette_y_start: int = 200   # valor inicial conservador

        # Estado drag
        self.dragging:     bool            = False
        self.drag_type:    Optional[ObjType] = None
        self.drag_x:       int             = 0    # posición actual del cursor
        self.drag_y:       int             = 0

        # Hover de celda (solo mientras arrastra sobre el mundo)
        self.hover_col:    int             = 0
        self.hover_row:    int             = 0
        self.hover_valid:  bool            = False   # True = está sobre el mundo

    # ---------------------------------------------------------------
    # Eventos — llamados desde main.py
    # ---------------------------------------------------------------

    def on_mouse_down(self, mx: int, my: int) -> bool:
        """
        Intenta iniciar drag si el clic está sobre un chip de la paleta.
        Devuelve True si se inició drag.
        """
        rects = get_chip_rects(_PANEL_X, self.palette_y_start)
        for i, (rx, ry, rw, rh) in enumerate(rects):
            if rx <= mx <= rx + rw and ry <= my <= ry + rh:
                self.dragging  = True
                self.drag_type = PALETTE[i]
                self.drag_x    = mx
                self.drag_y    = my
                self._update_hover(mx, my)
                return True
        return False

    def on_mouse_move(self, mx: int, my: int) -> None:
        self.drag_x = mx
        self.drag_y = my
        if self.dragging:
            self._update_hover(mx, my)

    def on_mouse_up(self) -> bool:
        """
        Suelta el objeto. Si está sobre el mundo, lo coloca.
        Devuelve True si se colocó.
        """
        if not self.dragging:
            return False
        placed = self._world.place(self.drag_type, self.hover_col, self.hover_row) \
            if self.hover_valid and self.drag_type is not None else False
        self._cancel()
        return placed

    def cancel(self) -> None:
        self._cancel()

    def on_right_click(self, mx: int, my: int) -> bool:
        """Borra el objeto en la celda bajo el cursor."""
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
        """Posición en píxeles de la celda hover (centro)."""
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
