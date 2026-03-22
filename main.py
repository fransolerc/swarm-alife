# =============================================================================
# main.py — swarm-alife
# Entry point. Loop principal Pygame: input → update → render.
# =============================================================================

import sys
import logging
import pygame

from utils import setup_logging
setup_logging()

from config import (
    FPS, WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_TITLE,
    NUM_CREATURES, UI_PANEL_WIDTH, CREATURE_RADIUS,
)
from agent.creature import Creature
from agent.social import update_social
from agent.communication import trigger_llm_message
from agent.memory.sim_clock import SimClock
from render.renderer import Renderer

logger = logging.getLogger(__name__)

_AREA_W = WINDOW_WIDTH - UI_PANEL_WIDTH

# Contador global para IDs únicos de criaturas generadas en runtime
_id_counter = 0


def _next_id() -> str:
    global _id_counter
    cid = f"sw{_id_counter:03d}"
    _id_counter += 1
    return cid


def make_initial_creatures() -> list[Creature]:
    """Crea las criaturas iniciales. Intenta cargar estado persistente."""
    creatures = []
    for _ in range(NUM_CREATURES):
        cid = _next_id()
        c = Creature(cid)
        c.load()
        creatures.append(c)
    return creatures


def find_creature_at(creatures: list[Creature], mx: int, my: int) -> Creature | None:
    """Devuelve la criatura bajo el cursor, o None."""
    for c in creatures:
        dx = c.x - mx
        dy = c.y - my
        if (dx * dx + dy * dy) <= (CREATURE_RADIUS + 6) ** 2:
            return c
    return None


def main() -> None:
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption(WINDOW_TITLE)
    clock = pygame.time.Clock()

    creatures = make_initial_creatures()
    sim_clock = SimClock(start_hour=8.0)
    renderer  = Renderer(screen)
    selected: Creature | None = None

    # Cola de criaturas a añadir (evita modificar la lista durante la iteración)
    pending_spawn: list[Creature] = []

    logger.info(f"swarm-alife started with {len(creatures)} creature(s)")

    running = True
    while running:
        delta = clock.tick(FPS) / 1000.0

        # --- Input ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

                elif event.key == pygame.K_f:
                    targets = [selected] if selected else creatures
                    for c in targets: c.feed()

                elif event.key == pygame.K_d:
                    targets = [selected] if selected else creatures
                    for c in targets: c.shower()

                elif event.key == pygame.K_j:
                    targets = [selected] if selected else creatures
                    for c in targets: c.play()

                elif event.key == pygame.K_s:
                    if selected:
                        selected.sleep()

                elif event.key == pygame.K_g:
                    for c in creatures:
                        c.save()
                    logger.info("State saved manually")

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    mx, my = event.pos
                    if mx < _AREA_W:
                        clicked = find_creature_at(creatures, mx, my)
                        if selected:
                            selected.selected = False
                        selected = clicked
                        if selected:
                            selected.selected = True

        # --- Update ---
        sim_clock.update(delta)
        is_night = sim_clock.is_night()

        for creature in creatures:
            signal = creature.update(delta, is_night=is_night)

            if signal == "reproduce":
                offspring = creature.spawn_offspring(_next_id())
                pending_spawn.append(offspring)
                logger.info(
                    f"Population: {len(creatures) + len(pending_spawn)} "
                    f"(+1 from {creature.id})"
                )
            elif signal is not None:
                trigger_llm_message(creature, signal)

        # Incorporar crías al swarm tras el loop de update
        if pending_spawn:
            creatures.extend(pending_spawn)
            pending_spawn.clear()

        update_social(creatures, delta)

        # --- Render ---
        renderer.draw_frame(
            creatures=creatures,
            selected=selected,
            clock_obj=sim_clock,
            delta=delta,
        )

    # --- Shutdown ---
    logger.info(f"Shutting down. Final population: {len(creatures)}")
    for c in creatures:
        c.save()
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()

