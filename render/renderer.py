# =============================================================================
# render/renderer.py — swarm-alife
# =============================================================================

import pygame
import math
import random
import logging
from typing import Optional, TYPE_CHECKING

from config import (
    WINDOW_WIDTH, WINDOW_HEIGHT, UI_PANEL_WIDTH,
    CREATURE_RADIUS, NEED_BAR_WIDTH, NEED_BAR_HEIGHT, NEED_BAR_OFFSET_Y,
    COLOR_UI_BG, COLOR_UI_TEXT,
    COLOR_NEED_BAR_BG, COLOR_HUNGER_BAR, COLOR_HYGIENE_BAR,
    COLOR_HAPPINESS_BAR, COLOR_ENERGY_BAR,
    COLOR_MESSAGE_BG, COLOR_MESSAGE_TEXT,
    NEED_MAX, GRID_CELL,
    PLACEMENT_HOVER_COLOR, PLACEMENT_BLOCKED_COLOR,
)
from locales import t
from world.objects import ObjType, OBJ_LABEL, WorldObject, GroundItem

if TYPE_CHECKING:
    from agent.creature import Creature
    from agent.memory.sim_clock import SimClock
    from world.objects import WorldMap
    from world.placement import PlacementMode

logger = logging.getLogger(__name__)

_PANEL_X = WINDOW_WIDTH - UI_PANEL_WIDTH
_AREA_W  = WINDOW_WIDTH - UI_PANEL_WIDTH

C_GRASS_DARK = (38,  58,  28)
C_GRASS_MID  = (44,  62,  30)
C_GRASS_LIT  = (52,  74,  34)
C_PANEL_SEP  = (50,  80,  45)
C_PANEL_LINE = (55,  75,  50)

_STATE_COLORS = {
    "normal":   ((120, 196, 138), (90,  170, 110), (88,  160, 102), (248, 164, 180)),
    "hungry":   ((196, 168,  80), (170, 142,  60), (160, 132,  50), (248, 196, 160)),
    "sad":      ((104, 136, 192), ( 74, 106, 170), ( 74, 106, 170), (160, 180, 232)),
    "tired":    ((136, 136, 152), (110, 110, 122), (106, 106, 118), (176, 176, 192)),
    "critical": ((208,  80,  64), (176,  56,  44), (176,  48,  36), (240, 160, 128)),
}
C_UI_LABEL = (160, 200, 160)
C_UI_VALUE = (200, 220, 200)
C_UI_DIM   = (100, 130, 100)
C_GEN_BG   = (26,  42,  26)
C_GEN_TEXT = (128, 200, 128)
C_SEL_RING = (255, 220,  50)
C_PULSE    = (232, 112,  96)


def _el(surf, color, cx, cy, rx, ry, w=0):
    pygame.draw.ellipse(surf, color,
                        (int(cx-rx), int(cy-ry), max(1,int(rx*2)), max(1,int(ry*2))), w)

def _ci(surf, color, cx, cy, r, w=0):
    pygame.draw.circle(surf, color, (int(cx), int(cy)), max(1, int(r)), w)


class Renderer:
    def __init__(self, screen: pygame.Surface):
        self.screen   = screen
        self._pulse_t = 0.0
        self._init_fonts()
        self._grass   = self._build_grass()
        logger.info("Renderer initialized")

    def _init_fonts(self):
        self.font_tiny   = pygame.font.SysFont("monospace", 10)
        self.font_small  = pygame.font.SysFont("monospace", 11)
        self.font_medium = pygame.font.SysFont("monospace", 13)
        self.font_large  = pygame.font.SysFont("monospace", 15, bold=True)
        self.font_msg    = pygame.font.SysFont("monospace", 12)

    # ---------------------------------------------------------------
    # Hierba
    # ---------------------------------------------------------------

    def _build_grass(self) -> pygame.Surface:
        surf = pygame.Surface((_AREA_W, WINDOW_HEIGHT))
        surf.fill(C_GRASS_DARK)
        rng = random.Random(42)
        for row in range(WINDOW_HEIGHT // GRID_CELL + 1):
            for col in range(_AREA_W // GRID_CELL + 1):
                if (row + col) % 2 == 0:
                    pygame.draw.rect(surf, C_GRASS_MID,
                                     (col*GRID_CELL, row*GRID_CELL, GRID_CELL, GRID_CELL))
        for _ in range(240):
            gx = rng.randint(4, _AREA_W - 4)
            gy = rng.randint(4, WINDOW_HEIGHT - 4)
            h  = rng.randint(5, 13)
            pygame.draw.line(surf, C_GRASS_LIT, (gx, gy), (gx, gy-h), 1)
            if rng.random() > 0.5:
                pygame.draw.line(surf, C_GRASS_LIT, (gx+2, gy), (gx+3, gy-h+3), 1)
        return surf

    # ---------------------------------------------------------------
    # Frame
    # ---------------------------------------------------------------

    def draw_frame(self, creatures, selected, clock_obj, world, placement, delta=0.016):
        self._pulse_t += delta
        self.screen.blit(self._grass, (0, 0))

        # Hover de celda (siempre visible cuando hay objeto seleccionado)
        if placement.selected is not None:
            self._draw_cell_hover(placement)

        self._draw_objects(world)
        self._draw_ground_items(world)
        self._draw_creatures(creatures)
        self._draw_panel(selected, clock_obj, len(creatures), placement)
        pygame.display.flip()

    # ---------------------------------------------------------------
    # Hover de celda
    # ---------------------------------------------------------------

    def _draw_cell_hover(self, placement):
        hx = placement.hover_col * GRID_CELL
        hy = placement.hover_row * GRID_CELL
        blocked = placement.hover_blocked()
        color   = PLACEMENT_BLOCKED_COLOR if blocked else PLACEMENT_HOVER_COLOR
        hover   = pygame.Surface((GRID_CELL, GRID_CELL), pygame.SRCALPHA)
        pygame.draw.rect(hover, (*color, 45),  (0, 0, GRID_CELL, GRID_CELL))
        pygame.draw.rect(hover, (*color, 160), (0, 0, GRID_CELL, GRID_CELL), 1)
        self.screen.blit(hover, (hx, hy))

    # ---------------------------------------------------------------
    # Objetos del mundo
    # ---------------------------------------------------------------

    def _draw_objects(self, world):
        for obj in world.all_objects():
            cx = int(obj.px)
            cy = int(obj.py)
            # Animación shake del árbol
            if obj.type == ObjType.TREE and obj.shake_t > 0:
                sway = int(math.sin(obj.shake_t * 40) * 3 * (obj.shake_t / 0.4))
                cx += sway
            self._draw_object(obj, cx, cy)

    def _draw_object(self, obj: WorldObject, cx: int, cy: int):
        if   obj.type == ObjType.TREE: self._draw_tree(cx, cy, obj.apple_count if obj.has_apples else -1)
        elif obj.type == ObjType.BATH: self._draw_bath(cx, cy)
        elif obj.type == ObjType.BALL: self._draw_ball(cx, cy)
        elif obj.type == ObjType.BED:  self._draw_bed(cx, cy)

    def _draw_tree(self, cx, cy, apple_count=0):
        """apple_count=-1 = árbol decorativo sin manzanas."""
        s = pygame.Surface((44, 12), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (0,0,0,50), (0,0,44,12))
        self.screen.blit(s, (cx-22, cy+10))
        pygame.draw.rect(self.screen, (107,66,38), (cx-5,cy-2,10,16), border_radius=3)
        pygame.draw.rect(self.screen, (125,80,48), (cx-3,cy,4,12))
        _el(self.screen, (45,110,40), cx, cy-16, 22, 20)
        _el(self.screen, (58,138,52), cx-4, cy-20, 14, 13)
        _el(self.screen, (42,98,36),  cx+4, cy-14, 10, 9)
        _el(self.screen, (74,168,66), cx-6, cy-24, 6, 5)
        if apple_count > 0:
            apple_positions = [(-8,-22),(6,-18),(-2,-28)]
            for i in range(min(apple_count, 3)):
                ax, ay = apple_positions[i]
                _ci(self.screen, (200,50,40), cx+ax, cy+ay, 4)
                _ci(self.screen, (230,80,60), cx+ax-1, cy+ay-1, 2)
                pygame.draw.line(self.screen, (80,120,40),
                                 (cx+ax, cy+ay-4), (cx+ax+2, cy+ay-7), 1)

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

    def _draw_bed(self, cx, cy):
        s = pygame.Surface((40,10), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (0,0,0,50), (0,0,40,10))
        self.screen.blit(s, (cx-20,cy+12))
        pygame.draw.rect(self.screen,(139,94,60),(cx-18,cy-2,36,20),border_radius=4)
        pygame.draw.rect(self.screen,(212,168,112),(cx-16,cy-6,32,16),border_radius=3)
        pygame.draw.rect(self.screen,(232,208,160),(cx-15,cy-6,30,10),border_radius=2)
        pygame.draw.rect(self.screen,(240,232,208),(cx-14,cy-8,12,8),border_radius=3)
        pygame.draw.rect(self.screen,(255,248,238),(cx-13,cy-7,10,6),border_radius=2)
        for px_ in [-14,14]:
            pygame.draw.rect(self.screen,(107,66,38),(cx+px_-2,cy+16,4,5),border_radius=1)
        self.screen.blit(self.font_tiny.render("zzz",True,(200,216,240)),(cx+10,cy-18))

    # ---------------------------------------------------------------
    # Manzanas en el suelo
    # ---------------------------------------------------------------

    def _draw_ground_items(self, world):
        for item in world.ground_items():
            self._draw_ground_apple(item)

    def _draw_ground_apple(self, item: GroundItem):
        cx, cy = int(item.x), int(item.y)
        # Se pone más oscura al pudrirse
        fade = 1.0 - (item.age / item.age.__class__(30.0) if item.age > 0 else 0)
        from world.objects import APPLE_ROT_TIME
        fade  = max(0.2, 1.0 - item.age / APPLE_ROT_TIME * 0.7)
        red   = int(180 * fade)
        green = int(40  * fade)
        # Sombra
        sh = pygame.Surface((14,6), pygame.SRCALPHA)
        pygame.draw.ellipse(sh, (0,0,0,40), (0,0,14,6))
        self.screen.blit(sh, (cx-7, cy+3))
        # Manzana
        _ci(self.screen, (red, green, 30), cx, cy, 5)
        _ci(self.screen, (min(255,red+40), green+20, 40), cx-1, cy-1, 2)
        # Rabillo
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
        s = pygame.Surface((40,12), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (0,0,0,55), (0,0,40,12))
        self.screen.blit(s, (int(c.x)-20, int(c.y)+CREATURE_RADIUS-4))

    def _state(self, c) -> str:
        n = c.needs
        if n.is_critical():    return "critical"
        if n.hunger    >= 75:  return "hungry"
        if n.happiness <= 30:  return "sad"
        if n.energy    <= 25:  return "tired"
        return "normal"

    def _draw_creature(self, c):
        cx, cy = int(c.x), int(c.y)
        state  = self._state(c)
        body_c, ear_c, leg_c, cheek_c = _STATE_COLORS[state]
        R = CREATURE_RADIUS

        is_walking = c.speed_real > 8.0
        if is_walking:
            freq, bob_amp, lean_amp = 8.0, 2.5, 2.0
            bob_y    = int(math.sin(c.anim_t * freq) * bob_amp)
            lean_x   = int(math.sin(c.anim_t * freq * 0.5) * lean_amp)
            stretch_y = 1.0 + math.sin(c.anim_t * freq) * 0.06
            stretch_x = 1.0 - math.sin(c.anim_t * freq) * 0.04
        else:
            freq, bob_amp = 1.8, 1.2
            bob_y    = int(math.sin(c.anim_t * freq) * bob_amp)
            lean_x   = 0
            stretch_y = 1.0 + math.sin(c.anim_t * freq) * 0.03
            stretch_x = 1.0

        acy = cy + bob_y
        acx = cx + lean_x

        if c.selected:
            _ci(self.screen, C_SEL_RING, cx, cy, R+5, 2)

        if state == "critical":
            pulse = abs(math.sin(self._pulse_t * 3.5))
            ps = pygame.Surface((80,80), pygame.SRCALPHA)
            _ci(ps, (*C_PULSE, int(160*pulse)), 40, 40, R+4+int(pulse*6), 2)
            self.screen.blit(ps, (cx-40,cy-40))

        if c._target_obj is not None and not c._using_obj:
            ts = pygame.Surface((_AREA_W, WINDOW_HEIGHT), pygame.SRCALPHA)
            pygame.draw.line(ts, (200,200,100,35),
                             (cx,cy), (int(c._target_obj.px),int(c._target_obj.py)), 1)
            self.screen.blit(ts, (0,0))

        _el(self.screen, ear_c,   acx-10, acy-R-2, 5, 7)
        _el(self.screen, ear_c,   acx+10, acy-R-2, 5, 7)
        _el(self.screen, cheek_c, acx-10, acy-R-3, 3, 4)
        _el(self.screen, cheek_c, acx+10, acy-R-3, 3, 4)

        rx = max(1, int(R * stretch_x))
        ry = max(1, int(R * 0.88 * stretch_y))
        _el(self.screen, body_c, acx, acy, rx, ry)

        if is_walking:
            leg_off = int(math.sin(c.anim_t * 8.0) * 3)
            _el(self.screen, leg_c, acx-10, acy+R-3 - leg_off, 5, 4)
            _el(self.screen, leg_c, acx+10, acy+R-3 + leg_off, 5, 4)
        else:
            _el(self.screen, leg_c, acx-10, acy+R-3, 5, 4)
            _el(self.screen, leg_c, acx+10, acy+R-3, 5, 4)

        self._draw_face(acx, acy, state, cheek_c)
        self._draw_bars(c, cx, cy)

        gs = self.font_tiny.render(f"g{c.generation}", True, C_GEN_TEXT)
        gw = gs.get_width() + 6
        bg = pygame.Surface((gw,13), pygame.SRCALPHA)
        pygame.draw.rect(bg, (*C_GEN_BG,200), (0,0,gw,13), border_radius=3)
        self.screen.blit(bg, (cx-gw//2, cy-R-20))
        self.screen.blit(gs, (cx-gs.get_width()//2, cy-R-19))

    def _draw_face(self, cx, cy, state, cheek_c):
        ey, elx, erx = cy-4, cx-6, cx+6
        if state == "normal":
            _ci(self.screen,(26,42,26),elx,ey,5)
            _ci(self.screen,(26,42,26),erx,ey,5)
            _ci(self.screen,(255,255,255),elx-1,ey-2,2)
            _ci(self.screen,(255,255,255),erx+1,ey-2,2)
            cs=pygame.Surface((10,6),pygame.SRCALPHA)
            pygame.draw.ellipse(cs,(*cheek_c,130),(0,0,10,6))
            self.screen.blit(cs,(cx-15,cy+1)); self.screen.blit(cs,(cx+5,cy+1))
            pygame.draw.arc(self.screen,(26,42,26),(cx-5,cy+2,10,7),math.pi,2*math.pi,2)
        elif state == "hungry":
            _el(self.screen,(42,26,26),elx,ey-1,5,6); _el(self.screen,(42,26,26),erx,ey-1,5,6)
            _ci(self.screen,(255,255,255),elx-1,ey-3,2); _ci(self.screen,(255,255,255),erx+1,ey-3,2)
            pygame.draw.line(self.screen,(42,26,26),(cx-9,cy-10),(cx-3,cy-13),2)
            pygame.draw.line(self.screen,(42,26,26),(cx+9,cy-10),(cx+3,cy-13),2)
            _el(self.screen,(42,26,26),cx,cy+5,5,4); _el(self.screen,(192,96,96),cx,cy+6,3,2)
            self.screen.blit(self.font_small.render("!",True,(255,204,68)),(cx-3,cy-CREATURE_RADIUS-14))
        elif state == "sad":
            _el(self.screen,(26,42,58),elx,ey,5,4); _el(self.screen,(26,42,58),erx,ey,5,4)
            pygame.draw.line(self.screen,(26,42,58),(cx-11,cy-6),(cx-1,cy-8),2)
            pygame.draw.line(self.screen,(26,42,58),(cx+1,cy-6),(cx+11,cy-8),2)
            pygame.draw.arc(self.screen,(26,42,58),(cx-5,cy+2,10,7),0,math.pi,2)
            _el(self.screen,(160,192,240),cx-8,cy+1,2,3)
        elif state == "tired":
            pygame.draw.line(self.screen,(42,42,58),(cx-11,cy-3),(cx-1,cy-1),3)
            pygame.draw.line(self.screen,(42,42,58),(cx+1,cy-3),(cx+11,cy-1),3)
            pygame.draw.line(self.screen,(42,42,58),(cx-4,cy+5),(cx+4,cy+5),2)
            self.screen.blit(self.font_tiny.render("zzz",True,(192,192,210)),(cx+10,cy-CREATURE_RADIUS-10))
        elif state == "critical":
            for ox in [elx,erx]:
                pygame.draw.line(self.screen,(42,10,10),(ox-4,ey-4),(ox+4,ey+4),2)
                pygame.draw.line(self.screen,(42,10,10),(ox+4,ey-4),(ox-4,ey+4),2)
            _el(self.screen,(42,10,10),cx,cy+5,6,5)
            self.screen.blit(self.font_small.render("!!",True,(255,170,68)),(cx-6,cy-CREATURE_RADIUS-14))

    def _draw_bars(self, c, cx, cy):
        bars=[(c.needs.hunger,COLOR_HUNGER_BAR,True),(c.needs.hygiene,COLOR_HYGIENE_BAR,False),
              (c.needs.happiness,COLOR_HAPPINESS_BAR,False),(c.needs.energy,COLOR_ENERGY_BAR,False)]
        x0=cx-NEED_BAR_WIDTH//2; y0=cy+NEED_BAR_OFFSET_Y
        for i,(val,col,inv) in enumerate(bars):
            by=y0+i*(NEED_BAR_HEIGHT+2)
            pygame.draw.rect(self.screen,COLOR_NEED_BAR_BG,(x0,by,NEED_BAR_WIDTH,NEED_BAR_HEIGHT),border_radius=2)
            fill=(1.0-val/NEED_MAX) if inv else (val/NEED_MAX)
            fw=max(0,int(NEED_BAR_WIDTH*fill))
            if fw: pygame.draw.rect(self.screen,col,(x0,by,fw,NEED_BAR_HEIGHT),border_radius=2)

    # ---------------------------------------------------------------
    # Burbuja
    # ---------------------------------------------------------------

    def _draw_bubble(self, c, message):
        cx,cy=int(c.x),int(c.y); pad,max_w=8,200
        words=message.split(); lines,cur=[],""
        for w in words:
            test=(cur+" "+w).strip()
            if self.font_msg.size(test)[0]>max_w and cur: lines.append(cur); cur=w
            else: cur=test
        if cur: lines.append(cur)
        surfs=[self.font_msg.render(l,True,COLOR_MESSAGE_TEXT) for l in lines]
        if not surfs: return
        bw=max(s.get_width() for s in surfs)+pad*2
        bh=sum(s.get_height() for s in surfs)+pad*2
        bx=max(4,min(cx-bw//2,_AREA_W-bw-4)); by=cy-CREATURE_RADIUS-bh-18
        bubble=pygame.Surface((bw,bh),pygame.SRCALPHA)
        pygame.draw.rect(bubble,(*COLOR_MESSAGE_BG,220),(0,0,bw,bh),border_radius=6)
        pygame.draw.rect(bubble,(100,140,100,180),(0,0,bw,bh),1,border_radius=6)
        self.screen.blit(bubble,(bx,by))
        tip_y=cy-CREATURE_RADIUS-4
        pygame.draw.polygon(self.screen,(*COLOR_MESSAGE_BG,180),
                            [(cx,tip_y),(cx-5,by+bh-1),(cx+5,by+bh-1)])
        ty=by+pad
        for s in surfs: self.screen.blit(s,(bx+pad,ty)); ty+=s.get_height()

    # ---------------------------------------------------------------
    # Panel UI
    # ---------------------------------------------------------------

    def _draw_panel(self, selected, clock_obj, population, placement):
        pygame.draw.rect(self.screen, COLOR_UI_BG, (_PANEL_X,0,UI_PANEL_WIDTH,WINDOW_HEIGHT))
        pygame.draw.line(self.screen, C_PANEL_SEP, (_PANEL_X,0), (_PANEL_X,WINDOW_HEIGHT), 2)
        x=_PANEL_X+14; y=14

        # Reloj + población
        self._txt(f"{clock_obj.time_str()}  {clock_obj.period()}", x, y, self.font_medium, C_UI_VALUE); y+=18
        self._txt(f"población: {population}", x, y, self.font_small, C_UI_DIM); y+=20
        self._hline(y); y+=10

        # Criatura seleccionada
        if selected:
            y = self._panel_selected(selected, x, y)
        else:
            self._txt(t("ui_no_selection"), x, y, self.font_small, C_UI_DIM); y+=24

        self._hline(y); y+=10

        # Paleta de objetos
        y = self._draw_palette_panel(placement, x, y)

    def _panel_selected(self, c, x, y) -> int:
        self._txt(c.id, x, y, self.font_large, C_UI_VALUE)
        self._txt(f"gen {c.generation}  |  {int(c.age)}s", x, y+18, self.font_tiny, C_UI_DIM)
        y += 38
        needs=[(t("ui_hunger"),c.needs.hunger,COLOR_HUNGER_BAR,True),
               (t("ui_hygiene"),c.needs.hygiene,COLOR_HYGIENE_BAR,False),
               (t("ui_happiness"),c.needs.happiness,COLOR_HAPPINESS_BAR,False),
               (t("ui_energy"),c.needs.energy,COLOR_ENERGY_BAR,False)]
        bw=UI_PANEL_WIDTH-28; bh=9
        for label,val,col,inv in needs:
            self._txt(f"{label}  {val:.0f}", x, y, self.font_small, C_UI_LABEL)
            y+=self.font_small.get_height()+3
            pygame.draw.rect(self.screen,COLOR_NEED_BAR_BG,(x,y,bw,bh),border_radius=3)
            fill=(1.0-val/NEED_MAX) if inv else (val/NEED_MAX)
            fw=max(0,int(bw*fill))
            if fw: pygame.draw.rect(self.screen,col,(x,y,fw,bh),border_radius=3)
            y+=bh+10
        if c.current_message:
            self._hline(y); y+=8
            self._txt(t("ui_messages"), x, y, self.font_medium, C_UI_VALUE); y+=16
            words=c.current_message.split(); line,lines="",[]
            for w in words:
                test=(line+" "+w).strip()
                if self.font_small.size(test)[0]>UI_PANEL_WIDTH-28 and line:
                    lines.append(line); line=w
                else: line=test
            if line: lines.append(line)
            for l in lines: self._txt(l,x+4,y,self.font_small,(180,220,180)); y+=14
        return y

    def _draw_palette_panel(self, placement, x: int, y: int) -> int:
        from world.placement import PALETTE
        self._txt("objetos", x, y, self.font_medium, C_UI_VALUE); y+=18
        self._txt("clic der. = borrar", x, y, self.font_tiny, C_UI_DIM); y+=14

        chip_w = UI_PANEL_WIDTH - 28
        chip_h = 32

        for i, obj_type in enumerate(PALETTE):
            sel = obj_type == placement.selected
            bg  = (42,80,32) if sel else (28,44,22)
            bdr = (144,224,112) if sel else (50,76,38)
            pygame.draw.rect(self.screen, bg,  (x,y,chip_w,chip_h), border_radius=4)
            pygame.draw.rect(self.screen, bdr, (x,y,chip_w,chip_h), 1 if not sel else 2, border_radius=4)

            # Miniatura
            self._draw_object_mini(obj_type, x+16, y+chip_h//2)

            # Label + tecla
            label = OBJ_LABEL.get(obj_type, obj_type.name)
            lc    = (144,224,112) if sel else (120,180,100)
            self._txt(f"[{i+1}] {label}", x+32, y+8, self.font_small, lc)

            y += chip_h + 4

        return y + 4

    def _draw_object_mini(self, obj_type: ObjType, cx: int, cy: int):
        if obj_type == ObjType.TREE:
            _el(self.screen,(58,138,52),cx,cy-4,10,9)
            pygame.draw.rect(self.screen,(107,66,38),(cx-2,cy+4,5,7),border_radius=1)
            _ci(self.screen,(200,50,40),cx-3,cy-8,3)
        elif obj_type == ObjType.BATH:
            pygame.draw.rect(self.screen,(208,232,240),(cx-9,cy-5,18,13),border_radius=3)
            pygame.draw.rect(self.screen,(90,180,212),(cx-7,cy-1,14,7),border_radius=2)
        elif obj_type == ObjType.BALL:
            _ci(self.screen,(224,64,48),cx,cy,9)
            pygame.draw.arc(self.screen,(255,255,255),(cx-9,cy-5,18,10),0,math.pi,1)
        elif obj_type == ObjType.BED:
            pygame.draw.rect(self.screen,(139,94,60),(cx-9,cy-2,18,12),border_radius=2)
            pygame.draw.rect(self.screen,(232,208,160),(cx-8,cy-4,16,8),border_radius=1)
            pygame.draw.rect(self.screen,(240,232,208),(cx-7,cy-5,7,5),border_radius=1)

    # ---------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------

    def _hline(self, y):
        pygame.draw.line(self.screen, C_PANEL_LINE, (_PANEL_X+8,y),(WINDOW_WIDTH-8,y),1)

    def _txt(self, text, x, y, font, color=None):
        self.screen.blit(font.render(text,True,color or COLOR_UI_TEXT),(x,y))
