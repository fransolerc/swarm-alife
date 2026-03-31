# =============================================================================
# agent/behavior/conversation.py — Conversación entre criaturas
# =============================================================================

import logging
import time
from typing import TYPE_CHECKING, Optional

from agent.behavior.base import Behavior
from config import INTERACTION_RADIUS, WRITING_GEM_COST

if TYPE_CHECKING:
    from agent.creature import Creature

logger = logging.getLogger(__name__)

# Configuración de conversaciones
CONVERSATION_DURATION = 4.0       # segundos que dura una conversación
CONVERSATION_COOLDOWN = 30.0     # segundos entre conversaciones
MAX_CONVERSATION_DISTANCE = INTERACTION_RADIUS * 0.8  # deben estar bastante cerca
GEM_COST_PER_CONVERSATION = WRITING_GEM_COST  # mismo coste que escribir diario


class ConversationBehavior(Behavior):
    """
    Comportamiento social: dos criaturas se encuentran, gastan gemas,
    conversan (LLM genera diálogo) y lo registran en sus diarios.
    """

    def __init__(self, creature: "Creature"):
        super().__init__(creature)
        self._partner: Optional["Creature"] = None
        self._timer: float = 0.0
        self._state: str = "idle"  # idle | approaching | talking | finishing
        self._last_conversation_time: float = 0.0
        self._conversation_summary: str = ""
        self._pending_diary_entry: bool = False
        self._cost_paid: bool = False

    def can_execute(self, world) -> bool:
        """¿Puede iniciar/buscar conversación ahora?"""
        # Cooldown personal
        now = time.time()
        if now - self._last_conversation_time < CONVERSATION_COOLDOWN:
            return False

        # No si está ocupada con otras cosas
        if self._creature._using_obj or self._creature.inventory.is_carrying:
            return False

        # Buscar compañero potencial
        partner = self._find_conversation_partner()
        if partner is None:
            return False

        return True

    def execute(self, delta: float, world) -> bool:
        """
        Ejecuta la conversación.
        Returns True si sigue en progreso, False si terminó.
        """
        if self._state == "idle":
            # Iniciar nueva conversación
            self._partner = self._find_conversation_partner()
            if self._partner is None:
                return False

            # Verificar que ambas pueden pagar
            if not self._can_afford_conversation(world):
                return False

            self._state = "approaching"
            self._timer = 0.0
            self._cost_paid = False

        if self._state == "approaching":
            return self._execute_approach(world)

        if self._state == "talking":
            return self._execute_talking( world)

        if self._state == "finishing":
            return self._execute_finishing()

        return False

    def _execute_approach(self, world) -> bool:
        """Acercarse al compañero hasta estar lo suficientemente cerca."""
        if self._partner is None:
            self._state = "idle"
            return False

        # Verificar si el compañero sigue disponible
        if self._partner._using_obj or getattr(self._partner, '_in_conversation', False):
            self._reset()
            return False

        dist = self._creature.distance_to(self._partner)

        if dist <= MAX_CONVERSATION_DISTANCE:
            # Ya están cerca - iniciar conversación
            self._start_conversation(world)
            return True

        # Navegar hacia el compañero
        if not self._creature.navigator.has_path:
            self._creature.navigator.navigate_to(world, self._partner.x, self._partner.y)

        return True

    def _execute_talking(self, delta: float) -> bool:
        """Durante la conversación - ambas criaturas están quietas."""
        self._timer += delta

        # Mantener ambas criaturas marcadas como en conversación
        self._creature._in_conversation = True
        if self._partner:
            self._partner._in_conversation = True

        # Limpiar paths para que no se muevan
        self._creature.navigator.clear_path()
        if self._partner:
            self._partner.navigator.clear_path()

        if self._timer >= CONVERSATION_DURATION:
            self._state = "finishing"
            self._timer = 0.0

        return True

    def _execute_finishing(self) -> bool:
        """Finalizar conversación y escribir en diarios."""
        if self._pending_diary_entry and self._partner:
            # Generar entradas de diario para ambas
            self._generate_conversation_entries()
            self._pending_diary_entry = False

        self._last_conversation_time = time.time()
        if self._partner:
            # Actualizar cooldown del compañero también (mitad del normal)
            self._partner._conversation_cooldown = time.time() + CONVERSATION_COOLDOWN * 0.5

        self._reset()
        return False

    def _find_conversation_partner(self) -> Optional["Creature"]:
        """Busca una criatura cercana que también quiera conversar."""
        # Necesitamos acceso a la lista de criaturas - está en world o necesitamos pasarla
        # Por ahora, retornamos None y lo manejaremos desde el Game
        return None

    def _can_afford_conversation(self, world) -> bool:
        """Verificar que hay gemas disponibles para la conversación."""
        store = world.nearest_store(self._creature.x, self._creature.y)
        if store is None or store.stored_gems < GEM_COST_PER_CONVERSATION * 2:
            # Necesitamos gemas para ambas criaturas
            return False
        return True

    def _start_conversation(self, world):
        """Iniciar la conversación: gastar gemas, marcar estados."""
        # Gastar gemas
        store = world.nearest_store(self._creature.x, self._creature.y)
        if store:
            store.stored_gems -= GEM_COST_PER_CONVERSATION * 2

        self._cost_paid = True
        self._state = "talking"
        self._timer = 0.0
        self._pending_diary_entry = True

        # Marcar a ambas como en conversación
        self._creature._in_conversation = True
        if self._partner:
            self._partner._in_conversation = True

        # Mensaje burbuja
        self._creature.set_message("💬 ...", duration=CONVERSATION_DURATION)
        if self._partner:
            self._partner.set_message("💬 ...", duration=CONVERSATION_DURATION)

        logger.info(f"Conversation started: {self._creature.id} ↔ {self._partner.id}")

    def _generate_conversation_entries(self):
        """Genera entradas de diario para ambas criaturas."""
        if self._partner is None:
            return

        # Crear resumen contextual
        keywords_c1 = ["hablé con", self._partner.id]
        keywords_c2 = ["hablé con", self._creature.id]

        # Entrada para criatura 1
        self._creature.memory.add_raw(
            subject="yo", predicate="hablé_con", object_=self._partner.id,
            poignancy=6.0, keywords=keywords_c1
        )

        # Entrada para criatura 2
        self._partner.memory.add_raw(
            subject="yo", predicate="hablé_con", object_=self._creature.id,
            poignancy=6.0, keywords=keywords_c2
        )

        # Intentar generar diario LLM (rate limited)
        from agent.writing import trigger_writing

        # Solo una de las dos escribe el diario (para no saturar)
        # La criatura seleccionada tiene prioridad
        is_selected = getattr(self._creature, 'selected', False)
        trigger_writing(self._creature, GEM_COST_PER_CONVERSATION, is_selected=is_selected)

        logger.debug(f"Conversation logged: {self._creature.id} ↔ {self._partner.id}")

    def _reset(self):
        """Resetear estado."""
        # Limpiar flags de conversación
        self._creature._in_conversation = False
        if self._partner:
            self._partner._in_conversation = False

        self._partner = None
        self._timer = 0.0
        self._state = "idle"
        self._conversation_summary = ""
        self._pending_diary_entry = False
        self._cost_paid = False

    def reset(self) -> None:
        """Reset forzado desde fuera."""
        self._reset()
