# =============================================================================
# agent/behavior/seek_food.py — Food seeking behavior (refactored)
# =============================================================================

import logging
from typing import TYPE_CHECKING, Callable
from dataclasses import dataclass

from agent.behavior.base import Behavior
from config import APPLE_HUNGER_VALUE, OBJ_USE_DURATION

if TYPE_CHECKING:
    from agent.creature import Creature

logger = logging.getLogger(__name__)


@dataclass
class FoodSource:
    """A potential food source with its handler functions."""
    name: str
    can_consume: bool
    navigate: Callable
    consume: Callable


class SeekFoodBehavior(Behavior):
    """Handles food seeking: store -> ground apples -> trees."""

    def __init__(self, creature: "Creature"):
        super().__init__(creature)
        self._target = None
        self._shake_target = None
        self._phase = "initial"
        self._use_timer = 0.0

    def can_execute(self, world) -> bool:
        return True

    def execute(self, delta: float, world) -> bool:
        """Execute food seeking behavior."""
        creature = self._creature

        if self._phase == "using":
            return self._continue_using(delta)

        self._shake_target = None

        # Try food sources in priority order
        if self._try_store_apples(world, creature):
            return True
        if self._try_ground_apples(world, creature):
            return True
        if self._try_tree(world, creature):
            return True

        return False

    def _continue_using(self, delta: float) -> bool:
        """Handle ongoing object use."""
        creature = self._creature
        self._use_timer += delta

        duration = OBJ_USE_DURATION.get(self._target.type.name, 3.0) if self._target else 3.0
        if self._use_timer < duration:
            creature.navigator.clear_path()
            return True

        self._release_target()
        self._phase = "done"
        return False

    def _try_store_apples(self, world, creature) -> bool:
        """Try to eat from store. Returns True if handled."""
        store = world.nearest_store_with_apples(creature.x, creature.y)
        if store is None:
            return False

        if not store.in_range(creature.x, creature.y):
            creature.navigator.navigate_to(world, store.px, store.py)
            return True

        if not store.take_apple():
            return False

        self._consume_apple("almacen", "manzana_almacen", ["manzana", "hambre", "almacen"])
        return True

    def _try_ground_apples(self, world, creature) -> bool:
        """Try to eat ground apples. Returns True if handled."""
        apple = world.nearest_apple(creature.x, creature.y)
        if apple is None:
            return False

        if not apple.in_range(creature.x, creature.y):
            creature.navigator.navigate_to(world, apple.x, apple.y)
            return True

        world.pick_apple(apple, creature.needs)
        self._consume_apple("suelo", "manzana", ["manzana", "hambre"])
        return True

    def _try_tree(self, world, creature) -> bool:
        """Try to eat from tree. Returns True if handled."""
        tree = world.nearest_shakeable_tree(creature.x, creature.y)
        if tree is None:
            return False

        self._shake_target = tree

        if not tree.in_shake_range(creature.x, creature.y):
            creature.navigator.navigate_to(world, tree.px, tree.py)
            return True

        success = world.eat_from_tree(tree.px, tree.py, creature.needs)
        self._shake_target = None

        if success:
            self._consume_apple("arbol", "manzana", ["arbol", "manzana", "hambre"])

        return True

    def _consume_apple(self, location: str, obj: str, keywords: list) -> None:
        """Record apple consumption and update state."""
        creature = self._creature
        creature.needs.feed_amount(APPLE_HUNGER_VALUE)
        creature.memory.add_raw("yo", "comi", obj, poignancy=5.0, keywords=keywords)
        logger.debug(f"{creature.id}: ate apple from {location}")
        self._phase = "done"

    def reset(self) -> None:
        self._release_target()
        self._phase = "initial"
        self._use_timer = 0.0

    def _release_target(self) -> None:
        if self._target is not None:
            self._target.release(self._creature.id)
        self._target = None
        self._phase = "initial"

    @property
    def shake_target(self):
        return self._shake_target
