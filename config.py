# =============================================================================
# config.py — swarm-alife
# Todas las constantes del sistema. Sin hardcoding fuera de este fichero.
# =============================================================================

# --- General ---
LANGUAGE = "es"           # "es" | "en"
FPS = 60
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720
WINDOW_TITLE = "swarm-alife"

# --- Simulación ---
NUM_CREATURES = 1         # Criaturas al inicio (la experiencia canónica es 1)
SIM_SPEED = 1.0           # Multiplicador de velocidad de simulación (1.0 = tiempo real)

# --- Reproducción asexual (división) ---
# Condición: edad mínima Y todas las necesidades por encima del umbral
REPRODUCTION_MIN_AGE        = 60.0   # Segundos reales mínimos de vida antes de poder dividirse
REPRODUCTION_NEED_THRESHOLD = 55.0   # Todas las necesidades deben superar este valor
REPRODUCTION_COOLDOWN       = 90.0   # Segundos reales de cooldown tras dividirse
# Las crías heredan necesidades del padre con algo de varianza
OFFSPRING_NEED_VARIANCE     = 15.0   # ±N sobre el valor del padre
# Distancia de spawn respecto al padre
OFFSPRING_SPAWN_RADIUS      = 40.0

# --- Criaturas: movimiento ---
CREATURE_RADIUS = 18      # Radio visual (píxeles)
CREATURE_SPEED = 60       # Píxeles por segundo
WANDER_INTERVAL = (2.0, 5.0)   # Segundos entre cambios de dirección (min, max)
INTERACTION_RADIUS = 80   # Radio de influencia social entre criaturas

# --- Sistema de necesidades ---
# Valores: 0.0 (mínimo) — 100.0 (máximo)

NEED_MAX = 100.0
NEED_MIN = 0.0

# Tasas de cambio pasivo (unidades por segundo de simulación)
HUNGER_RATE       =  1.2   # Aumenta con el tiempo
HYGIENE_RATE      = -0.8   # Disminuye con el tiempo
HAPPINESS_RATE    = -0.5   # Disminuye con el tiempo
ENERGY_RATE       = -0.6   # Disminuye con actividad

# Valores iniciales (con varianza para que no arranquen sincronizadas)
NEED_INITIAL_VARIANCE = 20.0  # ±N sobre el valor base

HUNGER_INITIAL    = 30.0
HYGIENE_INITIAL   = 80.0
HAPPINESS_INITIAL = 70.0
ENERGY_INITIAL    = 80.0

# Umbrales de seeking: disparan que la criatura busque el objeto autónomamente
# Más bajos que LLM para que actúen antes de llegar al límite
HUNGER_SEEK_THRESHOLD    = 45.0   # busca comida cuando hambre > 45
HYGIENE_SEEK_THRESHOLD   = 50.0   # busca baño cuando higiene < 50  (solo si usuario la dirige)
HAPPINESS_SEEK_THRESHOLD = 40.0   # busca pelota cuando felicidad < 40
ENERGY_SEEK_THRESHOLD    = 30.0   # busca cama cuando energía < 30

# Umbrales de comunicación: dispara invocación LLM
HUNGER_LLM_THRESHOLD    = 75.0
HYGIENE_LLM_THRESHOLD   = 25.0
HAPPINESS_LLM_THRESHOLD = 20.0
ENERGY_LLM_THRESHOLD    = 15.0

# Umbrales críticos: cambia comportamiento visible
HUNGER_CRITICAL    = 85.0
HYGIENE_CRITICAL   = 15.0
HAPPINESS_CRITICAL = 10.0
ENERGY_CRITICAL    = 10.0

# Cooldown mínimo entre mensajes LLM por criatura (segundos reales)
LLM_MESSAGE_COOLDOWN = 30.0

# Duración de uso de cada objeto (segundos que la criatura permanece junto al objeto)
OBJ_USE_DURATION: dict = {
    "BATH": 4.0,   # bañarse
    "BALL": 5.0,   # jugar
    "BED":  8.0,   # descansar
}

# --- Comportamiento social ---
# Contagio: cuánto afecta el estado de un vecino al propio
CONTAGION_HUNGER_RATE    = 0.05   # Por segundo, si vecino tiene hambre crítica
CONTAGION_ANXIETY_RATE   = 0.03   # Por segundo, contagio de ansiedad (baja happiness)

# Confort por proximidad
PROXIMITY_HAPPINESS_BONUS = 0.2   # Por segundo si hay ≥1 vecino cerca

# Competencia por recursos
FOOD_SOURCE_CAPACITY = 3          # Máx criaturas comiendo a la vez
TENSION_QUEUE_RATE   = 0.1        # Happiness baja si hay cola en la fuente

# --- Interacciones del usuario ---
FEED_HUNGER_REDUCTION   = 40.0
SHOWER_HYGIENE_RESTORE  = 50.0
PLAY_HAPPINESS_BONUS    = 30.0
PLAY_ENERGY_COST        = 15.0
SLEEP_ENERGY_RESTORE    = 60.0

# --- Memoria ---
MAX_ASSOCIATIVE_NODES = 100

# --- LLM ---
OLLAMA_MODEL   = "llama3.2:3b"
OLLAMA_TIMEOUT = 10           # Segundos máximos esperando respuesta
LLM_MAX_TOKENS = 80           # Respuestas cortas, solo comunicación

# --- Tiempo simulado ---
# 1 minuto real = SIM_MINUTES_PER_REAL_MINUTE minutos simulados
SIM_MINUTES_PER_REAL_MINUTE = 60   # 1 hora simulada por minuto real

# --- Mundo: cuadrícula ---
GRID_CELL         = 40          # píxeles por celda
OBJECT_USE_RANGE  = 38          # distancia para interactuar con un objeto (px)

# --- Objetos: efectos al usarlos ---
TREE_BLOCKS_PATH       = True
FOOD_HUNGER_REDUCTION  = 45.0
BATH_HYGIENE_RESTORE   = 55.0
BALL_HAPPINESS_BONUS   = 35.0
BALL_ENERGY_COST       = 10.0
BED_ENERGY_RESTORE     = 65.0

# Cooldown por objeto: segundos entre usos consecutivos por la misma criatura
OBJECT_USE_COOLDOWN = 8.0

# --- Tala de árboles ---
STUMP_DURATION      = 15.0   # segundos que permanece el tocón antes de desaparecer
WOOD_PER_TREE       = 2      # unidades de madera por árbol talado

# --- Modo colocación ---
PLACEMENT_GRID_COLOR    = (58,  82,  40)
PLACEMENT_HOVER_COLOR   = (144, 224, 112)
PLACEMENT_BLOCKED_COLOR = (200, 80,  60)

# --- Rendering ---
TOOLBAR_HEIGHT    = 82        # Altura de la barra de herramientas inferior
UI_PANEL_WIDTH    = 0         # Deprecated — mantenido por compatibilidad, no usar
SPRITE_SIZE       = 36
NEED_BAR_WIDTH    = 40
NEED_BAR_HEIGHT   = 5
NEED_BAR_OFFSET_Y = 24

# Toolbar — estilo madera
TOOLBAR_WOOD_DARK  = (90,  58,  24)
TOOLBAR_WOOD_MID   = (184, 137, 74)
TOOLBAR_WOOD_LIGHT = (212, 168, 96)
TOOLBAR_WOOD_EDGE  = (232, 196, 120)
TOOLBAR_BTN_DARK   = (138, 96,  48)
TOOLBAR_BTN_SEL    = (200, 160, 80)
TOOLBAR_BTN_SEL_EDGE = (255, 224, 128)
TOOLBAR_TEXT       = (58,  32,  10)

# --- Rutas ---
DATA_DIR = "data"             # Directorio de memoria persistente por criatura
ASSETS_DIR = "assets"
SPRITES_DIR = f"{ASSETS_DIR}/sprites"

# --- Colores (RGB) ---
COLOR_BG         = (30, 30, 40)
COLOR_CREATURE   = (120, 200, 140)
COLOR_SELECTED   = (255, 220, 50)
COLOR_CRITICAL   = (220, 60, 60)
COLOR_UI_BG      = (20, 20, 30)
COLOR_UI_TEXT    = (200, 200, 210)
COLOR_NEED_BAR_BG = (60, 60, 70)
COLOR_HUNGER_BAR  = (230, 120, 50)
COLOR_HYGIENE_BAR = (80, 180, 220)
COLOR_HAPPINESS_BAR = (240, 200, 60)
COLOR_ENERGY_BAR  = (100, 220, 160)
COLOR_FOOD_SOURCE = (180, 230, 100)
COLOR_MESSAGE_BG  = (40, 40, 55)
COLOR_MESSAGE_TEXT = (220, 240, 200)
