# =============================================================================
# agent/behavior/carry_resource.py — Resource carrying behavior
# =============================================================================

import logging
from typing import TYPE_CHECKING

from agent.behavior.base import Behavior
from utils import distance

if TYPE_CHECKING:
    from agent.creature import Creature

logger = logging.getLogger(__name__)


class CarryResourceBehavior(Behavior):
    """Handles autonomous resource carrying to stores."""

    def __init__(self, creature: "Creature"):
        super().__init__(creature)

    def can_execute(self, world) -> bool:
        from agent.inventory import Inventory
        return Inventory.can_carry(self._creature.needs)

    def execute(self, delta: float, world) -> bool:
        """Execute behavior. delta kept for interface consistency."""
        creature = self._creature
        inv = creature.inventory

        if inv.is_carrying:
            return self._deliver(world)
        return self._try_pickup(world)

    def _try_pickup(self, world) -> bool:
        """Try to pick up a resource. Returns True if handled."""
        creature = self._creature
        self._store = world.nearest_store(creature.x, creature.y)

        if self._store is None:
            return False

        # Try resources in priority order
        if self._try_ground_apples(world, creature):
            return True
        if self._try_mine_gems(world, creature):
            return True
        if self._try_wood_stumps(world, creature):
            return True
        if self._try_harvest_tree(world, creature):
            return True

        return False

    def _try_ground_apples(self, world, creature) -> bool:
        """Try to pick up ground apples."""
        apple = world.nearest_apple(creature.x, creature.y)
        if apple is None:
            return False

        if not apple.in_range(creature.x, creature.y):
            creature.navigator.navigate_to(world, apple.x, apple.y)
            return True

        if not world.pick_apple_to_carry(apple):
            return False

        creature.inventory.start_carrying("apple", self._store)
        creature.navigator.clear_path()
        return True

    def _try_mine_gems(self, world, creature) -> bool:
        """Try to extract gems from mine."""
        mine = world.nearest_mine(creature.x, creature.y)
        if mine is None:
            return False
        if not mine.can_use(creature.id):
            return False

        if not mine.in_range(creature.x, creature.y):
            creature.navigator.navigate_to(world, mine.px, mine.py)
            return True

        if not mine.extract_gem(creature.id):
            return False

        creature.inventory.start_carrying("gem", self._store)
        creature.navigator.clear_path()
        return True

    def _try_wood_stumps(self, world, creature) -> bool:
        """Try to pick up wood from stumps."""
        if world.wood <= 0:
            return False

        stump = world.nearest_stump(creature.x, creature.y)
        if stump is None:
            return False

        if distance(creature.pos, stump.pos) > 60:
            creature.navigator.navigate_to(world, stump.px, stump.py)
            return True

        world.wood -= 1
        creature.inventory.start_carrying("wood", self._store)
        creature.navigator.clear_path()
        return True

    def _try_harvest_tree(self, world, creature) -> bool:
        """Try to harvest apple from tree."""
        tree = world.nearest_shakeable_tree(creature.x, creature.y)
        if tree is None:
            return False

        if not tree.in_shake_range(creature.x, creature.y):
            creature.navigator.navigate_to(world, tree.px, tree.py)
            return True

        if not world.harvest_from_tree(tree.px, tree.py):
            return False

        creature.inventory.start_carrying("apple", self._store)
        creature.navigator.clear_path()
        return True

    def _deliver(self, world) -> bool:
        """Deliver carried resource to store."""
        creature = self._creature
        store = creature.inventory.target_store or world.nearest_store(creature.x, creature.y)

        if store is None:
            creature.inventory.cancel()
            return False

        if store.in_range(creature.x, creature.y):
            creature.inventory.deliver()
            return False

        creature.navigator.navigate_to(world, store.px, store.py)
        return True

    def reset(self) -> None:
        self._creature.inventory.cancel()
