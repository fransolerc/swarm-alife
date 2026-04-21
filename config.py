# =============================================================================
# config.py — swarm-alife
# =============================================================================

LANGUAGE = "es"
FPS = 60
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720
WINDOW_TITLE = "swarm-alife"

NUM_CREATURES = 1
SIM_SPEED = 1.0

REPRODUCTION_MIN_AGE        = 60.0
REPRODUCTION_NEED_THRESHOLD = 55.0
REPRODUCTION_COOLDOWN       = 90.0
OFFSPRING_NEED_VARIANCE     = 15.0
OFFSPRING_SPAWN_RADIUS      = 40.0

CREATURE_RADIUS = 18
CREATURE_SPEED = 60
WANDER_INTERVAL = (2.0, 5.0)
INTERACTION_RADIUS = 120

NEED_MAX = 100.0
NEED_MIN = 0.0

HUNGER_RATE       =  0.5
HYGIENE_RATE      =  0.5
HAPPINESS_RATE    =  0.5

NEED_INITIAL_VARIANCE = 20.0

HUNGER_INITIAL    = 0.0
HYGIENE_INITIAL   = 100.0
HAPPINESS_INITIAL = 70.0

HUNGER_SEEK_THRESHOLD    = 45.0
HYGIENE_SEEK_THRESHOLD   = 20.0
HAPPINESS_SEEK_THRESHOLD = 20.0

HUNGER_LLM_THRESHOLD    = 75.0
HYGIENE_LLM_THRESHOLD   = 25.0
HAPPINESS_LLM_THRESHOLD = 20.0

HUNGER_CRITICAL    = 85.0
HYGIENE_CRITICAL   = 15.0
HAPPINESS_CRITICAL = 10.0

LLM_MESSAGE_COOLDOWN = 30.0

OBJ_USE_DURATION: dict = {
    "BATH": 4.0,
    "BALL": 5.0,
}

CONTAGION_HUNGER_RATE     = 0.05
CONTAGION_ANXIETY_RATE    = 0.03
PROXIMITY_HAPPINESS_BONUS = 0.2
FOOD_SOURCE_CAPACITY      = 3
TENSION_QUEUE_RATE        = 0.1

FEED_HUNGER_REDUCTION  = 40.0
SHOWER_HYGIENE_RESTORE = 50.0
PLAY_HAPPINESS_BONUS   = 30.0

MAX_ASSOCIATIVE_NODES = 100

OLLAMA_MODEL   = "llama3.2:3b"
OLLAMA_TIMEOUT = 10
LLM_MAX_TOKENS = 80

SIM_MINUTES_PER_REAL_MINUTE = 60

GRID_CELL        = 40
OBJECT_USE_RANGE = 80  # Ampliado para asegurar alcance a almacenes y objetos bloqueados

TREE_BLOCKS_PATH      = True
FOOD_HUNGER_REDUCTION = 100.0
BATH_HYGIENE_RESTORE  = 100.0
BALL_HAPPINESS_BONUS  = 100.0

OBJECT_USE_COOLDOWN = 8.0

# --- Almacén ---
STORE_SIZE           = 2     # 2×2 celdas (80×80 px)
CARRY_NEED_THRESHOLD = 30.0  # Umbral más bajo para que trabajen más tiempo

# --- Tala ---
STUMP_DURATION = 90.0  # Más tiempo para recoger la madera antes de que el tronco desaparezca
WOOD_PER_TREE  = 2

# --- Manzanas ---
APPLE_MAX_PER_TREE = 3
APPLE_REGROW_TIME  = 45.0
APPLE_ROT_TIME     = 90.0  # Más tiempo para recoger manzanas del suelo
APPLE_PICK_RANGE   = 80.0
APPLE_HUNGER_VALUE = 30.0
SHAKE_COOLDOWN     = 2.0
APPLE_TREE_CHANCE  = 0.6
APPLE_SHAKE_RANGE  = 80.0

# --- Yacimientos y minas ---
GEM_DEPOSIT_COUNT     = 4      # yacimientos generados al inicio del mundo
MINE_EXTRACT_COOLDOWN = 12.0   # segundos entre extracciones de gema por criatura

# --- Conversaciones entre criaturas ---
CONVERSATIONS_ENABLED = True       # Activar/desactivar sistema de conversaciones
CONVERSATION_CHANCE = 0.02          # probabilidad por tick de iniciar conversación
CONVERSATION_MIN_HAPPINESS = 30.0  # necesita cierta felicidad para socializar
CONVERSATION_MAX_HUNGER = 60.0       # no conversa si tiene mucha hambre
CONVERSATION_COOLDOWN = 45.0         # segundos entre conversaciones
CONVERSATION_GEM_COST = 3           # gemas que cuesta cada conversación (c/u)
CONVERSATION_DURATION = 5.0          # segundos que duran quietos hablando

# --- Escritura (diario LLM) ---
# Desactivado por defecto para evitar colapso con muchas criaturas
# Options: "disabled" | "selected_only" | "full"
WRITING_MODE      = "disabled"  # "disabled" = sin diario, "selected_only" = solo criatura seleccionada, "full" = todas
WRITING_GEM_COST  = 3           # gemas que cuesta cada entrada de diario
WRITING_COOLDOWN  = 90.0        # segundos entre escrituras por criatura
DIARY_FILE        = "data/diary.json"

# --- LLM Mensajes ---
# Rate limiting global para evitar colapso
LLM_GLOBAL_COOLDOWN     = 5.0     # mínimos segundos entre llamadas LLM (globales)
LLM_MAX_CALLS_PER_MIN   = 10    # máximo de llamadas por minuto (aprox)
LLM_SELECTED_PRIORITY   = True    # priorizar llamadas para criaturas seleccionadas

PLACEMENT_GRID_COLOR    = (58,  82,  40)
PLACEMENT_HOVER_COLOR   = (144, 224, 112)
PLACEMENT_BLOCKED_COLOR = (200, 80,  60)

TOOLBAR_HEIGHT    = 82
UI_PANEL_WIDTH    = 0
SPRITE_SIZE       = 36
NEED_BAR_WIDTH    = 40
NEED_BAR_HEIGHT   = 5
NEED_BAR_OFFSET_Y = 24

TOOLBAR_WOOD_DARK    = (90,  58,  24)
TOOLBAR_WOOD_MID     = (184, 137, 74)
TOOLBAR_WOOD_LIGHT   = (212, 168, 96)
TOOLBAR_WOOD_EDGE    = (232, 196, 120)
TOOLBAR_BTN_DARK     = (138, 96,  48)
TOOLBAR_BTN_SEL      = (200, 160, 80)
TOOLBAR_BTN_SEL_EDGE = (255, 224, 128)
TOOLBAR_TEXT         = (58,  32,  10)

DATA_DIR   = "data"
ASSETS_DIR = "assets"
SPRITES_DIR = f"{ASSETS_DIR}/sprites"

COLOR_BG            = (30, 30, 40)
COLOR_CREATURE      = (120, 200, 140)
COLOR_SELECTED      = (255, 220, 50)
COLOR_CRITICAL      = (220, 60, 60)
COLOR_UI_BG         = (20, 20, 30)
COLOR_UI_TEXT       = (200, 200, 210)
COLOR_NEED_BAR_BG   = (60, 60, 70)
COLOR_HUNGER_BAR    = (230, 120, 50)
COLOR_HYGIENE_BAR   = (80, 180, 220)
COLOR_HAPPINESS_BAR = (240, 200, 60)
COLOR_ENERGY_BAR    = (100, 220, 160)
COLOR_FOOD_SOURCE   = (180, 230, 100)
COLOR_MESSAGE_BG    = (40, 40, 55)
COLOR_MESSAGE_TEXT  = (220, 240, 200)
