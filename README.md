# swarm-alife

A 2D top-down simulation of creatures with emergent social behaviour, internal needs, and event-driven LLM communication.

Technical continuation of [digimon-alife](https://github.com/fransolerc/digimon-alife). Same LLM/logic separation principle, new context: multiple creatures sharing a world with social interaction and autonomous behaviour.

## Concept

Creatures live together in a shared 2D space. Each one maintains an internal state of needs (hunger, hygiene, happiness, energy) that evolves over time. Emergent behaviour arises from simple proximity rules and mutual influence. The LLM only speaks when a creature crosses a critical need threshold.

Creatures are born one at a time and reproduce asexually when healthy enough — offspring inherit their parent's needs with slight variance. The colony grows indefinitely.

## Stack

| Component | Technology |
|---|---|
| Rendering + input | Pygame |
| Agent logic | Pure Python |
| User communication | Ollama + Llama 3.2 3B (event-driven) |
| No HTTP, no Flask, no external engine | Everything in a single process |

## Project structure

```
swarm-alife/
├── main.py                        # Entry point, Pygame loop
├── config.py                      # All constants centralised
├── locales.py                     # Localised strings (EN/ES)
├── utils.py                       # Shared utilities
├── requirements.txt
├── agent/
│   ├── creature.py                # Creature orchestrator
│   ├── needs.py                   # Needs system
│   ├── social.py                  # Emergent social behaviour
│   ├── communication.py           # Event-driven LLM (separate thread)
│   └── memory/
│       ├── concept_node.py        # SPO memory unit
│       ├── associative_memory.py  # Relevance-based retrieval
│       └── sim_clock.py           # Simulated clock
├── world/
│   ├── objects.py                 # World objects, apple system, WorldMap
│   └── placement.py               # Drag & drop placement state
├── render/
│   └── renderer.py                # Pygame renderer (drawing only)
└── data/                          # Per-creature persistent memory (not tracked)
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
| Keys 1–4 | Select object type in palette |
| F | Feed (selected or all) |
| D | Shower (selected or all) |
| J | Play (selected or all) |
| S | Sleep (selected only) |
| G | Save state |
| ESC | Quit |

## World objects

| Object | Effect |
|---|---|
| Tree | Blocks movement. ~60% chance to grow apples. Shake to drop them. |
| Bath | Restores hygiene. Player-initiated only. |
| Ball | Boosts happiness. Creatures seek it autonomously when unhappy. |
| Bed | Restores energy. Creatures seek it autonomously when tired. |

Apples fall to the ground when a tree is shaken, rot after 30 seconds, and are picked up automatically by hungry creatures nearby.

## Creature behaviour

Creatures wander autonomously and seek world objects when a need crosses its seeking threshold. When they reach an object they stop for a few seconds before moving on. Behaviour is influenced by proximity to neighbours — nearby hungry creatures spread anxiety; being close to others boosts happiness.

Visual states reflect internal needs: normal (green), hungry (yellow), sad (blue), tired (grey), critical (red with pulsing ring).

## Reproduction

A creature can divide when it has lived long enough and all its needs are above a health threshold. The offspring spawns nearby, inherits the parent's needs with slight variance, and belongs to the next generation. There is no population cap.

## LLM communication

The LLM is never polled continuously. It is invoked only when a creature crosses a critical need threshold and a per-creature cooldown has elapsed. Responses are generated in a background thread so the simulation never blocks. On failure, a localised fallback message is used — errors are always logged explicitly.

## Design principles

1. **LLM provides expression, Python owns all logic** — no exceptions
2. All thresholds and constants centralised in `config.py`
3. Localised strings in `locales.py`
4. Per-creature persistent memory in `data/` via atomic writes
5. Explicit LLM error logging — never silent

## Research goals

- Emergent collective behaviour from simple interaction rules
- State contagion between agents via proximity
- LLM as an occasional communication channel, not a simulation engine
- Cleaner and more controllable base than digimon-alife for experimenting with agent architectures

Inspired by [Generative Agents (Park et al., 2023)](https://arxiv.org/abs/2304.03442) and the Thronglets from Black Mirror.
