# =============================================================================
# core/persistence.py — Game state persistence
# =============================================================================

import os
import logging

from config import DATA_DIR, WINDOW_WIDTH
from utils import atomic_write_json, load_json

logger = logging.getLogger(__name__)

_AREA_W = None  # Will be set from config
_WORLD_FILE = "data/world.json"
_COLONY_FILE = "data/colony.json"


def setup_paths() -> None:
    """Initialize paths from config."""
    global _AREA_W, _WORLD_FILE, _COLONY_FILE
    _AREA_W = WINDOW_WIDTH
    _WORLD_FILE = os.path.join(DATA_DIR, "world.json")
    _COLONY_FILE = os.path.join(DATA_DIR, "colony.json")


# --- ID Generation ---

_id_counter = 0


def next_id() -> str:
    """Generate next creature ID."""
    global _id_counter
    cid = f"sw{_id_counter:03d}"
    _id_counter += 1
    return cid


def seed_id_counter(ids: list[str]) -> None:
    """Seed counter from existing IDs."""
    global _id_counter
    for cid in ids:
        if cid.startswith("sw"):
            try:
                n = int(cid[2:])
                _id_counter = max(_id_counter, n + 1)
            except ValueError:
                pass


# --- Creature Persistence ---

def save_colony(creatures: list) -> None:
    """Save creature IDs."""
    os.makedirs(DATA_DIR, exist_ok=True)
    atomic_write_json(_COLONY_FILE, [c.id for c in creatures])


def load_colony(creature_class, num_creatures: int) -> list:
    """Load or create creature colony."""
    ids = load_json(_COLONY_FILE, default=[])

    if not ids:
        creatures = []
        for _ in range(num_creatures):
            cid = next_id()
            c = creature_class(cid)
            c.load()
            creatures.append(c)
        logger.info(f"New colony started: {len(creatures)} creature(s)")
        return creatures

    seed_id_counter(ids)
    creatures = []
    for cid in ids:
        c = creature_class(cid)
        loaded = c.load()
        if not loaded:
            logger.warning(f"No save data for {cid}, using defaults")
        creatures.append(c)

    logger.info(f"Colony restored: {len(creatures)} creature(s)")
    return creatures


# --- World Persistence ---

def save_world(world) -> None:
    """Save world state."""
    os.makedirs(DATA_DIR, exist_ok=True)
    atomic_write_json(_WORLD_FILE, world.to_dict())


def load_world(world_class, gem_count: int):
    """Load or create world."""
    world = world_class()
    data = load_json(_WORLD_FILE, default=None)
    if data:
        world.from_dict(data)
        logger.info(f"World loaded: {len(world)} objects, {len(world.deposits())} deposits")
    else:
        world.generate_deposits(gem_count)
        logger.info(f"New world: {len(world.deposits())} deposits generated")
    return world
