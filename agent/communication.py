# =============================================================================
# agent/communication.py — swarm-alife
# Comunicación LLM event-driven. Se invoca solo cuando una criatura supera
# un umbral crítico de necesidad. Nunca corre en ciclo continuo.
# =============================================================================

import logging
import threading
from typing import TYPE_CHECKING

from locales import t
from config import OLLAMA_MODEL, LLM_MAX_TOKENS, LANGUAGE

if TYPE_CHECKING:
    from agent.creature import Creature

logger = logging.getLogger(__name__)


def trigger_llm_message(creature: "Creature", need: str) -> None:
    """
    Invoca el LLM de forma asíncrona (hilo separado) para generar un mensaje
    breve que refleje el estado emocional de la criatura.

    La respuesta se escribe en creature.current_message cuando está lista.
    No bloquea el loop principal de Pygame.

    Need: "hunger" | "hygiene" | "happiness" | "energy"
    """
    thread = threading.Thread(
        target=_llm_call,
        args=(creature, need),
        daemon=True,
        name=f"llm-{creature.id}-{need}",
    )
    thread.start()
    logger.info(f"LLM triggered for {creature.id} (need: {need})")


def _llm_call(creature: "Creature", need: str) -> None:
    """
    Llamada real a Ollama. Corre en hilo separado.
    En caso de error: usa fallback de locales.py, nunca swallow silencioso.
    """
    try:
        import ollama

        # Construir prompt a partir de memoria reciente
        recent_nodes = creature.memory.retrieve(
            query_keywords=[need, "usuario", "yo"],
            top_k=3,
        )
        memory_context = ""
        if recent_nodes:
            if LANGUAGE == "es":
                memory_context = "Recuerdas: " + "; ".join(
                    n.to_text() for n in recent_nodes
                ) + ". "
            else:
                memory_context = "You remember: " + "; ".join(
                    n.to_text() for n in recent_nodes
                ) + ". "

        system_prompt = t("llm_system")
        user_prompt   = memory_context + t(f"llm_prompt_{need}")

        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            options={
                "num_predict": LLM_MAX_TOKENS,
                "temperature": 0.8,
            },
        )

        message = response["message"]["content"].strip()

        # Sanitizar: máx. 2 frases, sin saltos de línea
        message = message.replace("\n", " ").strip()
        if len(message) > 120:
            message = message[:120].rsplit(" ", 1)[0] + "…"

        logger.info(f"LLM response for {creature.id}: {message!r}")
        creature.set_message(message)

    except Exception as e:
        # Error explícito, nunca silencioso
        logger.error(f"LLM call failed for {creature.id} (need={need}): {e}")
        fallback = t(f"llm_fallback_{need}")
        creature.set_message(fallback)
