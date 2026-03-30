# swarm-alife

A 2D top-down simulation of creatures with emergent social behaviour, internal needs, and event-driven LLM communication.

Technical continuation of [digimon-alife](https://github.com/fransolerc/digimon-alife). Same LLM/logic separation principle, new context: multiple creatures sharing a world with social interaction and autonomous behaviour.

## Concept

Creatures live together in a shared 2D space. Each one maintains an internal state of needs (hunger, hygiene, happiness) that evolves over time. Emergent behaviour arises from simple proximity rules and mutual influence. The LLM only speaks when a creature crosses a critical need threshold or writes in its diary.

Creatures are born one at a time and reproduce asexually when healthy enough — offspring inherit their parent's needs with slight variance. The colony grows indefinitely.

## Stack

| Component | Technology |
|---|---|
| Rendering + input | Pygame |
| Agent logic | Pure Python |
| Pathfinding | A* over grid cells (diagonal support for targets) |
| User communication | Ollama + Llama 3.2 3B (event-driven) |
| Persistent Storage | Atomic JSON writes with thread-safety (Windows optimized) |
| No HTTP, no Flask, no external engine | Everything in a single process |

## Project structure

```
swarm-alife/
├── main.py                        # Entry point, Pygame loop
├── config.py                      # All constants centralised
├── locales.py                     # Localised strings (EN/ES)
├── utils.py                       # Shared utilities (Thread-safe file I/O)
├── requirements.txt
├── agent/
│   ├── creature.py                # Creature orchestrator + A* navigation
│   ├── needs.py                   # Needs system (Hunger, Hygiene, Happiness)
│   ├── social.py                  # Emergent social behaviour
│   ├── communication.py           # Event-driven LLM messages
│   ├── writing.py                 # Diary writing system (Asynchronous)
│   └── memory/
│       ├── concept_node.py        # SPO memory unit
│       ├── associative_memory.py  # Relevance-based retrieval
│       └── sim_clock.py           # Simulated clock
├── world/
│   ├── objects.py                 # World objects, Apple/Wood/Gem systems
│   ├── placement.py               # Drag & drop placement state
│   └── progression.py             # Level progression singleton
├── render/
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
| Tab | Open/Close Diary |
| F | Feed (selected or all) |
| D | Shower (selected or all) |
| J | Play (selected or all) |
| G | Save state |
| ESC | Quit |

## World objects

| Object | Size | Effect |
|---|---|---|
| Tree | 1×1 | Blocks movement. ~60% chance to grow apples. Choppable with axe (yields wood). |
| Bath | 1×1 | Restores hygiene. Creatures seek it autonomously when dirty. |
| Ball | 1×1 | Boosts happiness. Creatures seek it autonomously when unhappy. |
| Mine | 1×1 | Placed over deposits. Creatures extract gems for diary writing. |
| Store | 2×2 | Receives apples, wood and gems carried by creatures. |

Apples fall to the ground when a tree is shaken, rot after 90 seconds, and are picked up by creatures. Chopped trees leave a stump that yields wood. Gems are infinite but have a per-creature extraction cooldown.

## Creature behaviour

Creatures navigate via A* pathfinding. They wander autonomously and seek world objects when a need crosses its seeking threshold. They can interact with objects from adjacent cells (including diagonals) to avoid getting stuck.

### Autonomous carrying & Resources

When comfortable (`CARRY_NEED_THRESHOLD`), creatures will autonomously:
1. Pick up ground apples or harvest them from trees.
2. Extract gems from mines.
3. Pick up wood from stumps.
Everything is delivered to the nearest **Store**.

### Diary Writing

Creatures can spend **3 gems** from a store to write a diary entry. This process uses the LLM asynchronously to reflect on their recent memories (eating, depositing, interactions). The diary is saved in `data/diary.json` and `data/diary.md`.

## Reproduction

A creature can divide when it has lived long enough and its hunger, hygiene, and happiness are above a health threshold. Offspring inherit needs with slight variance.

## LLM communication

The LLM is invoked:
1. When a creature crosses a critical need threshold (bubble message).
2. When a creature decides to write in its diary (spending gems).
Both processes run in background threads to ensure smooth gameplay.

## Design principles

1. **LLM provides expression, Python owns all logic**.
2. **Thread-safe persistence**: Atomic writes with locks to prevent Windows permission errors.
3. **Diagonal interaction**: Creatures can use objects from any surrounding cell.
4. **Centralised config**: All balance constants in `config.py`.

Inspired by [Generative Agents (Park et al., 2023)](https://arxiv.org/abs/2304.03442).
