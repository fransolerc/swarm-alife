# =============================================================================
# render/renderer.py — swarm-alife
# =============================================================================

import pygame
import math
import random
import logging
from typing import List

from config import (
    WINDOW_WIDTH, WINDOW_HEIGHT, TOOLBAR_HEIGHT,
    CREATURE_RADIUS, COLOR_HUNGER_BAR, COLOR_HYGIENE_BAR,
    COLOR_HAPPINESS_BAR,
    COLOR_MESSAGE_BG, COLOR_MESSAGE_TEXT,
    NEED_MAX, GRID_CELL,
    PLACEMENT_HOVER_COLOR, PLACEMENT_BLOCKED_COLOR,
    TOOLBAR_WOOD_DARK, TOOLBAR_WOOD_MID, TOOLBAR_WOOD_LIGHT, TOOLBAR_WOOD_EDGE,
    TOOLBAR_BTN_DARK, TOOLBAR_BTN_SEL, TOOLBAR_BTN_SEL_EDGE, TOOLBAR_TEXT,
)
from world.objects import ObjType, OBJ_LABEL, WorldObject

logger = logging.getLogger(__name__)

_WORLD_H   = WINDOW_HEIGHT - TOOLBAR_HEIGHT
_TOOLBAR_Y = _WORLD_H

C_GRASS_DARK = (38, 58, 28)
C_GRASS_MID  = (44, 62, 30)
C_GRASS_LIT  = (52, 74, 34)

_STATE_COLORS = {
    "normal":   ((120, 196, 138), (90,  170, 110), (88,  160, 102), (248, 164, 180)),
    "hungry":   ((196, 168,  80), (170, 142,  60), (160, 132,  50), (248, 196, 160)),
    "sad":      ((104, 136, 192), ( 74, 106, 170), ( 74, 106, 170), (160, 180, 232)),
    "tired":    ((136, 136, 152), (110, 110, 122), (106, 106, 118), (176, 176, 192)),
    "critical": ((208,  80,  64), (176,  56,  44), (176,  48,  36), (240, 160, 128)),
}
C_SEL_RING = (255, 220,  50)
C_PULSE    = (232, 112,  96)

_INFO_W = 220
_INFO_X = 8

_BTN_SIZE = 52
_BTN_GAP  = 5

_POP_CX = 42
_POP_CY = 42

# Almacén
C_STORE_WALL  = (180, 140, 80)
C_STORE_ROOF  = (140,  60, 40)
C_STORE_DOOR  = ( 90,  55, 25)
C_STORE_PLANK = (160, 120, 65)
C_STORE_STONE = (130, 115, 95)

# Yacimiento / mina
C_GEM_DARK   = (120,  50, 200)
C_GEM_MID    = (165,  80, 240)
C_GEM_LIGHT  = (210, 150, 255)
C_MINE_WOOD  = (107,  66,  38)
C_MINE_DARK  = ( 80,  48,  20)
C_MINE_ROOF  = ( 90,  55,  28)

# Overlay diario
C_DIARY_BG     = (18,  12,  32, 220)
C_DIARY_BORDER = (160, 120, 220, 200)
C_DIARY_HEAD   = (220, 190, 255)
C_DIARY_META   = (170, 140, 210)
C_DIARY_TEXT   = (230, 220, 248)
C_DIARY_GEM    = (190, 130, 255)
C_DIARY_LINE   = (80,  55, 120, 160)


def _el(surf, color, cx, cy, rx, ry, w=0):
    pygame.draw.ellipse(surf, color,
                        (int(cx-rx), int(cy-ry), max(1,int(rx*2)), max(1,int(ry*2))), w)

def _ci(surf, color, cx, cy, r, w=0):
    pygame.draw.circle(surf, color, (int(cx), int(cy)), max(1, int(r)), w)

def _rnd_rect(surf, color, x, y, w, h, r, width=0):
    pygame.draw.rect(surf, color, (int(x), int(y), int(w), int(h)),
                     width, border_radius=r)


class Renderer:
    def __init__(self, screen: pygame.Surface):
        self.screen   = screen
        self._pulse_t = 0.0
        self._init_fonts()
        self._grass = self._build_grass()
        logger.info("Renderer initialized")

    def _init_fonts(self):
        self.font_tiny   = pygame.font.SysFont("monospace", 10)
        self.font_small  = pygame.font.SysFont("monospace", 11)
        self.font_medium = pygame.font.SysFont("monospace", 13)
        self.font_large  = pygame.font.SysFont("monospace", 15, bold=True)
        self.font_msg    = pygame.font.SysFont("monospace", 12)

    @staticmethod
    def _build_grass() -> pygame.Surface:
        surf = pygame.Surface((WINDOW_WIDTH, _WORLD_H))
        surf.fill(C_GRASS_DARK)
        rng = random.Random(42)
        for row in range(_WORLD_H // GRID_CELL + 1):
            for col in range(WINDOW_WIDTH // GRID_CELL + 1):
                if (row + col) % 2 == 0:
                    pygame.draw.rect(surf, C_GRASS_MID,
                                     (col*GRID_CELL, row*GRID_CELL, GRID_CELL, GRID_CELL))
        for _ in range(320):
            gx = rng.randint(4, WINDOW_WIDTH - 4)
            gy = rng.randint(4, _WORLD_H - 4)
            h  = rng.randint(5, 13)
            pygame.draw.line(surf, C_GRASS_LIT, (gx, gy), (gx, gy-h), 1)
            if rng.random() > 0.5:
                pygame.draw.line(surf, C_GRASS_LIT, (gx+2, gy), (gx+3, gy-h+3), 1)
        return surf

    # ---------------------------------------------------------------
    # Frame principal
    # ---------------------------------------------------------------

    def draw_frame(
        self, creatures, selected, clock_obj, world, placement,
        delta=0.016, show_diary=False, diary_entries=None,
    ):
        self._pulse_t += delta

        self.screen.blit(self._grass, (0, 0))
        if placement.dragging and placement.hover_valid:
            self._draw_cell_hover(placement)
        self._draw_deposits(world)
        self._draw_objects(world)
        self._draw_ground_items(world)
        self._draw_creatures(creatures)
        self._draw_toolbar(selected, clock_obj, placement, world.wood)
        self._draw_population_badge(len(creatures))

        if show_diary:
            self._draw_diary_overlay(diary_entries or [])

        pygame.display.flip()

    # ---------------------------------------------------------------
    # Hover multi-celda
    # ---------------------------------------------------------------

    def _draw_cell_hover(self, placement):
        size    = placement.drag_size()
        blocked = placement.hover_blocked()
        color   = PLACEMENT_BLOCKED_COLOR if blocked else PLACEMENT_HOVER_COLOR
        for dc in range(size):
            for dr in range(size):
                hx = (placement.hover_col + dc) * GRID_CELL
                hy = (placement.hover_row + dr) * GRID_CELL
                if hy + GRID_CELL > _WORLD_H:
                    continue
                cell = pygame.Surface((GRID_CELL, GRID_CELL), pygame.SRCALPHA)
                pygame.draw.rect(cell, (*color, 45),  (0, 0, GRID_CELL, GRID_CELL))
                pygame.draw.rect(cell, (*color, 160), (0, 0, GRID_CELL, GRID_CELL), 1)
                self.screen.blit(cell, (hx, hy))

    # ---------------------------------------------------------------
    # Yacimientos de gemas (no son WorldObjects, se dibujan aparte)
    # ---------------------------------------------------------------

    def _draw_deposits(self, world):
        for col, row in world.deposits():
            cx = col * GRID_CELL + GRID_CELL // 2
            cy = row * GRID_CELL + GRID_CELL // 2
            self._draw_gem_deposit(cx, cy)

    def _draw_gem_deposit(self, cx, cy):
        # sombra
        s = pygame.Surface((34, 10), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (0, 0, 0, 45), (0, 0, 34, 10))
        self.screen.blit(s, (cx-17, cy+8))

        # Cristal central (grande)
        pts = [(cx, cy-16), (cx+8, cy-5), (cx+6, cy+7), (cx-6, cy+7), (cx-8, cy-5)]
        pygame.draw.polygon(self.screen, C_GEM_DARK, pts)
        pygame.draw.polygon(self.screen, C_GEM_MID, pts, 1)
        # Faceta de luz
        pygame.draw.line(self.screen, C_GEM_LIGHT, (cx, cy-16), (cx+4, cy-4), 1)
        pygame.draw.line(self.screen, C_GEM_LIGHT, (cx-4, cy-8), (cx, cy-16), 1)

        # Cristal derecho (pequeño)
        pts2 = [(cx+9, cy-8), (cx+15, cy-1), (cx+12, cy+6), (cx+6, cy-1)]
        pygame.draw.polygon(self.screen, C_GEM_DARK, pts2)
        pygame.draw.polygon(self.screen, C_GEM_MID, pts2, 1)
        pygame.draw.line(self.screen, C_GEM_LIGHT, (cx+9, cy-8), (cx+12, cy-2), 1)

        # Cristal izquierdo (pequeño)
        pts3 = [(cx-9, cy-7), (cx-14, cy+1), (cx-11, cy+6), (cx-5, cy+1)]
        pygame.draw.polygon(self.screen, C_GEM_DARK, pts3)
        pygame.draw.polygon(self.screen, C_GEM_MID, pts3, 1)
        pygame.draw.line(self.screen, C_GEM_LIGHT, (cx-9, cy-7), (cx-12, cy-1), 1)

        # Destello superior
        _ci(self.screen, C_GEM_LIGHT, cx, cy-16, 2)

    # ---------------------------------------------------------------
    # Objetos del mundo
    # ---------------------------------------------------------------

    def _draw_objects(self, world):
        for obj in world.all_objects():
            cx = int(obj.px)
            cy = int(obj.py)
            if obj.type == ObjType.TREE and obj.shake_t > 0:
                cx += int(math.sin(obj.shake_t * 40) * 3 * (obj.shake_t / 0.4))
            self._draw_object(obj, cx, cy)

    def _draw_object(self, obj: WorldObject, cx: int, cy: int):
        if obj.type == ObjType.TREE:
            if obj.chopped:
                self._draw_stump(cx, cy)
            else:
                self._draw_tree(cx, cy, obj.apple_count if obj.has_apples else -1)
        elif obj.type == ObjType.BATH:  self._draw_bath(cx, cy)
        elif obj.type == ObjType.BALL:  self._draw_ball(cx, cy)
        elif obj.type == ObjType.STORE: self._draw_store(obj, cx, cy)
        elif obj.type == ObjType.MINE:  self._draw_mine(cx, cy)

    def _draw_tree(self, cx, cy, apple_count=0):
        s = pygame.Surface((44, 12), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (0,0,0,50), (0,0,44,12))
        self.screen.blit(s, (cx-22, cy+10))
        pygame.draw.rect(self.screen, (107,66,38), (cx-5,cy-2,10,16), border_radius=3)
        pygame.draw.rect(self.screen, (125,80,48), (cx-3,cy,4,12))
        _el(self.screen, (45,110,40),  cx, cy-16, 22, 20)
        _el(self.screen, (58,138,52),  cx-4, cy-20, 14, 13)
        _el(self.screen, (42,98,36),   cx+4, cy-14, 10, 9)
        _el(self.screen, (74,168,66),  cx-6, cy-24, 6, 5)
        if apple_count > 0:
            for ax, ay in [(-8,-22),(6,-18),(-2,-28)][:apple_count]:
                _ci(self.screen, (200,50,40), cx+ax, cy+ay, 4)
                _ci(self.screen, (230,80,60), cx+ax-1, cy+ay-1, 2)
                pygame.draw.line(self.screen, (80,120,40),
                                 (cx+ax, cy+ay-4), (cx+ax+2, cy+ay-7), 1)

    def _draw_stump(self, cx, cy):
        s = pygame.Surface((28, 8), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (0,0,0,40), (0,0,28,8))
        self.screen.blit(s, (cx-14, cy+8))
        pygame.draw.rect(self.screen, (90, 55, 28), (cx-8, cy-2, 16, 12), border_radius=3)
        _el(self.screen, (110, 72, 38), cx, cy-2, 8, 5)
        _el(self.screen, (125, 85, 48), cx, cy-2, 5, 3)
        _el(self.screen, (140, 100, 58), cx, cy-2, 2, 1)
        pygame.draw.line(self.screen, (80, 50, 24), (cx-8, cy+8), (cx-13, cy+13), 2)
        pygame.draw.line(self.screen, (80, 50, 24), (cx+8, cy+8), (cx+13, cy+13), 2)

    def _draw_bath(self, cx, cy):
        s = pygame.Surface((40,10), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (0,0,0,50), (0,0,40,10))
        self.screen.blit(s, (cx-20,cy+12))
        pygame.draw.rect(self.screen,(208,232,240),(cx-16,cy-10,32,24),border_radius=6)
        pygame.draw.rect(self.screen,(168,204,224),(cx-14,cy-8,28,20),border_radius=4)
        pygame.draw.rect(self.screen,(90,180,212),(cx-13,cy-2,26,12),border_radius=3)
        for bx,by,br in [(-5,2,2.5),(3,1,2),(9,3,1.5),(-1,5,1.5)]:
            _ci(self.screen,(144,212,240),cx+bx,cy+by,br)
        for px_ in [-12,12]:
            pygame.draw.rect(self.screen,(176,200,216),(cx+px_-2,cy+13,4,6),border_radius=1)
        pygame.draw.rect(self.screen,(192,200,208),(cx-4,cy-16,8,6),border_radius=2)
        _ci(self.screen,(216,224,232),cx,cy-16,3)

    def _draw_ball(self, cx, cy):
        s = pygame.Surface((36,10), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (0,0,0,50), (0,0,36,10))
        self.screen.blit(s, (cx-18,cy+12))
        _ci(self.screen,(224,64,48),cx,cy,18)
        pygame.draw.arc(self.screen,(255,255,255),(cx-18,cy-10,36,20),0,math.pi,2)
        pygame.draw.arc(self.screen,(255,255,255),(cx-18,cy-10,36,20),math.pi,2*math.pi,2)
        _el(self.screen,(255,255,255),cx-7,cy-10,6,4)

    def _draw_store(self, obj: WorldObject, cx: int, cy: int):
        half = int(obj.size * GRID_CELL / 2)
        left = cx - half
        top  = cy - half
        _rnd_rect(self.screen, C_STORE_STONE, left+3, top+half+6, half*2-6, half-10, 4)
        _rnd_rect(self.screen, C_STORE_WALL, left+5, top+20, half*2-10, half, 3)
        for dy in range(0, half-4, 10):
            pygame.draw.rect(self.screen, C_STORE_PLANK,
                             (left+5, top+20+dy, half*2-10, 3), border_radius=1)
        roof_pts = [(left, top+24), (cx, top+4), (left+half*2, top+24)]
        pygame.draw.polygon(self.screen, C_STORE_ROOF, roof_pts)
        pygame.draw.polygon(self.screen, (160, 80, 55), roof_pts, 2)
        pygame.draw.line(self.screen, (120,50,30), (left, top+24), (left+half*2, top+24), 3)
        dw, dh = 18, 24
        dx = cx - dw//2
        dy = cy + half - dh - 6
        _rnd_rect(self.screen, C_STORE_DOOR, dx, dy, dw, dh, 2)
        _rnd_rect(self.screen, (70,42,18), dx, dy, dw, dh, 2, 1)
        _ci(self.screen, (200,170,80), dx+dw-5, dy+dh//2, 2)
        self._draw_store_hud(obj, left, top)

    def _draw_store_hud(self, obj: WorldObject, left: int, top: int):
        """Muestra contadores de manzanas, madera y gemas sobre el almacén."""
        hud_y = top - 16
        x = left + 4

        # Manzanas
        _ci(self.screen, (200,50,40), x+5, hud_y, 5)
        apple_s = self.font_small.render(str(obj.stored_apples), True, (255,220,200))
        self.screen.blit(apple_s, (x+13, hud_y-5))
        x += 28

        # Madera
        pygame.draw.rect(self.screen, (139,94,60), (x, hud_y-5, 10, 10), border_radius=2)
        wood_s = self.font_small.render(str(obj.stored_wood), True, (240,210,160))
        self.screen.blit(wood_s, (x+13, hud_y-5))
        x += 28

        # Gemas
        gem_pts = [
            (x+5, hud_y-7), (x+10, hud_y-2), (x+8, hud_y+4),
            (x+2, hud_y+4), (x,    hud_y-2),
        ]
        pygame.draw.polygon(self.screen, C_GEM_DARK, gem_pts)
        pygame.draw.polygon(self.screen, C_GEM_LIGHT, gem_pts, 1)
        gem_s = self.font_small.render(str(obj.stored_gems), True, C_GEM_LIGHT)
        self.screen.blit(gem_s, (x+13, hud_y-5))

    def _draw_mine(self, cx, cy):
        """Mina de gemas: estructura de madera sobre un yacimiento."""
        # sombra
        s = pygame.Surface((44, 12), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (0, 0, 0, 45), (0, 0, 44, 12))
        self.screen.blit(s, (cx-22, cy+10))

        # Patas
        for px_ in [-12, 12]:
            pygame.draw.rect(self.screen, C_MINE_WOOD, (cx+px_-3, cy+4, 6, 14), border_radius=1)

        # Cuerpo
        _rnd_rect(self.screen, C_MINE_WOOD, cx-16, cy-6, 32, 18, 3)
        _rnd_rect(self.screen, C_MINE_DARK, cx-16, cy-6, 32, 18, 3, 1)

        # Tejado triangular
        roof_pts = [(cx-20, cy-4), (cx, cy-18), (cx+20, cy-4)]
        pygame.draw.polygon(self.screen, C_MINE_ROOF, roof_pts)
        pygame.draw.polygon(self.screen, C_MINE_DARK, roof_pts, 1)

        # Entrada oscura
        _rnd_rect(self.screen, (30, 18, 8), cx-7, cy-2, 14, 14, 2)

        # Pico cruzado
        pygame.draw.line(self.screen, (160, 170, 180), (cx-10, cy+8), (cx+6, cy-4), 2)
        pts_axe = [(cx+4, cy-8), (cx+14, cy-4), (cx+10, cy+3), (cx, cy+1)]
        pygame.draw.polygon(self.screen, (180, 190, 200), pts_axe)
        pygame.draw.polygon(self.screen, (140, 148, 158), pts_axe, 1)

        # Gema brillando en el techo
        _ci(self.screen, C_GEM_DARK, cx-2, cy-20, 4)
        _ci(self.screen, C_GEM_MID,  cx-2, cy-20, 3)
        _ci(self.screen, C_GEM_LIGHT, cx-2, cy-20, 1)

    # ---------------------------------------------------------------
    # Manzanas en el suelo
    # ---------------------------------------------------------------

    def _draw_ground_items(self, world):
        from world.objects import APPLE_ROT_TIME
        for item in world.ground_items():
            cx, cy = int(item.x), int(item.y)
            fade  = max(0.2, 1.0 - item.age / APPLE_ROT_TIME * 0.7)
            red   = int(180 * fade)
            green = int(40  * fade)
            sh = pygame.Surface((14,6), pygame.SRCALPHA)
            pygame.draw.ellipse(sh, (0,0,0,40), (0,0,14,6))
            self.screen.blit(sh, (cx-7, cy+3))
            _ci(self.screen, (red, green, 30), cx, cy, 5)
            _ci(self.screen, (min(255,red+40), green+20, 40), cx-1, cy-1, 2)
            pygame.draw.line(self.screen, (80,120,40), (cx,cy-5),(cx+2,cy-8),1)

    # ---------------------------------------------------------------
    # Criaturas
    # ---------------------------------------------------------------

    def _draw_creatures(self, creatures):
        for c in creatures: self._draw_shadow(c)
        for c in creatures: self._draw_creature(c)
        for c in creatures:
            if c.current_message:
                self._draw_bubble(c, c.current_message)

    def _draw_shadow(self, c):
        if c.y + CREATURE_RADIUS > _WORLD_H:
            return
        s = pygame.Surface((40,12), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (0,0,0,55), (0,0,40,12))
        self.screen.blit(s, (int(c.x)-20, int(c.y)+CREATURE_RADIUS-4))

    @staticmethod
    def _state(c) -> str:
        n = c.needs
        if n.is_critical():    return "critical"
        if n.hunger    >= 75:  return "hungry"
        if n.happiness <= 30:  return "sad"
        return "normal"

    def _draw_creature(self, c):
        cx, cy = int(c.x), int(c.y)
        if cy > _WORLD_H + CREATURE_RADIUS:
            return
        state  = self._state(c)
        body_c, ear_c, leg_c, cheek_c = _STATE_COLORS[state]
        r = CREATURE_RADIUS

        is_walking = c.speed_real > 8.0
        if is_walking:
            freq, bob_amp, lean_amp = 8.0, 2.5, 2.0
            bob_y     = int(math.sin(c.anim_t * freq) * bob_amp)
            lean_x    = int(math.sin(c.anim_t * freq * 0.5) * lean_amp)
            stretch_y = 1.0 + math.sin(c.anim_t * freq) * 0.06
            stretch_x = 1.0 - math.sin(c.anim_t * freq) * 0.04
        else:
            bob_y = int(math.sin(c.anim_t * 1.8) * 1.2)
            lean_x, stretch_y, stretch_x = 0, 1.0 + math.sin(c.anim_t*1.8)*0.03, 1.0

        acy = cy + bob_y
        acx = cx + lean_x

        if c.selected:
            _ci(self.screen, C_SEL_RING, cx, cy, r+5, 2)
        if state == "critical":
            pulse = abs(math.sin(self._pulse_t * 3.5))
            ps = pygame.Surface((80,80), pygame.SRCALPHA)
            _ci(ps, (*C_PULSE, int(160*pulse)), 40, 40, r+4+int(pulse*6), 2)
            self.screen.blit(ps, (cx-40,cy-40))

        if c.target_obj is not None and not c.using_obj:
            ts = pygame.Surface((WINDOW_WIDTH, _WORLD_H), pygame.SRCALPHA)
            pygame.draw.line(ts, (200,200,100,35),
                             (cx,cy), (int(c.target_obj.px),int(c.target_obj.py)), 1)
            self.screen.blit(ts, (0,0))

        if c.shake_target is not None:
            ts = pygame.Surface((WINDOW_WIDTH, _WORLD_H), pygame.SRCALPHA)
            pygame.draw.line(ts, (200,140,60,40),
                             (cx,cy), (int(c.shake_target.px),int(c.shake_target.py)), 1)
            self.screen.blit(ts, (0,0))

        _el(self.screen, ear_c,   acx-10, acy-r-2, 5, 7)
        _el(self.screen, ear_c,   acx+10, acy-r-2, 5, 7)
        _el(self.screen, cheek_c, acx-10, acy-r-3, 3, 4)
        _el(self.screen, cheek_c, acx+10, acy-r-3, 3, 4)
        _el(self.screen, body_c, acx, acy,
            max(1,int(r*stretch_x)), max(1,int(r*0.88*stretch_y)))
        if is_walking:
            off = int(math.sin(c.anim_t * 8.0) * 3)
            _el(self.screen, leg_c, acx-10, acy+r-3 - off, 5, 4)
            _el(self.screen, leg_c, acx+10, acy+r-3 + off, 5, 4)
        else:
            _el(self.screen, leg_c, acx-10, acy+r-3, 5, 4)
            _el(self.screen, leg_c, acx+10, acy+r-3, 5, 4)
        self._draw_face(acx, acy, state, cheek_c)

        if c.carrying is not None:
            self._draw_carry_icon(acx, acy - r - 8, c.carrying)
        
        # Indicador de conversación
        if c.in_conversation:
            self._draw_talking_indicator(acx, acy - r - 12)

    def _draw_carry_icon(self, cx: int, cy: int, resource: str):
        if resource == "apple":
            _ci(self.screen, (200,50,40), cx, cy, 5)
            _ci(self.screen, (230,80,60), cx-1, cy-1, 2)
            pygame.draw.line(self.screen, (80,120,40), (cx,cy-5),(cx+2,cy-8),1)
        elif resource == "wood":
            pygame.draw.rect(self.screen, (139,94,60), (cx-7,cy-4,14,8), border_radius=2)
            pygame.draw.rect(self.screen, (107,66,38), (cx-7,cy-4,14,8), 1, border_radius=2)
        elif resource == "gem":
            pts = [
                (cx,   cy-8), (cx+6, cy-2), (cx+4, cy+5),
                (cx-4, cy+5), (cx-6, cy-2),
            ]
            pygame.draw.polygon(self.screen, C_GEM_DARK, pts)
            pygame.draw.polygon(self.screen, C_GEM_MID, pts, 1)
            _ci(self.screen, C_GEM_LIGHT, cx, cy-5, 1)

    def _draw_talking_indicator(self, cx: int, cy: int):
        """Dibuja una burbuja de diálogo estilo cómic sobre criaturas conversando."""
        # Tres puntos animados para indicar habla
        ticks = pygame.time.get_ticks()
        phase = (ticks // 300) % 3
        
        bw, bh = 24, 16
        bx, by = cx - bw//2, cy - bh
        
        # Sombra suave de la burbuja
        sh = pygame.Surface((bw+4, bh+4), pygame.SRCALPHA)
        pygame.draw.rect(sh, (0, 0, 0, 40), (0, 0, bw+4, bh+4), border_radius=8)
        self.screen.blit(sh, (bx-2, by+2))
        
        # Burbuja blanca
        _rnd_rect(self.screen, (255, 255, 255), bx, by, bw, bh, 6)
        _rnd_rect(self.screen, (100, 100, 150), bx, by, bw, bh, 6, 1)
        
        # Rabillo de la burbuja apuntando a la criatura
        pygame.draw.polygon(self.screen, (255, 255, 255), 
                            [(cx, cy-2), (cx-4, by+bh-2), (cx+4, by+bh-2)])
        pygame.draw.polygon(self.screen, (100, 100, 150), 
                            [(cx, cy-2), (cx-4, by+bh-2), (cx+4, by+bh-2)], 1)

        # Puntos animados
        for i, dx in enumerate([-6, 0, 6]):
            alpha = 255 if i == phase else 100
            dot_color = (80, 80, 120, alpha)
            _ci(self.screen, dot_color, cx + dx, by + bh//2, 2)

    def _draw_face(self, cx, cy, state, cheek_c):
        ey, elx, erx = cy-4, cx-6, cx+6
        if state == "normal":
            _ci(self.screen,(26,42,26),elx,ey,5)
            _ci(self.screen,(26,42,26),erx,ey,5)
            _ci(self.screen,(255,255,255),elx-1,ey-2,2)
            _ci(self.screen,(255,255,255),erx+1,ey-2,2)
            cs = pygame.Surface((10,6),pygame.SRCALPHA)
            pygame.draw.ellipse(cs,(*cheek_c,130),(0,0,10,6))
            self.screen.blit(cs,(cx-15,cy+1))
            self.screen.blit(cs,(cx+5,cy+1))
            pygame.draw.arc(self.screen,(26,42,26),(cx-5,cy+2,10,7),math.pi,2*math.pi,2)
        elif state == "hungry":
            _el(self.screen,(42,26,26),elx,ey-1,5,6)
            _el(self.screen,(42,26,26),erx,ey-1,5,6)
            _ci(self.screen,(255,255,255),elx-1,ey-3,2)
            _ci(self.screen,(255,255,255),erx+1,ey-3,2)
            pygame.draw.line(self.screen,(42,26,26),(cx-9,cy-10),(cx-3,cy-13),2)
            pygame.draw.line(self.screen,(42,26,26),(cx+9,cy-10),(cx+3,cy-13),2)
            _el(self.screen,(42,26,26),cx,cy+5,5,4)
            _el(self.screen,(192,96,96),cx,cy+6,3,2)
            self.screen.blit(self.font_small.render("!",True,(255,204,68)),
                             (cx-3, cy-CREATURE_RADIUS-14))
        elif state == "sad":
            _el(self.screen,(26,42,58),elx,ey,5,4)
            _el(self.screen,(26,42,58),erx,ey,5,4)
            pygame.draw.line(self.screen,(26,42,58),(cx-11,cy-6),(cx-1,cy-8),2)
            pygame.draw.line(self.screen,(26,42,58),(cx+1, cy-6),(cx+11,cy-8),2)
            pygame.draw.arc(self.screen,(26,42,58),(cx-5,cy+2,10,7),0,math.pi,2)
            _el(self.screen,(160,192,240),cx-8,cy+1,2,3)
        elif state == "tired":
            pygame.draw.line(self.screen,(42,42,58),(cx-11,cy-3),(cx-1,cy-1),3)
            pygame.draw.line(self.screen,(42,42,58),(cx+1, cy-3),(cx+11,cy-1),3)
            pygame.draw.line(self.screen,(42,42,58),(cx-4, cy+5),(cx+4, cy+5),2)
            self.screen.blit(self.font_tiny.render("zzz",True,(192,192,210)),
                             (cx+10, cy-CREATURE_RADIUS-10))
        elif state == "critical":
            for ox in [elx,erx]:
                pygame.draw.line(self.screen,(42,10,10),(ox-4,ey-4),(ox+4,ey+4),2)
                pygame.draw.line(self.screen,(42,10,10),(ox+4,ey-4),(ox-4,ey+4),2)
            _el(self.screen,(42,10,10),cx,cy+5,6,5)
            self.screen.blit(self.font_small.render("!!",True,(255,170,68)),
                             (cx-6, cy-CREATURE_RADIUS-14))

    # ---------------------------------------------------------------
    # Burbuja de mensaje
    # ---------------------------------------------------------------

    def _draw_bubble(self, c, message):
        cx, cy = int(c.x), int(c.y)
        pad, max_w = 8, 220
        words = message.split()
        lines, cur = [], ""
        for w in words:
            test = (cur+" "+w).strip()
            if self.font_msg.size(test)[0] > max_w and cur:
                lines.append(cur)
                cur = w
            else:
                cur = test
        if cur:
            lines.append(cur)
        surfs = [self.font_msg.render(l, True, COLOR_MESSAGE_TEXT) for l in lines]
        if not surfs:
            return
        bw = max(s.get_width() for s in surfs) + pad*2
        bh = sum(s.get_height() for s in surfs) + pad*2
        bx = max(4, min(cx-bw//2, WINDOW_WIDTH-bw-4))
        by = max(4, cy-CREATURE_RADIUS-bh-18)
        bubble = pygame.Surface((bw,bh), pygame.SRCALPHA)
        pygame.draw.rect(bubble, (*COLOR_MESSAGE_BG,220), (0,0,bw,bh), border_radius=6)
        pygame.draw.rect(bubble, (100,140,100,180), (0,0,bw,bh), 1, border_radius=6)
        self.screen.blit(bubble, (bx,by))
        tip_y = cy - CREATURE_RADIUS - 4
        if tip_y > by+bh-1:
            pygame.draw.polygon(self.screen, (*COLOR_MESSAGE_BG,180),
                                [(cx,tip_y),(cx-5,by+bh-1),(cx+5,by+bh-1)])
        ty = by + pad
        for s in surfs:
            self.screen.blit(s, (bx+pad, ty))
            ty += s.get_height()

    # ---------------------------------------------------------------
    # TOOLBAR
    # ---------------------------------------------------------------

    def _draw_toolbar(self, selected, clock_obj, placement, wood: int = 0):
        pygame.draw.rect(self.screen, TOOLBAR_WOOD_DARK,
                         (0, _TOOLBAR_Y, WINDOW_WIDTH, TOOLBAR_HEIGHT))
        pygame.draw.line(self.screen, TOOLBAR_WOOD_EDGE,
                         (0, _TOOLBAR_Y), (WINDOW_WIDTH, _TOOLBAR_Y), 2)
        self._draw_info_panel(selected)
        self._draw_palette_toolbar(placement, wood)
        ts = self.font_small.render(
            f"{clock_obj.time_str()}  {clock_obj.period()}", True, TOOLBAR_WOOD_LIGHT)
        self.screen.blit(ts, (WINDOW_WIDTH//2 - ts.get_width()//2, _TOOLBAR_Y + 4))
        # Pista de teclas
        hint = self.font_tiny.render("[Tab] diario", True, TOOLBAR_BTN_DARK)
        self.screen.blit(hint, (WINDOW_WIDTH//2 - hint.get_width()//2, _TOOLBAR_Y + 18))

    def _draw_info_panel(self, selected):
        px, py = _INFO_X, _TOOLBAR_Y + 6
        pw, ph = _INFO_W, TOOLBAR_HEIGHT - 12
        _rnd_rect(self.screen, TOOLBAR_WOOD_MID,  px, py, pw, ph, 6)
        _rnd_rect(self.screen, TOOLBAR_WOOD_EDGE, px, py, pw, ph, 6, 1)

        if selected is None:
            hint = self.font_small.render("click a creature", True, TOOLBAR_TEXT)
            self.screen.blit(hint, (px + pw//2 - hint.get_width()//2,
                                    py + ph//2 - hint.get_height()//2))
            return

        c = selected
        self._draw_creature_mini(px+22, py+ph//2, self._state(c))

        self.screen.blit(self.font_medium.render(c.id, True, TOOLBAR_TEXT), (px+44, py+6))
        self.screen.blit(self.font_tiny.render(f"gen {c.generation}", True, TOOLBAR_BTN_DARK),
                         (px+44, py+19))

        bw = pw - 50
        bh = 6
        bx = px + 44
        needs = [
            (c.needs.hunger,    COLOR_HUNGER_BAR,    True),
            (c.needs.hygiene,   COLOR_HYGIENE_BAR,   False),
            (c.needs.happiness, COLOR_HAPPINESS_BAR, False)
        ]
        by = py + 32
        for val, col, inv in needs:
            pygame.draw.rect(self.screen, TOOLBAR_BTN_DARK, (bx, by, bw, bh), border_radius=2)
            fill = (1.0 - val/NEED_MAX) if inv else (val/NEED_MAX)
            fw = max(0, int(bw * fill))
            if fw:
                pygame.draw.rect(self.screen, col, (bx, by, fw, bh), border_radius=2)
            by += bh + 2

    def _draw_creature_mini(self, cx, cy, state):
        body_c, ear_c, _, cheek_c = _STATE_COLORS[state]
        r = 12
        _el(self.screen, ear_c,   cx-7, cy-r-1, 4, 5)
        _el(self.screen, ear_c,   cx+7, cy-r-1, 4, 5)
        _el(self.screen, cheek_c, cx-7, cy-r-2, 2.5, 3)
        _el(self.screen, cheek_c, cx+7, cy-r-2, 2.5, 3)
        _el(self.screen, body_c, cx, cy, r, int(r*0.88))
        _ci(self.screen, (26,42,26), cx-4, cy-2, 3)
        _ci(self.screen, (26,42,26), cx+4, cy-2, 3)
        _ci(self.screen, (255,255,255), cx-3, cy-3, 1.5)
        _ci(self.screen, (255,255,255), cx+5, cy-3, 1.5)

    # --- Paleta de herramientas ---

    @staticmethod
    def _palette_geometry(palette):
        n       = len(palette) + 1
        panel_w = n * (_BTN_SIZE + _BTN_GAP) - _BTN_GAP + 12
        panel_x = WINDOW_WIDTH - panel_w - 8
        panel_y = _TOOLBAR_Y + 6
        panel_h = TOOLBAR_HEIGHT - 12
        btn_y   = panel_y + 4
        btn_h   = panel_h - 8
        return panel_x, panel_y, panel_w, panel_h, btn_y, btn_h

    def _draw_palette_toolbar(self, placement, wood: int = 0):
        from world.placement import PALETTE, ToolMode

        panel_x, panel_y, panel_w, panel_h, btn_y, btn_h = self._palette_geometry(PALETTE)

        _rnd_rect(self.screen, TOOLBAR_WOOD_MID,  panel_x, panel_y, panel_w, panel_h, 6)
        _rnd_rect(self.screen, TOOLBAR_WOOD_EDGE, panel_x, panel_y, panel_w, panel_h, 6, 1)

        placement.palette_x       = panel_x
        placement.palette_y_start = panel_y
        placement.btn_size        = _BTN_SIZE
        placement.btn_gap         = _BTN_GAP

        bx = panel_x + 6
        for obj_type in PALETTE:
            is_drag = placement.dragging and placement.drag_type == obj_type
            self._draw_palette_btn(obj_type, bx, btn_y, _BTN_SIZE, btn_h, is_drag)
            bx += _BTN_SIZE + _BTN_GAP

        self._draw_axe_btn(bx, btn_y, _BTN_SIZE, btn_h, placement.tool == ToolMode.AXE)

        if placement.dragging and placement.drag_type is not None:
            self._draw_drag_ghost(placement)

        if wood > 0:
            wx = panel_x - 56
            wy = panel_y + panel_h//2 - 10
            _rnd_rect(self.screen, TOOLBAR_WOOD_MID,  wx, wy, 50, 20, 4)
            _rnd_rect(self.screen, TOOLBAR_WOOD_EDGE, wx, wy, 50, 20, 4, 1)
            pygame.draw.rect(self.screen, (139,94,60), (wx+4,wy+4,12,12), border_radius=2)
            pygame.draw.rect(self.screen, (107,66,38), (wx+4,wy+4,12,12), 1, border_radius=2)
            self.screen.blit(self.font_small.render(str(wood),True,TOOLBAR_TEXT),(wx+20,wy+4))

    def _draw_palette_btn(self, obj_type, bx, by, bw, bh, is_dragging):
        bg  = TOOLBAR_BTN_SEL      if is_dragging else TOOLBAR_BTN_DARK
        bdr = TOOLBAR_BTN_SEL_EDGE if is_dragging else TOOLBAR_WOOD_LIGHT
        _rnd_rect(self.screen, bg,  bx, by, bw, bh, 5)
        _rnd_rect(self.screen, bdr, bx, by, bw, bh, 5, 2 if is_dragging else 1)
        if not is_dragging:
            self._draw_object_icon(obj_type, bx+bw//2, by+bh//2-4)
        label = OBJ_LABEL.get(obj_type, obj_type.name)
        ls = self.font_tiny.render(label, True, TOOLBAR_TEXT)
        self.screen.blit(ls, (bx+bw//2-ls.get_width()//2, by+bh-13))

    def _draw_axe_btn(self, bx, by, bw, bh, active):
        bg  = TOOLBAR_BTN_SEL      if active else TOOLBAR_BTN_DARK
        bdr = TOOLBAR_BTN_SEL_EDGE if active else TOOLBAR_WOOD_LIGHT
        _rnd_rect(self.screen, bg,  bx, by, bw, bh, 5)
        _rnd_rect(self.screen, bdr, bx, by, bw, bh, 5, 2 if active else 1)
        cx, cy = bx+bw//2, by+bh//2-4
        pygame.draw.line(self.screen, (139,94,60), (cx-8,cy+12), (cx+6,cy-4), 3)
        pts = [(cx+2,cy-8),(cx+12,cy-4),(cx+8,cy+4),(cx-2,cy+2)]
        pygame.draw.polygon(self.screen, (180,190,200), pts)
        pygame.draw.polygon(self.screen, (140,150,160), pts, 1)
        ls = self.font_tiny.render("hacha", True, TOOLBAR_TEXT)
        self.screen.blit(ls, (bx+bw//2-ls.get_width()//2, by+bh-13))

    def _draw_object_icon(self, obj_type, cx, cy):
        if obj_type == ObjType.TREE:
            _el(self.screen,(45,110,40),cx,cy-4,16,14)
            _el(self.screen,(58,138,52),cx-3,cy-8,10,9)
            pygame.draw.rect(self.screen,(107,66,38),(cx-3,cy+8,7,10),border_radius=2)
            _ci(self.screen,(200,50,40),cx-6,cy-10,3)
            _ci(self.screen,(200,50,40),cx+4,cy-7,3)
        elif obj_type == ObjType.BATH:
            pygame.draw.rect(self.screen,(208,232,240),(cx-12,cy-6,24,16),border_radius=4)
            pygame.draw.rect(self.screen,(90,180,212),(cx-10,cy-1,20,9),border_radius=3)
            _ci(self.screen,(144,212,240),cx-4,cy+2,2)
            _ci(self.screen,(144,212,240),cx+3,cy+1,1.5)
            pygame.draw.rect(self.screen,(192,200,208),(cx-3,cy-11,6,5),border_radius=1)
        elif obj_type == ObjType.BALL:
            _ci(self.screen,(224,64,48),cx,cy,14)
            pygame.draw.arc(self.screen,(255,255,255),(cx-14,cy-8,28,16),0,math.pi,2)
            pygame.draw.arc(self.screen,(255,255,255),(cx-14,cy-8,28,16),math.pi,2*math.pi,2)
            _el(self.screen,(255,255,255),cx-5,cy-8,5,3)
        elif obj_type == ObjType.STORE:
            pygame.draw.polygon(self.screen, C_STORE_ROOF,
                                [(cx-14,cy),(cx,cy-11),(cx+14,cy)])
            _rnd_rect(self.screen, C_STORE_WALL, cx-12, cy, 24, 13, 2)
            _rnd_rect(self.screen, C_STORE_DOOR, cx-4,  cy+3, 8, 10, 1)
        elif obj_type == ObjType.MINE:
            # Mini mina en botón de paleta
            roof_pts = [(cx-13, cy-2), (cx, cy-12), (cx+13, cy-2)]
            pygame.draw.polygon(self.screen, C_MINE_ROOF, roof_pts)
            _rnd_rect(self.screen, C_MINE_WOOD, cx-11, cy-2, 22, 14, 2)
            _rnd_rect(self.screen, (30,18,8), cx-5, cy+1, 10, 11, 1)
            # Gema en el tejado
            _ci(self.screen, C_GEM_MID,  cx, cy-13, 3)
            _ci(self.screen, C_GEM_LIGHT, cx, cy-13, 1)

    def _draw_drag_ghost(self, placement):
        mx, my   = placement.drag_x, placement.drag_y
        obj_type = placement.drag_type
        if obj_type is None:
            return
        if placement.hover_valid and my < _WORLD_H:
            size    = placement.drag_size()
            blocked = placement.hover_blocked()
            col     = PLACEMENT_BLOCKED_COLOR if blocked else PLACEMENT_HOVER_COLOR
            for dc in range(size):
                for dr in range(size):
                    gx = (placement.hover_col + dc) * GRID_CELL
                    gy = (placement.hover_row + dr) * GRID_CELL
                    ghost = pygame.Surface((GRID_CELL, GRID_CELL), pygame.SRCALPHA)
                    pygame.draw.rect(ghost, (*col,50),  (0,0,GRID_CELL,GRID_CELL))
                    pygame.draw.rect(ghost, (*col,180), (0,0,GRID_CELL,GRID_CELL), 1)
                    self.screen.blit(ghost, (gx,gy))
            snap_x = placement.hover_col * GRID_CELL + (size * GRID_CELL) // 2
            snap_y = placement.hover_row * GRID_CELL + (size * GRID_CELL) // 2
        else:
            snap_x, snap_y = mx, my
        self._draw_object_icon(obj_type, snap_x, snap_y - 4)

    # ---------------------------------------------------------------
    # Contador de población
    # ---------------------------------------------------------------

    def _draw_population_badge(self, population: int):
        cx, cy = _POP_CX, _POP_CY
        _ci(self.screen, TOOLBAR_WOOD_MID,  cx, cy, 30)
        _ci(self.screen, TOOLBAR_WOOD_EDGE, cx, cy, 30, 2)
        _ci(self.screen, TOOLBAR_WOOD_DARK, cx, cy, 26)
        _el(self.screen, (78,180,98), cx, cy-4, 11, 10)
        _el(self.screen, (78,180,98), cx-7, cy-13, 3, 5)
        _el(self.screen, (78,180,98), cx+7, cy-13, 3, 5)
        _ci(self.screen, (26,42,26), cx-3, cy-5, 2.5)
        _ci(self.screen, (26,42,26), cx+3, cy-5, 2.5)
        num = self.font_large.render(str(population), True, TOOLBAR_WOOD_LIGHT)
        self.screen.blit(num, (cx-num.get_width()//2, cy+8))

    # ---------------------------------------------------------------
    # Overlay diario
    # ---------------------------------------------------------------

    def _draw_diary_overlay(self, diary_entries: List[dict]) -> None:
        """Panel semitransparente que muestra las últimas entradas del diario."""
        ow, oh = 520, _WORLD_H - 40
        ox = (WINDOW_WIDTH - ow) // 2
        oy = 20

        panel = pygame.Surface((ow, oh), pygame.SRCALPHA)
        panel.fill(C_DIARY_BG)
        pygame.draw.rect(panel, C_DIARY_BORDER, (0, 0, ow, oh), 2, border_radius=10)

        title = self.font_large.render("✦  Diario de las criaturas  ✦", True, C_DIARY_HEAD)
        panel.blit(title, (ow//2 - title.get_width()//2, 12))
        pygame.draw.line(panel, C_DIARY_LINE, (16, 32), (ow-16, 32), 1)

        if not diary_entries:
            self._draw_empty_diary(panel, ow, oh)
        else:
            self._draw_diary_entries(panel, diary_entries, ow, oh)

        hint = self.font_tiny.render("[Tab] cerrar", True, C_DIARY_META)
        panel.blit(hint, (ow//2 - hint.get_width()//2, oh - 14))
        self.screen.blit(panel, (ox, oy))

    def _draw_empty_diary(self, panel: pygame.Surface, ow: int, oh: int):
        txt = "Aún no hay entradas. Las criaturas necesitan gemas."
        empty = self.font_small.render(txt, True, C_DIARY_META)
        panel.blit(empty, (ow//2 - empty.get_width()//2, oh//2))

    def _draw_diary_entries(self, panel: pygame.Surface, entries: List[dict], ow: int, oh: int):
        y = 42
        for entry in reversed(entries[-12:]):
            if y >= oh - 30: break
            
            # Cabecera
            dt = entry.get('datetime', '')[-8:]
            meta = f"[{dt}]  {entry['creature_id']}  💎×{entry['gems_spent']}"
            panel.blit(self.font_small.render(meta, True, C_DIARY_META), (14, y))
            y += 15

            # Texto envuelto
            y = self._draw_wrapped_text(panel, entry['text'], 14, y, ow - 28, oh)
            
            y += 6
            pygame.draw.line(panel, C_DIARY_LINE, (14, y), (ow-14, y), 1)
            y += 8

    def _draw_wrapped_text(self, panel: pygame.Surface, text: str, x: int, y: int, max_w: int, oh: int) -> int:
        words = text.split()
        line = ""
        for w in words:
            if y >= oh - 20: break
            test = (line + " " + w).strip()
            if self.font_msg.size(test)[0] > max_w and line:
                panel.blit(self.font_msg.render(line, True, C_DIARY_TEXT), (x, y))
                y += 14
                line = w
            else:
                line = test
        if line and y < oh - 20:
            panel.blit(self.font_msg.render(line, True, C_DIARY_TEXT), (x, y))
            y += 14
        return y
