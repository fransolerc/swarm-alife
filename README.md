# swarm-alife

Simulación 2D de criaturas con comportamiento social emergente, necesidades internas y comunicación LLM event-driven.

Continuación técnica de [digimon-alife](https://github.com/fransolerc/digimon-alife). Misma separación LLM/lógica, nuevo contexto: múltiples criaturas en un espacio compartido con interacción social.

## Concepto

Varias criaturas conviven en un espacio 2D top-down. Cada una mantiene un estado interno de necesidades (hambre, higiene, felicidad, energía) que evoluciona con el tiempo. El comportamiento emergente surge de reglas simples de proximidad e influencia mutua. El LLM solo habla cuando una criatura supera un umbral crítico de necesidad.

## Stack

| Componente | Tecnología |
|---|---|
| Rendering + input | Pygame |
| Lógica de agentes | Python puro |
| Comunicación con usuario | Ollama + Llama 3.2 3B (event-driven) |
| Sin HTTP, sin Flask, sin motor externo | Todo en el mismo proceso |

## Estructura

```
swarm-alife/
├── main.py                        # Entry point, loop Pygame
├── config.py                      # Todas las constantes centralizadas
├── locales.py                     # Strings ES/EN
├── utils.py                       # Utilidades compartidas
├── requirements.txt
├── agent/
│   ├── creature.py                # Orquestador de criatura
│   ├── needs.py                   # Sistema de necesidades
│   ├── social.py                  # Comportamiento social emergente
│   ├── communication.py           # LLM event-driven (hilo separado)
│   └── memory/
│       ├── concept_node.py        # Unidad SPO de memoria
│       ├── associative_memory.py  # Recuperación por relevancia
│       └── sim_clock.py           # Reloj simulado
├── render/
│   └── renderer.py                # Rendering Pygame (solo dibuja)
├── data/                          # Memoria persistente por criatura (no versionado)
└── assets/
    └── sprites/                   # Sprites pixel art
```

## Instalación

```bash
pip install -r requirements.txt
ollama pull llama3.2:3b
python main.py
```

## Controles

| Tecla | Acción |
|---|---|
| Clic izquierdo | Seleccionar criatura |
| F | Alimentar (seleccionada o todas) |
| D | Duchar (seleccionada o todas) |
| J | Jugar (seleccionada o todas) |
| S | Dormir (solo seleccionada) |
| G | Guardar estado |
| ESC | Salir |

## Principios de diseño

1. **LLM proporciona expresión, Python maneja la lógica** — sin excepciones
2. Umbrales y constantes centralizados en `config.py`
3. Strings localizados en `locales.py`
4. Memoria persistente por criatura en `data/`
5. Escritura atómica para evitar corrupción
6. Logging explícito de errores LLM, nunca silencioso

## Investigación

- Comportamiento emergente colectivo a partir de reglas simples
- Contagio de estados entre agentes por proximidad
- LLM como canal de comunicación ocasional, no como motor del sistema

Inspirado en [Generative Agents (Park et al., 2023)](https://arxiv.org/abs/2304.03442) y los Thronglets de Black Mirror.
