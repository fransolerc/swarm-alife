# =============================================================================
# agent/inventory.py — Carrying system for resources
# =============================================================================

import logging
from typing import Optional

from agent.memory.associative_memory import AssociativeMemory
from config import CARRY_NEED_THRESHOLD, NEED_MAX

logger = logging.getLogger(__name__)


class Inventory:
    """Manages resource carrying and delivery."""

    def __init__(self, memory: AssociativeMemory):
        self._memory = memory
        self._carrying: Optional[str] = None
        self._store = None

    @property
    def is_carrying(self) -> bool:
        return self._carrying is not None

    @property
    def resource(self) -> Optional[str]:
        return self._carrying

    @property
    def target_store(self):
        return self._store

    def set_store(self, store) -> None:
        self._store = store

    def start_carrying(self, resource: str, store) -> None:
        """Start carrying a resource to a store."""
        self._carrying = resource
        self._store = store
        translations = {
            "apple": ("manzana", "recogi"),
            "gem": ("gema", "extraje"),
            "wood": ("madera", "recogi"),
        }
        if resource in translations:
            obj, verb = translations[resource]
            self._memory.add_raw(
                "yo", f"{verb}_para_almacen", obj,
                poignancy=4.0 if resource != "gem" else 6.0,
                keywords=[obj, "almacen"]
            )
            logger.info(f"Started carrying {resource} to store")

    def deliver(self) -> Optional[str]:
        """Deliver carried resource and return what was delivered."""
        if not self._carrying or not self._store:
            return None

        resource = self._carrying
        store = self._store

        if resource == "apple":
            store.deposit_apple(1)
            self._memory.add_raw("yo", "deposite", "manzana",
                                 poignancy=3.0, keywords=["manzana", "almacen"])
        elif resource == "wood":
            store.deposit_wood(1)
            self._memory.add_raw("yo", "deposite", "madera",
                                 poignancy=3.0, keywords=["madera", "almacen"])
        elif resource == "gem":
            store.deposit_gem(1)
            self._memory.add_raw("yo", "deposite", "gema",
                                 poignancy=5.0, keywords=["gema", "almacen"])

        logger.info(f"Delivered {resource} to store")
        self._carrying = None
        self._store = None
        return resource

    def cancel(self) -> None:
        """Cancel carrying."""
        self._carrying = None
        self._store = None

    @staticmethod
    def can_carry(needs) -> bool:
        """Check if needs allow carrying."""
        return (
            needs.hunger <= (NEED_MAX - CARRY_NEED_THRESHOLD)
            and needs.hygiene >= CARRY_NEED_THRESHOLD
            and needs.happiness >= CARRY_NEED_THRESHOLD
        )
