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
    """
    Aplica todos los mecanismos sociales a la lista de criaturas.
    """
    _proximity_effects(creatures, delta)
    _try_conversations(creatures, world)


def _proximity_effects(creatures: list["Creature"], delta: float) -> None:
    """Efectos de proximidad: confort y contagio de estados."""
    pairs = _get_nearby_pairs(creatures)
    
    for c, neighbors in pairs.items():
        if not neighbors:
            continue
            
        # Confort por proximidad
        c.needs.apply_proximity_bonus(delta)
        
        # Contagio de hambre
        hungry_count = sum(1 for n in neighbors if n.needs.hunger >= HUNGER_CRITICAL)
        for _ in range(hungry_count):
            c.needs.apply_hunger_contagion(delta)


def _get_nearby_pairs(creatures: list["Creature"]) -> dict["Creature", list["Creature"]]:
    """Obtiene pares de criaturas que están cerca una de otra."""
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
    """
    Intenta iniciar conversaciones entre pares de criaturas cercanas.
    Consume gemas y las hace estar quietas un tiempo.
    """
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
    """Devuelve criaturas que pueden iniciar/unirse a conversaciones."""
    now = time.time()
    available = []
    for c in creatures:
        if _can_converse(c, now) and not getattr(c, '_in_conversation', False):
            available.append(c)
    return available


def _find_conversation_partner(
    c1: "Creature",
    available: list["Creature"],
    paired: set,
    world
) -> "Creature | None":
    """Busca un compañero de conversación válido para c1."""
    # Probabilidad de iniciar conversación
    if random.random() > CONVERSATION_CHANCE:
        return None

    # Buscar candidatos cercanos
    candidates = [
        c2 for c2 in available
        if c2.id not in paired
        and c2.id != c1.id
        and c1.is_near(c2)
        and not getattr(c2, '_in_conversation', False)
    ]

    if not candidates:
        return None

    c2 = random.choice(candidates)

    # Verificar gemas disponibles
    store = world.nearest_store(c1.x, c1.y)
    if store is None or store.stored_gems < CONVERSATION_GEM_COST * 2:
        return None

    return c2


def _start_conversation(c1: "Creature", c2: "Creature", world, now: float) -> None:
    """Inicia una conversación entre dos criaturas."""
    # Gastar gemas
    store = world.nearest_store(c1.x, c1.y)
    if store is None:
        return

    store.stored_gems -= CONVERSATION_GEM_COST * 2

    # Marcar estado usando setattr para evitar warnings
    setattr(c1, '_in_conversation', True)
    setattr(c2, '_in_conversation', True)
    setattr(c1, '_conversation_partner', c2)
    setattr(c2, '_conversation_partner', c1)
    setattr(c1, '_conversation_timer', 0.0)
    setattr(c2, '_conversation_timer', 0.0)
    setattr(c1, '_conversation_end_time', now + CONVERSATION_DURATION)
    setattr(c2, '_conversation_end_time', now + CONVERSATION_DURATION)

    # Mensajes
    c1.set_message("💬 ...", duration=CONVERSATION_DURATION)
    c2.set_message("💬 ...", duration=CONVERSATION_DURATION)

    # Memoria
    c1.memory.add_raw(
        subject="yo", predicate="hablé_con", object_=c2.id,
        poignancy=5.0, keywords=["conversación", c2.id]
    )
    c2.memory.add_raw(
        subject="yo", predicate="hablé_con", object_=c1.id,
        poignancy=5.0, keywords=["conversación", c1.id]
    )

    logger.info(f"🗣️  Conversation: {c1.id} ↔ {c2.id} (gems: -{CONVERSATION_GEM_COST * 2})")


def _can_converse(c: "Creature", now: float) -> bool:
    """¿Puede esta criatura iniciar/unirse a una conversación?"""
    # Cooldown
    last_conv = getattr(c, '_last_conversation', 0)
    if now - last_conv < CONVERSATION_COOLDOWN:
        return False

    # Estados que impiden conversar
    if getattr(c, '_using_obj', False):
        return False
    if c.inventory.is_carrying:
        return False
    if c.needs.hunger > CONVERSATION_MAX_HUNGER:
        return False
    if c.needs.happiness < CONVERSATION_MIN_HAPPINESS:
        return False

    return True


def update_conversations(creatures: list["Creature"], delta: float) -> None:
    """
    Actualiza el estado de conversaciones en curso.
    Llama a esto desde el game loop después de update_social.
    """
    if not CONVERSATIONS_ENABLED:
        return

    now = time.time()

    for c in creatures:
        if not getattr(c, '_in_conversation', False):
            continue

        # Actualizar timer
        current_timer = getattr(c, '_conversation_timer', 0)
        setattr(c, '_conversation_timer', current_timer + delta)

        # Mantener quieto
        c.navigator.clear_path()

        # Verificar si terminó
        end_time = getattr(c, '_conversation_end_time', 0)
        if now >= end_time or current_timer >= CONVERSATION_DURATION:
            _end_conversation(c, now)


def _end_conversation(c: "Creature", now: float) -> None:
    """Finaliza la conversación de una criatura."""
    setattr(c, '_in_conversation', False)
    setattr(c, '_last_conversation', now)

    partner = getattr(c, '_conversation_partner', None)
    if partner:
        setattr(c, '_conversation_partner', None)

    # Intentar generar entrada de diario (una sola vez por conversación)
    # Solo la criatura que termina primero genera el diario
    if partner and not getattr(partner, '_conversation_diary_written', False):
        from agent.writing import trigger_writing

        # La criatura seleccionada tiene prioridad
        is_selected = getattr(c, 'selected', False)
        trigger_writing(c, CONVERSATION_GEM_COST, is_selected=is_selected)

        setattr(c, '_conversation_diary_written', True)
        setattr(partner, '_conversation_diary_written', True)

    logger.debug(f"Conversation ended for {c.id}")
