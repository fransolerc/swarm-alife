# =============================================================================
# core/input_handler.py — Input handling
# =============================================================================

import pygame
import logging
from typing import TYPE_CHECKING

from config import CREATURE_RADIUS
from utils import load_json
from core.persistence import save_colony, save_world
from world.placement import ToolMode

if TYPE_CHECKING:
    from agent.creature import Creature

logger = logging.getLogger(__name__)


def find_creature_at(creatures: list, mx: int, my: int) -> "Creature | None":
    """Find creature at mouse position."""
    for c in creatures:
        dx, dy = c.x - mx, c.y - my
        if (dx * dx + dy * dy) <= (CREATURE_RADIUS + 6) ** 2:
            return c
    return None


class InputHandler:
    """Handles all game input."""

    def __init__(self, area_w: int, world_h: int):
        self.area_w = area_w
        self.world_h = world_h
        self.selected = None
        self.show_diary = False
        self.diary_entries = []
        self.quit_requested = False

    def is_in_world(self, mx: int, my: int) -> bool:
        return mx < self.area_w and my < self.world_h

    def handle_event(
        self,
        event: pygame.event.Event,
        creatures: list,
        world,
        placement,
        diary_file: str
    ) -> None:
        if event.type == pygame.QUIT:
            self.quit_requested = True
        elif event.type == pygame.KEYDOWN:
            self._handle_keydown(event, creatures, world, diary_file)
        elif event.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
            self._handle_mouse(event, creatures, world, placement)

    def _handle_keydown(self, event: pygame.event.Event, creatures: list, world, diary_file: str) -> None:
        if event.key == pygame.K_ESCAPE:
            self.quit_requested = True
            return

        if event.key == pygame.K_TAB:
            self.show_diary = not self.show_diary
            if self.show_diary:
                self.diary_entries = load_json(diary_file, default=[])
            return

        targets = [self.selected] if self.selected else creatures
        self._apply_action_key(event.key, targets, creatures, world)

    def _apply_action_key(self, key: int, targets: list, creatures: list, world) -> None:
        if key == pygame.K_f:
            for c in targets:
                c.feed()
        elif key == pygame.K_d:
            for c in targets:
                c.shower()
        elif key == pygame.K_j:
            for c in targets:
                c.play()
        elif key == pygame.K_g:
            for c in creatures:
                c.save()
            save_world(world)
            save_colony(creatures)
            logger.info("State saved manually")

    def _handle_mouse(self, event: pygame.event.Event, creatures: list, world, placement) -> None:
        mx, my = event.pos
        in_area = self.is_in_world(mx, my)

        if event.type == pygame.MOUSEMOTION:
            if in_area:
                placement.on_mouse_move(mx, my)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            self._handle_button_down(event, mx, my, in_area, creatures, world, placement)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            placement.on_mouse_up()

    def _handle_button_down(
        self,
        event: pygame.event.Event,
        mx: int,
        my: int,
        in_area: bool,
        creatures: list,
        world,
        placement
    ) -> None:
        if event.button == 1:
            if placement.on_mouse_down(mx, my):
                return
            if in_area:
                self.selected = self._handle_left_click(mx, my, creatures, world, placement)
        elif event.button == 3 and in_area:
            placement.on_right_click(mx, my)

    def _handle_left_click(self, mx: int, my: int, creatures: list, world, placement) -> "Creature | None":

        clicked = find_creature_at(creatures, mx, my)
        if clicked:
            if self.selected:
                self.selected.selected = False
            clicked.selected = True
            return clicked

        if placement.tool == ToolMode.AXE:
            world.chop_tree_at(mx, my)
            return self.selected

        if self.selected:
            self.selected.selected = False
        return None
