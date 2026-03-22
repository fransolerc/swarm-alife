# =============================================================================
# locales.py — swarm-alife
# Todos los strings visibles centralizados. Sin texto hardcode en el código.
# =============================================================================

from config import LANGUAGE

_STRINGS = {
    "es": {
        # --- UI ---
        "ui_selected":       "Seleccionada",
        "ui_no_selection":   "Ninguna criatura seleccionada",
        "ui_needs":          "Necesidades",
        "ui_hunger":         "Hambre",
        "ui_hygiene":        "Higiene",
        "ui_happiness":      "Felicidad",
        "ui_energy":         "Energía",
        "ui_messages":       "Mensajes",
        "ui_time":           "Hora",
        "ui_actions":        "Acciones",
        "ui_feed_all":       "[F] Alimentar todas",
        "ui_shower_all":     "[D] Duchar todas",
        "ui_play_all":       "[J] Jugar con todas",
        "ui_feed_one":       "[F] Alimentar",
        "ui_shower_one":     "[D] Duchar",
        "ui_play_one":       "[J] Jugar",
        "ui_sleep_one":      "[S] Dormir",

        # --- Estados de necesidad ---
        "need_satisfied":    "satisfecha",
        "need_hungry":       "hambrienta",
        "need_critical":     "crítica",
        "need_tired":        "agotada",
        "need_dirty":        "sucia",
        "need_sad":          "triste",

        # --- Períodos del día ---
        "period_morning":    "mañana",
        "period_afternoon":  "tarde",
        "period_evening":    "noche",
        "period_night":      "madrugada",

        # --- Prompts LLM ---
        # {name} y {need} son sustituidos en tiempo de ejecución
        "llm_system": (
            "Eres una criatura pequeña y expresiva. "
            "Comunicas tu estado emocional en una sola frase breve, "
            "en primera persona, sin explicaciones. "
            "Máximo 15 palabras."
        ),
        "llm_prompt_hunger":    "Tengo mucha hambre. ¿Cómo me siento ahora mismo?",
        "llm_prompt_hygiene":   "Estoy muy sucio. ¿Cómo me siento ahora mismo?",
        "llm_prompt_happiness": "Me siento muy solo y triste. ¿Cómo me siento ahora mismo?",
        "llm_prompt_energy":    "Estoy agotado. ¿Cómo me siento ahora mismo?",

        # --- Mensajes de error / fallback ---
        "llm_fallback_hunger":    "...tengo hambre.",
        "llm_fallback_hygiene":   "...necesito ducharme.",
        "llm_fallback_happiness": "...me siento solo.",
        "llm_fallback_energy":    "...estoy muy cansado.",
        "llm_error":              "[sin respuesta]",
    },

    "en": {
        # --- UI ---
        "ui_selected":       "Selected",
        "ui_no_selection":   "No creature selected",
        "ui_needs":          "Needs",
        "ui_hunger":         "Hunger",
        "ui_hygiene":        "Hygiene",
        "ui_happiness":      "Happiness",
        "ui_energy":         "Energy",
        "ui_messages":       "Messages",
        "ui_time":           "Time",
        "ui_actions":        "Actions",
        "ui_feed_all":       "[F] Feed all",
        "ui_shower_all":     "[D] Shower all",
        "ui_play_all":       "[J] Play with all",
        "ui_feed_one":       "[F] Feed",
        "ui_shower_one":     "[D] Shower",
        "ui_play_one":       "[J] Play",
        "ui_sleep_one":      "[S] Sleep",

        # --- Need states ---
        "need_satisfied":    "satisfied",
        "need_hungry":       "hungry",
        "need_critical":     "critical",
        "need_tired":        "exhausted",
        "need_dirty":        "dirty",
        "need_sad":          "sad",

        # --- Day periods ---
        "period_morning":    "morning",
        "period_afternoon":  "afternoon",
        "period_evening":    "evening",
        "period_night":      "night",

        # --- LLM prompts ---
        "llm_system": (
            "You are a small expressive creature. "
            "Communicate your emotional state in a single short sentence, "
            "in first person, no explanations. "
            "Maximum 15 words."
        ),
        "llm_prompt_hunger":    "I'm very hungry. How do I feel right now?",
        "llm_prompt_hygiene":   "I'm very dirty. How do I feel right now?",
        "llm_prompt_happiness": "I feel very lonely and sad. How do I feel right now?",
        "llm_prompt_energy":    "I'm exhausted. How do I feel right now?",

        # --- Fallback messages ---
        "llm_fallback_hunger":    "...I'm so hungry.",
        "llm_fallback_hygiene":   "...I need a shower.",
        "llm_fallback_happiness": "...I feel so alone.",
        "llm_fallback_energy":    "...I'm exhausted.",
        "llm_error":              "[no response]",
    },
}


def t(key: str) -> str:
    """Devuelve el string localizado para la clave dada."""
    lang = _STRINGS.get(LANGUAGE, _STRINGS["es"])
    return lang.get(key, f"[{key}]")
