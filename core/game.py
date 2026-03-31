# =============================================================================
# core/game.py — Main game loop and logic
# =============================================================================

import logging
import pygame

from agent.social import update_social, update_conversations
from agent.communication import trigger_llm_message
from agent.memory.sim_clock import SimClock
from world.objects import WorldMap
from world.placement import PlacementMode
from core.input_handler import InputHandler
from core.persistence import save_colony, save_world, load_colony, load_world, next_id, setup_paths
from render.renderer import Renderer

from config import (
    FPS, WINDOW_WIDTH, WINDOW_HEIGHT,
    NUM_CREATURES, TOOLBAR_HEIGHT, DIARY_FILE, GEM_DEPOSIT_COUNT,
)

logger = logging.getLogger(__name__)

_AREA_W = WINDOW_WIDTH
_WORLD_H = WINDOW_HEIGHT - TOOLBAR_HEIGHT


class Game:
    """Main game controller."""

    def __init__(self, screen, creature_class):
        self.screen = screen
        self.creature_class = creature_class
        self.running = True

        # Setup paths first
        setup_paths()

        # Initialize systems
        self.creatures = load_colony(creature_class, NUM_CREATURES)
        self.sim_clock = SimClock(start_hour=8.0)
        self.world = load_world(WorldMap, GEM_DEPOSIT_COUNT)
        self.placement = PlacementMode(self.world)
        self.renderer = Renderer(screen)
        self.input = InputHandler(_AREA_W, _WORLD_H)
        self.pending_spawn = []

        logger.info(
            f"swarm-alife started — {len(self.creatures)} creature(s), "
            f"{len(self.world)} object(s), {len(self.world.deposits())} deposits"
        )

    def handle_event(self, event: pygame.event.Event) -> None:
        """Process single event."""
        self.input.handle_event(
            event,
            self.creatures,
            self.world,
            self.placement,
            DIARY_FILE
        )
        if self.input.quit_requested:
            self.running = False

    def update(self, delta: float) -> None:
        """Update game state."""
        self.sim_clock.update(delta)
        self.world.update(delta)
        
        # Identificar criatura seleccionada para prioridad LLM
        selected_creature = self.input.selected

        for creature in self.creatures:
            signal = creature.update(delta, world=self.world, selected_creature=selected_creature)
            if signal == "reproduce":
                self.pending_spawn.append(creature.spawn_offspring(next_id()))
            elif signal is not None:
                # Solo llamar LLM si está seleccionada o pasa el rate limit
                is_selected = (selected_creature == creature)
                trigger_llm_message(creature, signal, is_selected=is_selected)

        if self.pending_spawn:
            self.creatures.extend(self.pending_spawn)
            self.pending_spawn.clear()

        update_social(self.creatures, delta, self.world)
        update_conversations(self.creatures, delta)

    def render(self, delta: float) -> None:
        """Render frame."""
        self.renderer.draw_frame(
            creatures=self.creatures,
            selected=self.input.selected,
            clock_obj=self.sim_clock,
            world=self.world,
            placement=self.placement,
            delta=delta,
            show_diary=self.input.show_diary,
            diary_entries=self.input.diary_entries,
        )

    def shutdown(self) -> None:
        """Save state and cleanup."""
        logger.info(f"Shutting down. Population: {len(self.creatures)}")
        for c in self.creatures:
            c.save()
        save_world(self.world)
        save_colony(self.creatures)

    def run(self) -> None:
        """Main game loop."""
        clock = pygame.time.Clock()

        while self.running:
            delta = clock.tick(FPS) / 1000.0

            for event in pygame.event.get():
                self.handle_event(event)

            self.update(delta)
            self.render(delta)

        self.shutdown()
