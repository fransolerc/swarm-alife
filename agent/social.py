# =============================================================================
# agent/social.py — swarm-alife
# Comportamiento social emergente + conversaciones
# =============================================================================

import logging
import random
import time
from typing import TYPE_CHECKING

from config import (
    HUNGER_CRITICAL,
    CONVERSATIONS_ENABLED, CONVERSATION_CHANCE,
    CONVERSATION_MIN_HAPPINESS, CONVERSATION_MAX_HUNGER,
    CONVERSATION_COOLDOWN, CONVERSATION_GEM_COST, CONVERSATION_DURATION
)

if TYPE_CHECKING:
    from agent.creature import Creature

logger = logging.getLogger(__name__)


def update_social(creatures: list["Creature"], delta: float, world=None) -> None:
    _proximity_effects(creatures, delta)
    _try_conversations(creatures, world)


def _proximity_effects(creatures: list["Creature"], delta: float) -> None:
    pairs = _get_nearby_pairs(creatures)
    for c, neighbors in pairs.items():
        if not neighbors:
            continue
        c.needs.apply_proximity_bonus(delta)
        hungry_count = sum(1 for n in neighbors if n.needs.hunger >= HUNGER_CRITICAL)
        for _ in range(hungry_count):
            c.needs.apply_hunger_contagion(delta)


def _get_nearby_pairs(creatures: list["Creature"]) -> dict["Creature", list["Creature"]]:
    n = len(creatures)
    pairs = {c: [] for c in creatures}
    for i in range(n):
        c1 = creatures[i]
        for j in range(i + 1, n):
            c2 = creatures[j]
            if c1.is_near(c2):
                pairs[c1].append(c2)
                pairs[c2].append(c1)
    return pairs


def _try_conversations(creatures: list["Creature"], world) -> None:
    if not CONVERSATIONS_ENABLED or world is None:
        return

    available = _get_available_creatures(creatures)
    if len(available) < 2:
        return

    paired = set()
    for c1 in available:
        if c1.id in paired:
            continue
        c2 = _find_conversation_partner(c1, available, paired, world)
        if c2 is None:
            continue
        _start_conversation(c1, c2, world, time.time())
        paired.add(c1.id)
        paired.add(c2.id)


def _get_available_creatures(creatures: list["Creature"]) -> list["Creature"]:
    now = time.time()
    return [
        c for c in creatures
        if _can_converse(c, now) and not c.in_conversation
    ]


def _find_conversation_partner(
        c1: "Creature",
        available: list["Creature"],
        paired: set,
        world
) -> "Creature | None":
    if random.random() > CONVERSATION_CHANCE:
        return None

    candidates = [
        c2 for c2 in available
        if c2.id not in paired
           and c2.id != c1.id
           and c1.is_near(c2)
           and not c2.in_conversation
    ]
    if not candidates:
        return None

    c2 = random.choice(candidates)
    store = world.nearest_store(c1.x, c1.y)
    if store is None or store.stored_gems < CONVERSATION_GEM_COST * 2:
        return None

    return c2


def _start_conversation(c1: "Creature", c2: "Creature", world, now: float) -> None:
    store = world.nearest_store(c1.x, c1.y)
    if store is None:
        return

    store.stored_gems -= CONVERSATION_GEM_COST * 2

    c1.in_conversation = True
    c2.in_conversation = True
    c1.conversation_partner = c2
    c2.conversation_partner = c1
    c1.conversation_timer = 0.0
    c2.conversation_timer = 0.0
    c1.conversation_end_time = now + CONVERSATION_DURATION
    c2.conversation_end_time = now + CONVERSATION_DURATION

    c1.set_message("💬 ...", duration=CONVERSATION_DURATION)
    c2.set_message("💬 ...", duration=CONVERSATION_DURATION)

    c1.memory.add_raw("yo", "hablé_con", c2.id, poignancy=5.0, keywords=["conversación", c2.id])
    c2.memory.add_raw("yo", "hablé_con", c1.id, poignancy=5.0, keywords=["conversación", c1.id])

    logger.info(f"🗣️  Conversation: {c1.id} ↔ {c2.id} (gems: -{CONVERSATION_GEM_COST * 2})")


def _can_converse(c: "Creature", now: float) -> bool:
    if now - c.last_conversation < CONVERSATION_COOLDOWN:
        return False
    if c.using_obj:
        return False
    if c.inventory.is_carrying:
        return False
    if c.needs.hunger > CONVERSATION_MAX_HUNGER:
        return False
    if c.needs.happiness < CONVERSATION_MIN_HAPPINESS:
        return False
    return True


def update_conversations(creatures: list["Creature"], delta: float) -> None:
    if not CONVERSATIONS_ENABLED:
        return

    now = time.time()
    for c in creatures:
        if not c.in_conversation:
            continue

        c.conversation_timer += delta
        c.navigator.clear_path()

        if now >= c.conversation_end_time or c.conversation_timer >= CONVERSATION_DURATION:
            _end_conversation(c, now)


def _end_conversation(c: "Creature", now: float) -> None:
    c.in_conversation = False
    c.last_conversation = now

    partner = c.conversation_partner
    c.conversation_partner = None

    if partner and not c.conversation_diary_written:
        from agent.writing import trigger_writing
        trigger_writing(c, CONVERSATION_GEM_COST, is_selected=c.selected)
        c.conversation_diary_written = True
        partner.conversation_diary_written = True

    logger.debug(f"Conversation ended for {c.id}")