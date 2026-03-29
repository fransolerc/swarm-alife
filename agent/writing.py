# =============================================================================
# agent/writing.py — swarm-alife
# Escritura de diario event-driven. Se invoca cuando una criatura cómoda
# dispone de gemas suficientes en el almacén. Nunca bloquea el loop principal.
# =============================================================================

import logging
import os
import threading
import time
from datetime import datetime
from typing import TYPE_CHECKING

from config import OLLAMA_MODEL, LANGUAGE, DIARY_FILE
from utils import atomic_write_json, load_json

if TYPE_CHECKING:
    from agent.creature import Creature

logger = logging.getLogger(__name__)

_DIARY_MD = DIARY_FILE.replace(".json", ".md")


def trigger_writing(creature: "Creature", gems_spent: int) -> None:
    """
    Lanza la escritura de diario en un hilo separado.
    No bloquea el loop de Pygame. La entrada se escribe en data/diary.json
    y en data/diary.md cuando el LLM responde.
    """
    thread = threading.Thread(
        target=_writing_call,
        args=(creature, gems_spent),
        daemon=True,
        name=f"write-{creature.id}",
    )
    thread.start()
    logger.info(f"Writing triggered for {creature.id} ({gems_spent} gems)")


def _writing_call(creature: "Creature", gems_spent: int) -> None:
    """Llamada real al LLM. Corre en hilo separado."""
    try:
        import ollama

        # Contexto de memoria reciente de la criatura
        recent = creature.memory.retrieve(
            query_keywords=["yo", "comi", "use", "deposite", "usuario"],
            top_k=5,
        )
        context = "; ".join(n.to_text() for n in recent) if recent else "nada en particular"

        if LANGUAGE == "es":
            system = (
                "Eres una pequeña criatura sintiente. Escribes en tu diario personal. "
                "Primera persona, tono íntimo y breve. Sin explicaciones ni metanarración. "
                "Máximo 40 palabras."
            )
            prompt = (
                f"Soy {creature.id}. He gastado {gems_spent} gemas para escribir esto. "
                f"Recuerdo: {context}. "
                f"Escribe la entrada de diario de hoy."
            )
        else:
            system = (
                "You are a small sentient creature. You write in your personal diary. "
                "First person, intimate and brief. No explanations or meta-narration. "
                "Max 40 words."
            )
            prompt = (
                f"I am {creature.id}. I spent {gems_spent} gems to write this. "
                f"I remember: {context}. "
                f"Write today's diary entry."
            )

        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": prompt},
            ],
            options={"num_predict": 120, "temperature": 0.92},
        )

        text = response["message"]["content"].strip().replace("\n", " ")
        if len(text) > 220:
            text = text[:220].rsplit(" ", 1)[0] + "…"

    except Exception as e:
        logger.error(f"Writing LLM call failed for {creature.id}: {e}")
        text = (
            "...hoy ha sido un día normal. Sigo aquí."
            if LANGUAGE == "es"
            else "...today was an ordinary day. Still here."
        )

    _append_diary(creature.id, text, gems_spent)

    # El mensaje visible en burbuja es una versión corta
    preview = text[:70] + "…" if len(text) > 70 else text
    creature.set_message(f"✍ {preview}", duration=8.0)
    logger.info(f"Diary entry written by {creature.id}: {text[:60]!r}")


def _append_diary(creature_id: str, text: str, gems: int) -> None:
    """Persiste la entrada en diary.json y diary.md de forma atómica."""
    os.makedirs("data", exist_ok=True)

    entry = {
        "creature_id": creature_id,
        "text":        text,
        "gems_spent":  gems,
        "timestamp":   time.time(),
        "datetime":    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    # JSON estructurado (para el overlay in-game)
    entries = load_json(DIARY_FILE, default=[])
    entries.append(entry)
    atomic_write_json(DIARY_FILE, entries)

    # Markdown legible fuera del juego
    write_header = not os.path.exists(_DIARY_MD)
    with open(_DIARY_MD, "a", encoding="utf-8") as f:
        if write_header:
            f.write("# Diario de las criaturas — swarm-alife\n\n")
        f.write(
            f"## [{entry['datetime']}] {creature_id}  _(💎 ×{gems})_\n"
            f"{text}\n\n"
        )
