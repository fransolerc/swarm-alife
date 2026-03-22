# =============================================================================
# main.py — swarm-alife
# =============================================================================

import sys
import logging
import os
import pygame

from utils import setup_logging, atomic_write_json, load_json
setup_logging()

from config import (
    FPS, WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_TITLE,
    NUM_CREATURES, UI_PANEL_WIDTH, CREATURE_RADIUS, DATA_DIR, GRID_CELL,
)
from agent.creature import Creature
from agent.social import update_social
from agent.communication import trigger_llm_message
from agent.memory.sim_clock import SimClock
from world.objects import WorldMap, ObjType
from world.placement import PlacementMode, PALETTE
from render.renderer import Renderer

logger = logging.getLogger(__name__)

_AREA_W     = WINDOW_WIDTH - UI_PANEL_WIDTH
_WORLD_FILE = os.path.join(DATA_DIR, "world.json")

_id_counter = 0

def _next_id() -> str:
    global _id_counter
    cid = f"sw{_id_counter:03d}"
    _id_counter += 1
    return cid


def make_initial_creatures() -> list[Creature]:
    creatures = []
    for _ in range(NUM_CREATURES):
        cid = _next_id()
        c = Creature(cid)
        c.load()
        creatures.append(c)
    return creatures


def save_world(world: WorldMap) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    atomic_write_json(_WORLD_FILE, world.to_list())


def load_world(world: WorldMap) -> None:
    data = load_json(_WORLD_FILE, default=[])
    if data:
        world.from_list(data)
        logger.info(f"World loaded: {len(world)} objects")


def find_creature_at(creatures: list[Creature], mx: int, my: int) -> Creature | None:
    for c in creatures:
        dx = c.x - mx
        dy = c.y - my
        if (dx*dx + dy*dy) <= (CREATURE_RADIUS + 6) ** 2:
            return c
    return None


def main() -> None:
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption(WINDOW_TITLE)
    clock = pygame.time.Clock()

    creatures     = make_initial_creatures()
    sim_clock     = SimClock(start_hour=8.0)
    world         = WorldMap()
    placement     = PlacementMode(world)
    renderer      = Renderer(screen)
    selected: Creature | None = None
    pending_spawn: list[Creature] = []

    load_world(world)
    logger.info(f"swarm-alife — {len(creatures)} criatura(s), {len(world)} objeto(s)")

    running = True
    while running:
        delta = clock.tick(FPS) / 1000.0

        # ----------------------------------------------------------------
        # Input
        # ----------------------------------------------------------------
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

                # Teclas 1-5: seleccionar objeto de paleta
                elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3,
                                   pygame.K_4, pygame.K_5):
                    placement.select_by_index(event.key - pygame.K_1)

                # Acciones sobre criaturas
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
                    if selected: selected.sleep()

                # Guardar
                elif event.key == pygame.K_g:
                    for c in creatures: c.save()
                    save_world(world)
                    logger.info("Guardado manual")

            elif event.type == pygame.MOUSEMOTION:
                mx, my = event.pos
                if mx < _AREA_W:
                    placement.on_mouse_move(mx, my)

            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos
                in_area = mx < _AREA_W

                if event.button == 1 and in_area:
                    # Prioridad 1: clic en criatura → seleccionar
                    clicked_creature = find_creature_at(creatures, mx, my)
                    if clicked_creature:
                        if selected: selected.selected = False
                        selected = clicked_creature
                        selected.selected = True

                    # Prioridad 2: clic en árbol → zarandear
                    elif world.get_at_px(mx, my) and \
                         world.get_at_px(mx, my).type == ObjType.TREE:
                        world.shake_tree_at(mx, my)

                    # Prioridad 3: colocar objeto si hay uno seleccionado
                    elif placement.selected is not None:
                        placement.on_left_click(mx, my)

                    # Prioridad 4: deseleccionar criatura
                    else:
                        if selected:
                            selected.selected = False
                            selected = None

                elif event.button == 3 and in_area:
                    # Clic derecho: borrar objeto
                    placement.on_right_click(mx, my)

        # ----------------------------------------------------------------
        # Update
        # ----------------------------------------------------------------
        sim_clock.update(delta)
        world.update(delta)

        for creature in creatures:
            signal = creature.update(delta, is_night=sim_clock.is_night(), world=world)
            if signal == "reproduce":
                pending_spawn.append(creature.spawn_offspring(_next_id()))
            elif signal is not None:
                trigger_llm_message(creature, signal)

        if pending_spawn:
            creatures.extend(pending_spawn)
            pending_spawn.clear()

        update_social(creatures, delta)

        # ----------------------------------------------------------------
        # Render
        # ----------------------------------------------------------------
        renderer.draw_frame(
            creatures=creatures,
            selected=selected,
            clock_obj=sim_clock,
            world=world,
            placement=placement,
            delta=delta,
        )

    # ----------------------------------------------------------------
    # Shutdown
    # ----------------------------------------------------------------
    logger.info(f"Cerrando. Población: {len(creatures)}")
    for c in creatures: c.save()
    save_world(world)
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
