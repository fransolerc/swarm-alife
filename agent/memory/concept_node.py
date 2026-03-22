# =============================================================================
# agent/memory/concept_node.py — swarm-alife
# Unidad atómica de memoria estructurada en formato SPO (Subject-Predicate-Object).
# Portado de digimon-alife, eliminadas dependencias de Flask/UE5.
# =============================================================================

import time
import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ConceptNode:
    """
    Unidad de memoria en formato Sujeto-Predicado-Objeto.

    Ejemplos:
        subject="yo", predicate="siento", object_="hambre"
        subject="usuario", predicate="me_dio", object_="comida"
        subject="criatura_3", predicate="estaba_cerca_cuando", object_="yo_lloraba"
    """
    subject:    str
    predicate:  str
    object_:    str

    # Relevancia emocional/importancia (0–10). Valores altos sobreviven más tiempo.
    poignancy:  float = 5.0

    # Timestamp de simulación en el que se creó el nodo (segundos)
    created_at: float = field(default_factory=time.time)

    # Identificador único
    node_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    # Keywords para recuperación por relevancia
    keywords: list[str] = field(default_factory=list)

    # Metadata opcional (ej: hora simulada, contexto)
    meta: dict = field(default_factory=dict)

    def to_text(self) -> str:
        """Representación legible para incluir en prompts LLM."""
        return f"{self.subject} {self.predicate} {self.object_}"

    def to_dict(self) -> dict:
        """Serialización para persistencia JSON."""
        return {
            "node_id":    self.node_id,
            "subject":    self.subject,
            "predicate":  self.predicate,
            "object_":    self.object_,
            "poignancy":  self.poignancy,
            "created_at": self.created_at,
            "keywords":   self.keywords,
            "meta":       self.meta,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ConceptNode":
        """Deserialización desde JSON."""
        return cls(
            subject    = data["subject"],
            predicate  = data["predicate"],
            object_    = data["object_"],
            poignancy  = data.get("poignancy", 5.0),
            created_at = data.get("created_at", time.time()),
            node_id    = data.get("node_id", str(uuid.uuid4())[:8]),
            keywords   = data.get("keywords", []),
            meta       = data.get("meta", {}),
        )

    def __repr__(self) -> str:
        return (
            f"ConceptNode(id={self.node_id!r}, "
            f"spo='{self.subject} | {self.predicate} | {self.object_}', "
            f"poignancy={self.poignancy:.1f})"
        )
