# swarm-alife

A 2D top-down artificial life simulation with autonomous creatures, emergent social behaviour, internal needs, and event-driven LLM communication via a local model.

Technical continuation of [digimon-alife](https://github.com/fransolerc/digimon-alife). Same LLM/logic separation principle, new context: multiple creatures sharing a world with social interaction and autonomous behaviour.

## Concept

Creatures live together in a shared 2D space. Each one maintains an internal state of needs (hunger, hygiene, happiness) that evolves over time. Emergent behaviour arises from simple proximity rules and mutual influence. The LLM only speaks when a creature crosses a critical need threshold or writes in its diary.

Creatures are born one at a time and reproduce asexually when healthy enough — offspring inherit their parent's needs with slight variance. The colony grows indefinitely.

## Stack

| Component | Technology |
|---|---|
| Rendering + input | Pygame |
| Agent logic | Pure Python |
| Pathfinding | A* over a 4-directional grid |
| LLM communication | Ollama + Llama 3.2 3B (event-driven) |
| Persistent storage | Atomic JSON writes with thread-safety (Windows optimised) |
| No HTTP, no Flask, no external engine | Everything in a single process |

## Project structure

```
swarm-alife/
├── main.py                        # Entry point
├── config.py                      # All constants centralised
├── locales.py                     # Localised strings (EN/ES)
├── utils.py                       # Shared utilities (thread-safe file I/O)
├── requirements.txt
├── core/                          # Core game systems
│   ├── game.py                    # Main game loop controller
│   ├── persistence.py             # Save/load state & ID generation
│   └── input_handler.py           # Keyboard & mouse input handling
├── agent/                         # Agent logic
│   ├── creature.py                # Creature orchestrator
│   ├── navigation.py              # A* pathfinding & grid movement
│   ├── inventory.py               # Resource carrying system
│   ├── needs/                     # Needs package
│   │   ├── needs.py               # Needs container (hunger/hygiene/happiness)
│   │   ├── core.py                # Single need with thresholds
│   │   └── modifiers.py           # Social need modifiers
│   ├── behavior/                  # Behavior modules
│   │   ├── base.py                # Base behavior class
│   │   ├── seek_food.py           # Food seeking strategy
│   │   └── carry_resource.py      # Resource transport behavior
│   ├── social.py                  # Emergent social behaviour
│   ├── communication.py           # Event-driven LLM messages
│   ├── writing.py                 # Diary writing system (asynchronous)
│   └── memory/
│       ├── concept_node.py        # SPO memory unit
│       ├── associative_memory.py  # Relevance-based retrieval
│       └── sim_clock.py           # Simulated clock
├── world/                         # World simulation
│   ├── objects.py                 # World objects, apple/wood/gem systems
│   ├── placement.py               # Drag & drop placement state
│   └── progression.py             # Level progression singleton
├── render/                        # Rendering layer
│   └── renderer.py                # Pygame renderer (drawing only)
└── data/                          # Persistent memory, world state and diary
```

## Installation

```bash
pip install -r requirements.txt
ollama pull llama3.2:3b
python main.py
```

## Controls

| Input | Action |
|---|---|
| Left click on creature | Select creature |
| Left click on tree | Shake tree (drop apples) |
| Drag from palette → world | Place object |
| Right click on object | Remove object |
| Axe tool (palette) | Toggle axe mode |
| Left click on tree (axe mode) | Chop tree |
| Tab | Open/close diary |
| F | Feed selected creature, or all if none selected |
| D | Shower selected creature, or all if none selected |
| J | Play with selected creature, or all if none selected |
| G | Save state |
| ESC | Quit |

## World objects

| Object | Size | Effect |
|---|---|---|
| Tree | 1×1 | Blocks movement. ~60% chance to grow apples. Choppable with axe (yields wood). |
| Bath | 1×1 | Restores hygiene. Creatures seek it autonomously when dirty. |
| Ball | 1×1 | Boosts happiness. Creatures seek it autonomously when unhappy. |
| Mine | 1×1 | Placed over gem deposits. Creatures extract gems autonomously. |
| Store | 2×2 | Receives apples, wood and gems carried by creatures. |

Apples fall to the ground when a tree is shaken, rot after 90 seconds, and are picked up by creatures. Chopped trees leave a stump that yields wood. Gem deposits are fixed at world generation; placing a mine over one enables extraction. Gems are infinite per mine but have a per-creature extraction cooldown.

## Creature behaviour

Creatures navigate via A* pathfinding on a 4-directional grid. They wander autonomously and seek world objects when a need crosses its seeking threshold. Interaction range uses Euclidean distance, so creatures can use objects from any adjacent cell including diagonals.

### Needs

Each creature tracks three needs:

| Need | Direction | Triggers seeking at | LLM message at |
|---|---|---|---|
| Hunger | Increases over time | 45 | 75 |
| Hygiene | Decreases over time | 20 | 25 |
| Happiness | Decreases over time | 20 | 20 |

### Autonomous carrying & resources

When all needs are comfortable (`CARRY_NEED_THRESHOLD`), creatures will autonomously:

1. Pick up ground apples or harvest them from trees.
2. Extract gems from mines.
3. Pick up wood from stumps.

Everything is delivered to the nearest store.

### Diary writing

Creatures can spend gems from a store to write a diary entry. The LLM reflects on their recent associative memories (eating, depositing, interactions). The diary is saved to `data/diary.json` and `data/diary.md`, and readable in-game via the Tab overlay.

Diary writing is controlled by `WRITING_MODE` in `config.py`:

| Value | Behaviour |
|---|---|
| `"disabled"` | No diary entries generated |
| `"selected_only"` | Only the currently selected creature writes |
| `"full"` | All creatures write (high LLM load) |

## Reproduction

A creature divides when it has lived long enough and its hunger, hygiene, and happiness are above a health threshold. Offspring inherit the parent's needs with slight random variance.

## Social behaviour

Nearby creatures influence each other passively: proximity raises happiness, and being near a critically hungry creature generates mild anxiety. Creatures can also spend gems to hold short conversations, which are recorded in their associative memories and can trigger diary entries.

## LLM communication

The LLM is invoked in two situations:

1. When a creature crosses a critical need threshold (short bubble message).
2. When a creature decides to write in its diary (spending gems from a store).

Both run in background threads to keep the game loop smooth. A global cooldown and per-minute call limit prevent saturation.

## Design principles

1. **LLM provides expression, Python owns all logic.**
2. **Thread-safe persistence**: atomic writes with locks to prevent permission errors on Windows.
3. **Single source of truth**: all balance constants in `config.py`, all visible strings in `locales.py`.
4. **Centralised object mutex**: only one creature can use a world object at a time.

Inspired by [Generative Agents (Park et al., 2023)](https://arxiv.org/abs/2304.03442).
