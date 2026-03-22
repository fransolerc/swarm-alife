# =============================================================================
# render/renderer.py — swarm-alife
# Rendering Pygame con lenguaje visual pixel art generado por código.
# Solo dibuja, no contiene lógica de simulación.
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
    NEED_MAX,
)
from locales import t

if TYPE_CHECKING:
    from agent.creature import Creature
    from agent.memory.sim_clock import SimClock

logger = logging.getLogger(__name__)

_PANEL_X = WINDOW_WIDTH - UI_PANEL_WIDTH
_AREA_W  = WINDOW_WIDTH - UI_PANEL_WIDTH

# --- Paleta mundo ---
C_GRASS_DARK  = (38,  58,  28)
C_GRASS_MID   = (44,  62,  30)
C_GRASS_LIGHT = (52,  74,  34)
C_PANEL_SEP   = (50,  80,  45)
C_PANEL_LINE  = (55,  75,  50)

# --- Colores criatura por estado: (cuerpo, orejas, patas, mejilla) ---
_STATE_COLORS = {
    "normal":   ((120, 196, 138), (90,  170, 110), (88,  160, 102), (248, 164, 180)),
    "hungry":   ((196, 168,  80), (170, 142,  60), (160, 132,  50), (248, 196, 160)),
    "sad":      ((104, 136, 192), ( 74, 106, 170), ( 74, 106, 170), (160, 180, 232)),
    "tired":    ((136, 136, 152), (110, 110, 122), (106, 106, 118), (176, 176, 192)),
    "critical": ((208,  80,  64), (176,  56,  44), (176,  48,  36), (240, 160, 128)),
}

C_UI_LABEL  = (160, 200, 160)
C_UI_VALUE  = (200, 220, 200)
C_UI_DIM    = (100, 130, 100)
C_GEN_BG    = (26,  42,  26)
C_GEN_TEXT  = (128, 200, 128)
C_SEL_RING  = (255, 220,  50)
C_PULSE     = (232, 112,  96)


def _ellipse(surf, color, cx, cy, rx, ry, width=0):
    pygame.draw.ellipse(surf, color, (int(cx - rx), int(cy - ry), int(rx * 2), int(ry * 2)), width)


def _circle(surf, color, cx, cy, r, width=0):
    pygame.draw.circle(surf, color, (int(cx), int(cy)), max(1, int(r)), width)


class Renderer:
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self._init_fonts()
        self._grass = self._build_grass()
        self._pulse_t = 0.0
        logger.info("Renderer initialized")

    def _init_fonts(self):
        self.font_tiny   = pygame.font.SysFont("monospace", 10)
        self.font_small  = pygame.font.SysFont("monospace", 11)
        self.font_medium = pygame.font.SysFont("monospace", 13)
        self.font_large  = pygame.font.SysFont("monospace", 15, bold=True)
        self.font_msg    = pygame.font.SysFont("monospace", 12)

    # ------------------------------------------------------------------
    # Fondo de hierba
    # ------------------------------------------------------------------

    def _build_grass(self) -> pygame.Surface:
        surf = pygame.Surface((_AREA_W, WINDOW_HEIGHT))
        surf.fill(C_GRASS_DARK)
        tile = 40
        rng  = random.Random(42)

        for row in range(WINDOW_HEIGHT // tile + 1):
            for col in range(_AREA_W // tile + 1):
                if (row + col) % 2 == 0:
                    pygame.draw.rect(surf, C_GRASS_MID,
                                     (col * tile, row * tile, tile, tile))

        for _ in range(240):
            gx = rng.randint(4, _AREA_W - 4)
            gy = rng.randint(4, WINDOW_HEIGHT - 4)
            h  = rng.randint(5, 13)
            pygame.draw.line(surf, C_GRASS_LIGHT, (gx, gy), (gx, gy - h), 1)
            if rng.random() > 0.5:
                pygame.draw.line(surf, C_GRASS_LIGHT, (gx + 2, gy), (gx + 3, gy - h + 3), 1)

        return surf

    # ------------------------------------------------------------------
    # Frame principal
    # ------------------------------------------------------------------

    def draw_frame(self, creatures, selected, clock_obj, delta=0.016):
        self._pulse_t += delta
        self.screen.blit(self._grass, (0, 0))
        self._draw_area(creatures)
        self._draw_panel(selected, clock_obj, len(creatures))
        pygame.display.flip()

    # ------------------------------------------------------------------
    # Área de simulación
    # ------------------------------------------------------------------

    def _draw_area(self, creatures):
        pygame.draw.line(self.screen, C_PANEL_SEP, (_PANEL_X, 0), (_PANEL_X, WINDOW_HEIGHT), 2)

        for c in creatures:                          # sombras primero
            self._draw_shadow(c)
        for c in creatures:                          # criaturas
            self._draw_creature(c)
        for c in creatures:                          # burbujas encima
            if c.current_message:
                self._draw_bubble(c, c.current_message)

    def _draw_shadow(self, c):
        cx, cy = int(c.x), int(c.y)
        s = pygame.Surface((40, 12), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (0, 0, 0, 55), (0, 0, 40, 12))
        self.screen.blit(s, (cx - 20, cy + CREATURE_RADIUS - 4))

    # ------------------------------------------------------------------
    # Criatura
    # ------------------------------------------------------------------

    def _state(self, c) -> str:
        n = c.needs
        if n.is_critical():          return "critical"
        if n.hunger    >= 75:        return "hungry"
        if n.happiness <= 30:        return "sad"
        if n.energy    <= 25:        return "tired"
        return "normal"

    def _draw_creature(self, c):
        cx, cy   = int(c.x), int(c.y)
        state    = self._state(c)
        body_c, ear_c, leg_c, cheek_c = _STATE_COLORS[state]
        R = CREATURE_RADIUS

        # Selección
        if c.selected:
            _circle(self.screen, C_SEL_RING, cx, cy, R + 5, 2)

        # Pulso crítico
        if state == "critical":
            pulse = abs(math.sin(self._pulse_t * 3.5))
            ps = pygame.Surface((80, 80), pygame.SRCALPHA)
            _circle(ps, (*C_PULSE, int(160 * pulse)), 40, 40, R + 4 + int(pulse * 6), 2)
            self.screen.blit(ps, (cx - 40, cy - 40))

        # Orejas
        _ellipse(self.screen, ear_c,   cx - 10, cy - R - 2, 5, 7)
        _ellipse(self.screen, ear_c,   cx + 10, cy - R - 2, 5, 7)
        _ellipse(self.screen, cheek_c, cx - 10, cy - R - 3, 3, 4)
        _ellipse(self.screen, cheek_c, cx + 10, cy - R - 3, 3, 4)

        # Cuerpo
        _ellipse(self.screen, body_c, cx, cy, R, int(R * 0.88))

        # Patas
        _ellipse(self.screen, leg_c, cx - 10, cy + R - 3, 5, 4)
        _ellipse(self.screen, leg_c, cx + 10, cy + R - 3, 5, 4)

        # Cara
        self._draw_face(cx, cy, state, cheek_c)

        # Barras
        self._draw_bars(c, cx, cy)

        # Etiqueta generación
        gs = self.font_tiny.render(f"g{c.generation}", True, C_GEN_TEXT)
        gw = gs.get_width() + 6
        bg = pygame.Surface((gw, 13), pygame.SRCALPHA)
        pygame.draw.rect(bg, (*C_GEN_BG, 200), (0, 0, gw, 13), border_radius=3)
        self.screen.blit(bg, (cx - gw // 2, cy - R - 20))
        self.screen.blit(gs, (cx - gs.get_width() // 2, cy - R - 19))

    def _draw_face(self, cx, cy, state, cheek_c):
        ey   = cy - 4
        elx  = cx - 6
        erx  = cx + 6
        dark = (26, 42, 26)

        if state == "normal":
            _circle(self.screen, dark, elx, ey, 5)
            _circle(self.screen, dark, erx, ey, 5)
            _circle(self.screen, (255, 255, 255), elx - 1, ey - 2, 2)
            _circle(self.screen, (255, 255, 255), erx + 1, ey - 2, 2)
            cs = pygame.Surface((10, 6), pygame.SRCALPHA)
            pygame.draw.ellipse(cs, (*cheek_c, 130), (0, 0, 10, 6))
            self.screen.blit(cs, (cx - 15, cy + 1))
            self.screen.blit(cs, (cx + 5,  cy + 1))
            pygame.draw.arc(self.screen, dark, (cx - 5, cy + 2, 10, 7),
                            math.pi, 2 * math.pi, 2)

        elif state == "hungry":
            _ellipse(self.screen, (42, 26, 26), elx, ey - 1, 5, 6)
            _ellipse(self.screen, (42, 26, 26), erx, ey - 1, 5, 6)
            _circle(self.screen, (255, 255, 255), elx - 1, ey - 3, 2)
            _circle(self.screen, (255, 255, 255), erx + 1, ey - 3, 2)
            pygame.draw.line(self.screen, (42, 26, 26), (cx - 9, cy - 10), (cx - 3, cy - 13), 2)
            pygame.draw.line(self.screen, (42, 26, 26), (cx + 9, cy - 10), (cx + 3, cy - 13), 2)
            _ellipse(self.screen, (42, 26, 26),  cx, cy + 5, 5, 4)
            _ellipse(self.screen, (192, 96, 96), cx, cy + 6, 3, 2)
            excl = self.font_small.render("!", True, (255, 204, 68))
            self.screen.blit(excl, (cx - 3, cy - CREATURE_RADIUS - 14))

        elif state == "sad":
            _ellipse(self.screen, (26, 42, 58), elx, ey, 5, 4)
            _ellipse(self.screen, (26, 42, 58), erx, ey, 5, 4)
            pygame.draw.line(self.screen, (26, 42, 58), (cx - 11, cy - 6), (cx - 1, cy - 8), 2)
            pygame.draw.line(self.screen, (26, 42, 58), (cx + 1,  cy - 6), (cx + 11, cy - 8), 2)
            pygame.draw.arc(self.screen, (26, 42, 58),
                            (cx - 5, cy + 2, 10, 7), 0, math.pi, 2)
            _ellipse(self.screen, (160, 192, 240), cx - 8, cy + 1, 2, 3)

        elif state == "tired":
            pygame.draw.line(self.screen, (42, 42, 58), (cx - 11, cy - 3), (cx - 1, cy - 1), 3)
            pygame.draw.line(self.screen, (42, 42, 58), (cx + 1,  cy - 3), (cx + 11, cy - 1), 3)
            pygame.draw.line(self.screen, (42, 42, 58), (cx - 4,  cy + 5), (cx + 4,  cy + 5), 2)
            zz = self.font_tiny.render("zzz", True, (192, 192, 210))
            self.screen.blit(zz, (cx + 10, cy - CREATURE_RADIUS - 10))

        elif state == "critical":
            for ox in [elx, erx]:
                pygame.draw.line(self.screen, (42, 10, 10), (ox - 4, ey - 4), (ox + 4, ey + 4), 2)
                pygame.draw.line(self.screen, (42, 10, 10), (ox + 4, ey - 4), (ox - 4, ey + 4), 2)
            _ellipse(self.screen, (42, 10, 10), cx, cy + 5, 6, 5)
            excl = self.font_small.render("!!", True, (255, 170, 68))
            self.screen.blit(excl, (cx - 6, cy - CREATURE_RADIUS - 14))

    def _draw_bars(self, c, cx, cy):
        bars = [
            (c.needs.hunger,    COLOR_HUNGER_BAR,    True),
            (c.needs.hygiene,   COLOR_HYGIENE_BAR,   False),
            (c.needs.happiness, COLOR_HAPPINESS_BAR, False),
            (c.needs.energy,    COLOR_ENERGY_BAR,    False),
        ]
        bw = NEED_BAR_WIDTH
        bh = NEED_BAR_HEIGHT
        x0 = cx - bw // 2
        y0 = cy + NEED_BAR_OFFSET_Y

        for i, (val, col, inv) in enumerate(bars):
            by = y0 + i * (bh + 2)
            pygame.draw.rect(self.screen, COLOR_NEED_BAR_BG, (x0, by, bw, bh), border_radius=2)
            fill = (1.0 - val / NEED_MAX) if inv else (val / NEED_MAX)
            fw   = max(0, int(bw * fill))
            if fw:
                pygame.draw.rect(self.screen, col, (x0, by, fw, bh), border_radius=2)

    # ------------------------------------------------------------------
    # Burbuja de mensaje
    # ------------------------------------------------------------------

    def _draw_bubble(self, c, message: str):
        cx, cy  = int(c.x), int(c.y)
        pad     = 8
        max_w   = 200

        words = message.split()
        lines, cur = [], ""
        for w in words:
            test = (cur + " " + w).strip()
            if self.font_msg.size(test)[0] > max_w and cur:
                lines.append(cur); cur = w
            else:
                cur = test
        if cur:
            lines.append(cur)

        surfs = [self.font_msg.render(l, True, COLOR_MESSAGE_TEXT) for l in lines]
        if not surfs:
            return

        bw = max(s.get_width() for s in surfs) + pad * 2
        bh = sum(s.get_height() for s in surfs) + pad * 2
        bx = max(4, min(cx - bw // 2, _AREA_W - bw - 4))
        by = cy - CREATURE_RADIUS - bh - 18

        bubble = pygame.Surface((bw, bh), pygame.SRCALPHA)
        pygame.draw.rect(bubble, (*COLOR_MESSAGE_BG, 220), (0, 0, bw, bh), border_radius=6)
        pygame.draw.rect(bubble, (100, 140, 100, 180), (0, 0, bw, bh), 1, border_radius=6)
        self.screen.blit(bubble, (bx, by))

        # Cola
        tip_y = cy - CREATURE_RADIUS - 4
        pygame.draw.polygon(self.screen, (*COLOR_MESSAGE_BG, 180),
                            [(cx, tip_y), (cx - 5, by + bh - 1), (cx + 5, by + bh - 1)])

        ty = by + pad
        for s in surfs:
            self.screen.blit(s, (bx + pad, ty))
            ty += s.get_height()

    # ------------------------------------------------------------------
    # Panel UI
    # ------------------------------------------------------------------

    def _draw_panel(self, selected, clock_obj, population: int):
        pygame.draw.rect(self.screen, COLOR_UI_BG,
                         (_PANEL_X, 0, UI_PANEL_WIDTH, WINDOW_HEIGHT))
        x = _PANEL_X + 14
        y = 14

        self._txt(f"{clock_obj.time_str()}  {clock_obj.period()}", x, y, self.font_medium, C_UI_VALUE)
        y += 18
        self._txt(f"población: {population}", x, y, self.font_small, C_UI_DIM)
        y += 20
        self._hline(y); y += 10

        if selected:
            y = self._panel_selected(selected, x, y)
        else:
            self._panel_empty(x, y)

    def _panel_selected(self, c, x: int, y: int) -> int:
        self._txt(c.id, x, y, self.font_large, C_UI_VALUE)
        self._txt(f"gen {c.generation}  |  {int(c.age)}s", x, y + 18, self.font_tiny, C_UI_DIM)
        y += 38

        needs = [
            (t("ui_hunger"),    c.needs.hunger,    COLOR_HUNGER_BAR,    True),
            (t("ui_hygiene"),   c.needs.hygiene,   COLOR_HYGIENE_BAR,   False),
            (t("ui_happiness"), c.needs.happiness, COLOR_HAPPINESS_BAR, False),
            (t("ui_energy"),    c.needs.energy,    COLOR_ENERGY_BAR,    False),
        ]
        bw = UI_PANEL_WIDTH - 28
        bh = 9

        for label, val, col, inv in needs:
            self._txt(f"{label}  {val:.0f}", x, y, self.font_small, C_UI_LABEL)
            y += self.font_small.get_height() + 3
            pygame.draw.rect(self.screen, COLOR_NEED_BAR_BG, (x, y, bw, bh), border_radius=3)
            fill = (1.0 - val / NEED_MAX) if inv else (val / NEED_MAX)
            fw   = max(0, int(bw * fill))
            if fw:
                pygame.draw.rect(self.screen, col, (x, y, fw, bh), border_radius=3)
            y += bh + 10

        self._hline(y); y += 10
        self._txt(t("ui_actions"), x, y, self.font_medium, C_UI_VALUE)
        y += 18
        for action in [t("ui_feed_one"), t("ui_shower_one"), t("ui_play_one"), t("ui_sleep_one")]:
            self._txt(action, x + 4, y, self.font_small, C_UI_DIM)
            y += 15

        if c.current_message:
            self._hline(y + 4); y += 14
            self._txt(t("ui_messages"), x, y, self.font_medium, C_UI_VALUE)
            y += 16
            words = c.current_message.split()
            line, lines = "", []
            for w in words:
                test = (line + " " + w).strip()
                if self.font_small.size(test)[0] > UI_PANEL_WIDTH - 28 and line:
                    lines.append(line); line = w
                else:
                    line = test
            if line:
                lines.append(line)
            for l in lines:
                self._txt(l, x + 4, y, self.font_small, (180, 220, 180))
                y += 14

        return y

    def _panel_empty(self, x: int, y: int):
        self._txt(t("ui_no_selection"), x, y, self.font_small, C_UI_DIM)
        y += 28
        for key in ["ui_feed_all", "ui_shower_all", "ui_play_all"]:
            self._txt(t(key), x + 4, y, self.font_small, C_UI_DIM)
            y += 15

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _hline(self, y: int):
        pygame.draw.line(self.screen, C_PANEL_LINE,
                         (_PANEL_X + 8, y), (WINDOW_WIDTH - 8, y), 1)

    def _txt(self, text: str, x: int, y: int, font, color=None):
        self.screen.blit(font.render(text, True, color or COLOR_UI_TEXT), (x, y))
