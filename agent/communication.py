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


def trigger_llm_message(creature: "Creature", need: str, is_selected: bool = False) -> None:
    """
    Invoca el LLM de forma asíncrona (hilo separado) para generar un mensaje
    breve que refleje el estado emocional de la criatura.
    
    Rate limiting: solo una llamada LLM activa global, prioridad a seleccionadas.
    """
    import config
    import time
    
    # Verificar cooldown global
    now = time.time()
    last_global_call = getattr(trigger_llm_message, '_last_global_call', 0)
    time_since_last = now - last_global_call
    if time_since_last < config.LLM_GLOBAL_COOLDOWN:
        # Solo permitir si es seleccionada y han pasado al menos 1 segundo
        if not (is_selected and time_since_last >= 1.0):
            logger.debug(f"LLM skipped for {creature.id}: global cooldown ({time_since_last:.1f}s)")
            return
    
    # Rate limit: máximo de llamadas por minuto
    call_times = getattr(trigger_llm_message, '_call_times', [])
    # Limpiar llamadas antiguas (> 60 segundos)
    call_times = [ct for ct in call_times if now - ct < 60]
    setattr(trigger_llm_message, '_call_times', call_times)
    
    if len(call_times) >= config.LLM_MAX_CALLS_PER_MIN:
        # Solo permitir si es seleccionada y prioridad está habilitada
        if not (is_selected and config.LLM_SELECTED_PRIORITY):
            logger.debug(f"LLM skipped for {creature.id}: max calls per minute reached")
            return
    
    # Solo una llamada activa a la vez
    active_calls = getattr(trigger_llm_message, '_active_calls', 0)
    if active_calls >= 1:
        logger.debug(f"LLM skipped for {creature.id}: another call in progress")
        return
    setattr(trigger_llm_message, '_active_calls', active_calls + 1)
    
    # Registrar tiempo de llamada
    setattr(trigger_llm_message, '_last_global_call', now)
    call_times.append(now)
    setattr(trigger_llm_message, '_call_times', call_times)
    
    thread = threading.Thread(
        target=_llm_call_wrapper,
        args=(creature, need),
        daemon=True,
        name=f"llm-{creature.id}-{need}",
    )
    thread.start()
    logger.info(f"LLM triggered for {creature.id} (need: {need}, selected: {is_selected})")


def _llm_call_wrapper(creature: "Creature", need: str) -> None:
    """Wrapper que maneja el contador de llamadas activas."""
    try:
        _llm_call(creature, need)
    finally:
        # Decrementar contador de forma segura usando getattr/setattr
        current = getattr(trigger_llm_message, '_active_calls', 1)
        setattr(trigger_llm_message, '_active_calls', max(0, current - 1))


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
