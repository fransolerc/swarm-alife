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
    NUM_CREATURES, CREATURE_RADIUS, DATA_DIR,
    TOOLBAR_HEIGHT, DIARY_FILE, GEM_DEPOSIT_COUNT,
)
from agent.creature import Creature
from agent.social import update_social
from agent.communication import trigger_llm_message
from agent.memory.sim_clock import SimClock
from world.objects import WorldMap
from world.placement import PlacementMode, ToolMode
from render.renderer import Renderer

logger = logging.getLogger(__name__)

_AREA_W        = WINDOW_WIDTH
_WORLD_H       = WINDOW_HEIGHT - TOOLBAR_HEIGHT
_WORLD_FILE    = os.path.join(DATA_DIR, "world.json")
_COLONY_FILE   = os.path.join(DATA_DIR, "colony.json")
_id_counter    = 0


def _next_id() -> str:
    global _id_counter
    cid = f"sw{_id_counter:03d}"
    _id_counter += 1
    return cid


def _seed_id_counter(ids: list[str]) -> None:
    global _id_counter
    for cid in ids:
        if cid.startswith("sw"):
            try:
                n = int(cid[2:])
                _id_counter = max(_id_counter, n + 1)
            except ValueError:
                pass


# ---------------------------------------------------------------
# Persistencia de criaturas
# ---------------------------------------------------------------

def save_colony(creatures: list[Creature]) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    atomic_write_json(_COLONY_FILE, [c.id for c in creatures])


def load_colony() -> list[Creature]:
    ids = load_json(_COLONY_FILE, default=[])

    if not ids:
        creatures = []
        for _ in range(NUM_CREATURES):
            cid = _next_id()
            c = Creature(cid)
            c.load()
            creatures.append(c)
        logger.info(f"New colony started: {len(creatures)} creature(s)")
        return creatures

    _seed_id_counter(ids)
    creatures = []
    for cid in ids:
        c = Creature(cid)
        loaded = c.load()
        if not loaded:
            logger.warning(f"No save data for {cid}, using defaults")
        creatures.append(c)

    logger.info(f"Colony restored: {len(creatures)} creature(s)")
    return creatures


def save_world(world: WorldMap) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    atomic_write_json(_WORLD_FILE, world.to_dict())


def load_world(world: WorldMap) -> None:
    data = load_json(_WORLD_FILE, default=None)
    if data:
        world.from_dict(data)
        logger.info(f"World loaded: {len(world)} objects, {len(world.deposits())} deposits")
    else:
        # Mundo nuevo: generar yacimientos
        world.generate_deposits(GEM_DEPOSIT_COUNT)
        logger.info(f"New world: {len(world.deposits())} deposits generated")


# ---------------------------------------------------------------
# Input helpers
# ---------------------------------------------------------------

def find_creature_at(creatures: list[Creature], mx: int, my: int) -> Creature | None:
    for c in creatures:
        dx, dy = c.x - mx, c.y - my
        if (dx * dx + dy * dy) <= (CREATURE_RADIUS + 6) ** 2:
            return c
    return None


def _apply_action_key(
    key: int,
    targets: list[Creature],
    selected: Creature | None,
    creatures: list[Creature],
    world: WorldMap,
) -> None:
    if key == pygame.K_f:
        for c in targets: c.feed()
    elif key == pygame.K_d:
        for c in targets: c.shower()
    elif key == pygame.K_j:
        for c in targets: c.play()
    elif key == pygame.K_s:
        if selected: selected.sleep()
    elif key == pygame.K_g:
        for c in creatures: c.save()
        save_world(world)
        save_colony(creatures)
        logger.info("State saved manually")


def _handle_keydown(
    event: pygame.event.Event,
    creatures: list[Creature],
    selected: Creature | None,
    world: WorldMap,
    show_diary: bool,
    diary_entries: list,
) -> tuple[bool, bool, list]:
    """
    Devuelve (quit, nuevo_show_diary, nuevas_diary_entries).
    Tab alterna el overlay del diario y carga las entradas al abrir.
    """
    if event.key == pygame.K_ESCAPE:
        return True, show_diary, diary_entries

    if event.key == pygame.K_TAB:
        new_show = not show_diary
        new_entries = load_json(DIARY_FILE, default=[]) if new_show else diary_entries
        return False, new_show, new_entries

    targets = [selected] if selected else creatures
    _apply_action_key(event.key, targets, selected, creatures, world)
    return False, show_diary, diary_entries


def _handle_left_click(
    mx: int,
    my: int,
    creatures: list[Creature],
    selected: Creature | None,
    placement: PlacementMode,
    world: WorldMap,
) -> Creature | None:
    clicked = find_creature_at(creatures, mx, my)
    if clicked:
        if selected: selected.selected = False
        clicked.selected = True
        return clicked

    if placement.tool == ToolMode.AXE:
        world.chop_tree_at(mx, my)
        return selected

    if selected:
        selected.selected = False
    return None


def _handle_button_down(
    event: pygame.event.Event,
    mx: int,
    my: int,
    in_area: bool,
    creatures: list[Creature],
    selected: Creature | None,
    placement: PlacementMode,
    world: WorldMap,
) -> Creature | None:
    if event.button == 1:
        if placement.on_mouse_down(mx, my):
            return selected
        if in_area:
            return _handle_left_click(mx, my, creatures, selected, placement, world)
    if event.button == 3 and in_area:
        placement.on_right_click(mx, my)
    return selected


def _handle_mouse_event(
    event: pygame.event.Event,
    creatures: list[Creature],
    selected: Creature | None,
    placement: PlacementMode,
    world: WorldMap,
) -> Creature | None:
    mx, my   = event.pos
    in_area  = mx < _AREA_W and my < _WORLD_H

    if event.type == pygame.MOUSEMOTION:
        if in_area:
            placement.on_mouse_move(mx, my)
        return selected

    if event.type == pygame.MOUSEBUTTONDOWN:
        return _handle_button_down(event, mx, my, in_area, creatures, selected, placement, world)

    if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
        placement.on_mouse_up()

    return selected


# ---------------------------------------------------------------
# Update
# ---------------------------------------------------------------

def _update(
    creatures: list[Creature],
    pending_spawn: list[Creature],
    sim_clock: SimClock,
    world: WorldMap,
    delta: float,
) -> None:
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


# ---------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------

def main() -> None:
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption(WINDOW_TITLE)
    clock = pygame.time.Clock()

    creatures     = load_colony()
    sim_clock     = SimClock(start_hour=8.0)
    world         = WorldMap()
    placement     = PlacementMode(world)
    renderer      = Renderer(screen)
    selected: Creature | None = None
    pending_spawn: list[Creature] = []

    show_diary:    bool = False
    diary_entries: list = []

    load_world(world)
    logger.info(f"swarm-alife started — {len(creatures)} creature(s), {len(world)} object(s), "
                f"{len(world.deposits())} deposits")

    running = True
    while running:
        delta = clock.tick(FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                quit_, show_diary, diary_entries = _handle_keydown(
                    event, creatures, selected, world, show_diary, diary_entries
                )
                if quit_:
                    running = False
            elif event.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
                selected = _handle_mouse_event(event, creatures, selected, placement, world)

        _update(creatures, pending_spawn, sim_clock, world, delta)

        renderer.draw_frame(
            creatures=creatures,
            selected=selected,
            clock_obj=sim_clock,
            world=world,
            placement=placement,
            delta=delta,
            show_diary=show_diary,
            diary_entries=diary_entries,
        )

    logger.info(f"Shutting down. Population: {len(creatures)}")
    for c in creatures: c.save()
    save_world(world)
    save_colony(creatures)
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
