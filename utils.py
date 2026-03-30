# =============================================================================
# utils.py — swarm-alife
# Utilidades compartidas.
# =============================================================================

import os
import json
import tempfile
import logging
import math
import random
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)

# Mutex global para asegurar acceso exclusivo a archivos.
# Previene errores de "PermissionError" en Windows cuando varios hilos 
# intentan manipular el mismo archivo (diario, estados de criaturas, etc).
_file_lock = threading.RLock()


def atomic_write_json(path: str, data: Any) -> None:
    """Escribe data como JSON en path de forma atómica."""
    dir_path = os.path.dirname(path) or "."
    os.makedirs(dir_path, exist_ok=True)
    
    with _file_lock:
        fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as tmp:
                json.dump(data, tmp, ensure_ascii=False, indent=2)
            
            # En Windows, os.replace puede fallar momentáneamente si el archivo 
            # acaba de cerrarse. Intentamos un par de veces.
            for i in range(5):
                try:
                    os.replace(tmp_path, path)
                    break
                except PermissionError:
                    if i == 4: raise
                    time.sleep(0.01 * (i + 1))
        except Exception as e:
            if os.path.exists(tmp_path):
                try: os.remove(tmp_path)
                except: pass
            logger.error(f"atomic_write_json failed for {path}: {e}")
            raise


def load_json(path: str, default: Any = None) -> Any:
    """Carga JSON desde path de forma segura."""
    with _file_lock:
        if not os.path.exists(path):
            return default
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"load_json failed for {path}: {e}")
            return default


def safe_append_text(path: str, text: str) -> None:
    """Añade texto a un archivo de forma segura bajo el lock global."""
    dir_path = os.path.dirname(path) or "."
    if dir_path and not os.path.exists(dir_path):
        os.makedirs(dir_path, exist_ok=True)
        
    with _file_lock:
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(text)
        except Exception as e:
            logger.error(f"safe_append_text failed for {path}: {e}")


# --- Extracción de keywords ---

_STOPWORDS_ES = {
    "de", "la", "el", "en", "y", "a", "los", "las", "un", "una", "que",
    "es", "se", "no", "con", "por", "para", "su", "al", "lo", "como",
    "más", "pero", "sus", "le", "ya", "o", "fue", "este", "ha", "si",
    "me", "mi", "muy", "tengo", "siento", "estoy", "hay", "ahora", "cuando",
}

_STOPWORDS_EN = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "i", "my", "me", "it", "its", "this", "that",
    "feel", "feeling", "very", "so", "am", "now",
}

_PUNCTUATION = ".,;:!?\"'()[]"

def extract_keywords(text: str, language: str = "es", max_keywords: int = 8) -> list[str]:
    """Extrae keywords relevantes de un texto eliminando stopwords."""
    stopwords = _STOPWORDS_ES if language == "es" else _STOPWORDS_EN
    words = text.lower().split()
    keywords = [
        w.strip(_PUNCTUATION)
        for w in words
        if w.strip(_PUNCTUATION) not in stopwords
        and len(w.strip(_PUNCTUATION)) > 2
    ]
    return keywords[:max_keywords]


# --- Matemáticas / geometría ---

def distance(pos1: tuple[float, float], pos2: tuple[float, float]) -> float:
    """Distancia euclidiana entre dos puntos (x, y)."""
    return math.hypot(pos1[0] - pos2[0], pos1[1] - pos2[1])


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Limita value al rango [min_val, max_val]."""
    return max(min_val, min(max_val, value))


def random_point_in_rect(x: int, y: int, w: int, h: int) -> tuple[float, float]:
    """Punto aleatorio dentro de un rectángulo."""
    return random.uniform(x, x + w), random.uniform(y, y + h)


def normalize(dx: float, dy: float) -> tuple[float, float]:
    """Normaliza un vector (dx, dy). Devuelve (0, 0) si es nulo."""
    length = math.hypot(dx, dy)
    if length == 0:
        return 0.0, 0.0
    return dx / length, dy / length


# --- Logging ---

def setup_logging(level: int = logging.INFO) -> None:
    """Configura el logging básico para el proyecto."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
