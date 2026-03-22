# =============================================================================
# render/renderer.py — swarm-alife
# Rendering Pygame. Solo dibuja, no contiene lógica de simulación.
# =============================================================================

import pygame
import logging
from typing import Optional, TYPE_CHECKING

from config import (
    WINDOW_WIDTH, WINDOW_HEIGHT, UI_PANEL_WIDTH,
    CREATURE_RADIUS, SPRITE_SIZE,
    NEED_BAR_WIDTH, NEED_BAR_HEIGHT, NEED_BAR_OFFSET_Y,
    COLOR_BG, COLOR_CREATURE, COLOR_SELECTED, COLOR_CRITICAL,
    COLOR_UI_BG, COLOR_UI_TEXT,
    COLOR_NEED_BAR_BG, COLOR_HUNGER_BAR, COLOR_HYGIENE_BAR,
    COLOR_HAPPINESS_BAR, COLOR_ENERGY_BAR,
    COLOR_MESSAGE_BG, COLOR_MESSAGE_TEXT, COLOR_FOOD_SOURCE,
    NEED_MAX,
)
from locales import t

if TYPE_CHECKING:
    from agent.creature import Creature
    from agent.memory.sim_clock import SimClock

logger = logging.getLogger(__name__)

_PANEL_X = WINDOW_WIDTH - UI_PANEL_WIDTH
_AREA_W  = WINDOW_WIDTH - UI_PANEL_WIDTH


class Renderer:
    """
    Encapsula todo el rendering Pygame.
    Se instancia después de pygame.init() y pygame.display.set_mode().
    """

    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self._init_fonts()
        logger.info("Renderer initialized")

    def _init_fonts(self) -> None:
        self.font_small  = pygame.font.SysFont("monospace", 11)
        self.font_medium = pygame.font.SysFont("monospace", 13)
        self.font_large  = pygame.font.SysFont("monospace", 16, bold=True)
        self.font_msg    = pygame.font.SysFont("monospace", 12)

    # --- Frame principal ---

    def draw_frame(
        self,
        creatures: list["Creature"],
        selected: Optional["Creature"],
        clock_obj: "SimClock",
        messages: list[tuple[str, str]],  # [(creature_id, message), ...]
    ) -> None:
        self.screen.fill(COLOR_BG)
        self._draw_simulation_area(creatures, messages)
        self._draw_ui_panel(selected, clock_obj)
        pygame.display.flip()

    # --- Área de simulación ---

    def _draw_simulation_area(
        self,
        creatures: list["Creature"],
        messages: list[tuple[str, str]],
    ) -> None:
        # Separador panel
        pygame.draw.line(
            self.screen, (60, 60, 80),
            (_PANEL_X, 0), (_PANEL_X, WINDOW_HEIGHT), 1
        )

        for creature in creatures:
            self._draw_creature(creature)

        # Mensajes flotantes sobre criaturas
        for creature in creatures:
            if creature.current_message:
                self._draw_speech_bubble(creature, creature.current_message)

    def _draw_creature(self, creature: "Creature") -> None:
        cx, cy = int(creature.x), int(creature.y)
        is_critical = creature.needs.is_critical()

        # Color base
        color = COLOR_CRITICAL if is_critical else COLOR_CREATURE
        if creature.selected:
            # Anillo de selección
            pygame.draw.circle(self.screen, COLOR_SELECTED, (cx, cy), CREATURE_RADIUS + 4, 2)

        # Cuerpo (círculo por ahora — placeholder para sprite)
        pygame.draw.circle(self.screen, color, (cx, cy), CREATURE_RADIUS)

        # ID pequeño encima
        id_surf = self.font_small.render(creature.id[-3:], True, (200, 200, 200))
        self.screen.blit(id_surf, (cx - id_surf.get_width() // 2, cy - CREATURE_RADIUS - 12))

        # Barras de necesidades debajo
        self._draw_need_bars(creature, cx, cy)

    def _draw_need_bars(self, creature: "Creature", cx: int, cy: int) -> None:
        """4 barras apiladas bajo la criatura."""
        bars = [
            (creature.needs.hunger,    COLOR_HUNGER_BAR,    True),   # True = invertida (máx = malo)
            (creature.needs.hygiene,   COLOR_HYGIENE_BAR,   False),
            (creature.needs.happiness, COLOR_HAPPINESS_BAR, False),
            (creature.needs.energy,    COLOR_ENERGY_BAR,    False),
        ]
        bw = NEED_BAR_WIDTH
        bh = NEED_BAR_HEIGHT
        x0 = cx - bw // 2
        y0 = cy + NEED_BAR_OFFSET_Y

        for i, (value, color, inverted) in enumerate(bars):
            by = y0 + i * (bh + 2)
            # Fondo
            pygame.draw.rect(self.screen, COLOR_NEED_BAR_BG, (x0, by, bw, bh))
            # Relleno
            fill = value / NEED_MAX
            if inverted:
                fill = 1.0 - fill
            fill_w = int(bw * fill)
            if fill_w > 0:
                pygame.draw.rect(self.screen, color, (x0, by, fill_w, bh))

    def _draw_speech_bubble(self, creature: "Creature", message: str) -> None:
        """Burbuja de mensaje flotante sobre la criatura."""
        cx, cy = int(creature.x), int(creature.y)
        padding = 6
        max_width = 200

        # Wrap básico
        words = message.split()
        lines = []
        current = ""
        for word in words:
            test = (current + " " + word).strip()
            surf = self.font_msg.render(test, True, COLOR_MESSAGE_TEXT)
            if surf.get_width() > max_width and current:
                lines.append(current)
                current = word
            else:
                current = test
        if current:
            lines.append(current)

        line_surfs = [self.font_msg.render(l, True, COLOR_MESSAGE_TEXT) for l in lines]
        if not line_surfs:
            return

        bw = max(s.get_width() for s in line_surfs) + padding * 2
        bh = sum(s.get_height() for s in line_surfs) + padding * 2

        bx = cx - bw // 2
        by = cy - CREATURE_RADIUS - bh - 10

        # Fondo burbuja
        bubble_rect = pygame.Rect(bx, by, bw, bh)
        pygame.draw.rect(self.screen, COLOR_MESSAGE_BG, bubble_rect, border_radius=4)
        pygame.draw.rect(self.screen, (100, 120, 100), bubble_rect, 1, border_radius=4)

        # Texto
        ty = by + padding
        for surf in line_surfs:
            self.screen.blit(surf, (bx + padding, ty))
            ty += surf.get_height()

    # --- Panel UI ---

    def _draw_ui_panel(
        self,
        selected: Optional["Creature"],
        clock_obj: "SimClock",
    ) -> None:
        panel_rect = pygame.Rect(_PANEL_X, 0, UI_PANEL_WIDTH, WINDOW_HEIGHT)
        pygame.draw.rect(self.screen, COLOR_UI_BG, panel_rect)

        x = _PANEL_X + 12
        y = 16

        # Hora simulada
        time_str = f"{t('ui_time')}: {clock_obj.time_str()} ({clock_obj.period()})"
        self._text(time_str, x, y, self.font_medium)
        y += 28

        pygame.draw.line(self.screen, (60, 60, 80), (_PANEL_X + 8, y), (WINDOW_WIDTH - 8, y))
        y += 12

        # Criatura seleccionada
        if selected:
            self._text(f"{t('ui_selected')}: {selected.id}", x, y, self.font_large)
            y += 22
            y = self._draw_needs_detail(selected, x, y)
            y += 8
            self._text(t("ui_actions"), x, y, self.font_large)
            y += 18
            for action in [
                t("ui_feed_one"), t("ui_shower_one"),
                t("ui_play_one"), t("ui_sleep_one"),
            ]:
                self._text(action, x + 4, y, self.font_small)
                y += 16
        else:
            self._text(t("ui_no_selection"), x, y, self.font_medium)
            y += 28
            self._text(t("ui_feed_all"),   x + 4, y, self.font_small); y += 16
            self._text(t("ui_shower_all"), x + 4, y, self.font_small); y += 16
            self._text(t("ui_play_all"),   x + 4, y, self.font_small); y += 16

        y += 8
        pygame.draw.line(self.screen, (60, 60, 80), (_PANEL_X + 8, y), (WINDOW_WIDTH - 8, y))
        y += 12
        self._text(t("ui_messages"), x, y, self.font_large)
        y += 20
        # Espacio reservado para log de mensajes recientes (sprint siguiente)
        self._text("—", x + 4, y, self.font_small)

    def _draw_needs_detail(self, creature: "Creature", x: int, y: int) -> int:
        """Dibuja los valores de necesidades con nombre y barra. Devuelve y final."""
        needs_data = [
            (t("ui_hunger"),    creature.needs.hunger,    COLOR_HUNGER_BAR,    True),
            (t("ui_hygiene"),   creature.needs.hygiene,   COLOR_HYGIENE_BAR,   False),
            (t("ui_happiness"), creature.needs.happiness, COLOR_HAPPINESS_BAR, False),
            (t("ui_energy"),    creature.needs.energy,    COLOR_ENERGY_BAR,    False),
        ]
        bw = UI_PANEL_WIDTH - 30
        bh = 10

        for label, value, color, inverted in needs_data:
            label_surf = self.font_small.render(f"{label}: {value:.0f}", True, COLOR_UI_TEXT)
            self.screen.blit(label_surf, (x, y))
            y += label_surf.get_height() + 2

            # Barra
            pygame.draw.rect(self.screen, COLOR_NEED_BAR_BG, (x, y, bw, bh))
            fill = value / NEED_MAX
            if inverted:
                fill = 1.0 - fill
            fill_w = int(bw * fill)
            if fill_w > 0:
                pygame.draw.rect(self.screen, color, (x, y, fill_w, bh))
            y += bh + 8

        return y

    # --- Helpers ---

    def _text(self, text: str, x: int, y: int, font: pygame.font.Font, color=None) -> None:
        surf = font.render(text, True, color or COLOR_UI_TEXT)
        self.screen.blit(surf, (x, y))
