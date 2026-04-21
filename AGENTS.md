# AGENTS.md — swarm-alife

AI agents working in this codebase should understand this architecture and development context.

## Architecture Overview

**swarm-alife** is a single-process 2D artificial life simulator. No external services or HTTP—everything runs locally with Pygame rendering and Ollama LLM integration.

### Core Philosophy

1. **LLM provides expression only**: Python owns all logic. LLM is invoked event-driven (async threads) when creatures cross critical need thresholds or write diaries—never in the main loop.
2. **Config is single source of truth**: Every constant (thresholds, timings, colors, needs rates) lives in `config.py`. Never hardcode values.
3. **Thread-safe persistence**: All file I/O uses atomic writes with a global lock (`utils._file_lock`) to prevent Windows permission errors on simultaneous reads/writes.
4. **One object, one creature**: Mutex pattern for world objects ensures only one creature uses a bath/ball/mine at a time.

### Three Core Loops

- **Game loop** (`core/game.py`): Updates creatures, world state, checks reproduction/LLM signals every frame.
- **Creature logic** (`agent/creature.py`): Needs decay, behavior tree selection, navigation, memory recording.
- **Social layer** (`agent/social.py`): Proximity-based happiness bonuses, hunger contagion, conversation triggering.

### Key Data Flows

```
Game.update() → for each creature:
  creature.update(delta, world, selected)
    → needs.update(delta) [decay by rate, apply social modifiers]
    → behavior selection (seek food? use object? wander? reproduce?)
    → navigation.step() [A* movement on 4-directional grid]
    → interaction_check() [if near object, use it atomically]
    → memory.record_event() [eating, depositing, conversations logged]
    → return signal (e.g., "hunger", "reproduce")

  if signal: trigger_llm_message(creature, signal) [async thread, respects rate limits]
```

**Persistence**: Creature state, world objects, and diary entries saved atomically to `data/` via `core/persistence.py`.

## Critical Patterns

### Needs Convention
- **Hunger**: 0=satiated → 100=starving (direction=+1, increases over time)
- **Hygiene**: 0=dirty → 100=clean (direction=-1, decreases over time)
- **Happiness**: 0=miserable → 100=very happy (direction=-1, decreases over time)

Each need has: `initial`, `rate` (decay per sec), `seek_threshold` (when creature starts seeking), `llm_threshold` (when LLM speaks).

### Behavior Architecture
Behaviors inherit from `agent/behavior/base.py`. Current: `SeekFoodBehavior`. To add behavior:
1. Subclass `BaseBehavior`
2. Implement `can_execute(creature)` and `execute(creature, delta)`
3. Instantiate in `Creature.__init__()` and call in `update()` based on creature state

### Object Interaction
World objects are defined in `world/objects.py` with types (TREE, BATH, BALL, STORE, MINE). Creatures interact via:
- `creature.target_obj`: current target
- `Object.use_by(creature)`: atomic mutex—only one creature at a time
- Cooldowns tracked per-creature per-object (`Object.last_use_by`)

### Memory System
`agent/memory/associative_memory.py` stores concept nodes (SPO: subject-predicate-object triples). Used for:
- Diary writing (LLM reflects on recent memories)
- Relevance scoring (decay by sim time)
- Max 100 nodes per creature (config: `MAX_ASSOCIATIVE_NODES`)

### LLM Rate Limiting
- Global cooldown: `LLM_GLOBAL_COOLDOWN` (5s default) between any two LLM calls
- Per-minute cap: `LLM_MAX_CALLS_PER_MIN` (10 default)
- Selected creature priority: bypass delays if `LLM_SELECTED_PRIORITY=True`
- Runs in background thread (`threading.Thread`) to keep game smooth

### Persistence Strategy
```python
# Save atomically (temp file → atomic rename)
atomic_write_json("data/world.json", state_dict)

# Load safely (with fallback)
state = load_json("data/colony.json", default=[])
```

All I/O protected by `threading.RLock()` in `utils.py`.

## Development Workflows

### Running the Game
```bash
pip install -r requirements.txt
ollama pull llama3.2:3b
python main.py
```

### Adding a New Creature Need
1. Add constants to `config.py` (rate, thresholds, LLM trigger, critical point)
2. Extend `Needs.__init__()` in `agent/needs/needs.py` (create `Need` object)
3. Add accessor method (e.g., `needs.hunger_level()`)
4. Update seek/LLM logic in `creature.update()` if new behaviors needed

### Adding a World Object Type
1. Add enum to `ObjType` in `world/objects.py`
2. Define metadata dicts: `OBJ_LABEL`, `OBJ_SIZE`, `OBJ_NEED`
3. Implement subclass of `GameObject` with `update()` and `use_by()` methods
4. Register in `WorldMap.generate()` for world initialization

### Debugging Common Issues
- **Creatures not moving**: Check `Navigator` path invalidation or grid bounds (`_MAX_COL`, `_MAX_ROW` in `creature.py`)
- **LLM not responding**: Verify Ollama running, model name in `config.OLLAMA_MODEL`, check `agent/communication.py` rate limits
- **Save errors on Windows**: Likely file lock contention; `atomic_write_json()` retries up to 5 times with backoff
- **Needs stuck**: Verify `SIM_SPEED` > 0, social modifiers not overriding decay in `agent/social.py`

## File Organization

| Path | Role |
|------|------|
| `config.py` | All tunable constants |
| `main.py` | Entry, Pygame init |
| `core/game.py` | Main loop, signal dispatch |
| `core/persistence.py` | Save/load, ID generation |
| `agent/creature.py` | Creature orchestrator, update dispatch |
| `agent/needs/*.py` | Need state, modifiers |
| `agent/behavior/*.py` | Decision tree modules |
| `agent/memory/*.py` | Associative memory, sim clock |
| `agent/communication.py` | LLM async invocation, rate limit |
| `agent/social.py` | Social modifiers, conversations |
| `world/objects.py` | World object definitions, mutex logic |
| `render/renderer.py` | Pygame drawing only (read-only to game state) |
| `data/` | Persistent JSON (colony, world, diary) |

## Localization

All UI strings in `locales.py`. Use `t(key, language)` for translation. Supports ES/EN.

---

**Last updated**: Apr 2026. Reference: README.md design principles, `config.py` for all constants.

