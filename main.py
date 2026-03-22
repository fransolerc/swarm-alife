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


def make_creatures(n: int) -> list[Creature]:
    """Crea N criaturas con IDs únicos. Intenta cargar estado persistente."""
    creatures = []
    for i in range(n):
        cid = f"sw{i:02d}"
        c = Creature(cid)
        c.load()  # no-op si no existe fichero guardado
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

    creatures = make_creatures(NUM_CREATURES)
    sim_clock = SimClock(start_hour=8.0)
    renderer  = Renderer(screen)
    selected: Creature | None = None

    logger.info(f"swarm-alife started with {len(creatures)} creatures")

    running = True
    while running:
        delta = clock.tick(FPS) / 1000.0  # segundos reales del último frame

        # --- Input ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

                # Acciones globales (todas las criaturas)
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

                # Guardar estado
                elif event.key == pygame.K_g:
                    for c in creatures:
                        c.save()
                    logger.info("State saved manually")

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # clic izquierdo
                    mx, my = event.pos
                    if mx < _AREA_W:  # dentro del área de simulación
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
            triggered_need = creature.update(delta, is_night=is_night)
            if triggered_need:
                trigger_llm_message(creature, triggered_need)

        update_social(creatures, delta)

        # --- Render ---
        renderer.draw_frame(
            creatures=creatures,
            selected=selected,
            clock_obj=sim_clock,
            messages=[],  # placeholder para log global de mensajes
        )

    # --- Shutdown ---
    logger.info("Shutting down, saving state...")
    for c in creatures:
        c.save()
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
