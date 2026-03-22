# =============================================================================
# agent/memory/associative_memory.py — swarm-alife
# Memoria asociativa: almacena ConceptNodes, recupera por relevancia y poignancy.
# Portado de digimon-alife, eliminadas dependencias de Flask/UE5.
# =============================================================================

import logging
from typing import Optional

from agent.memory.concept_node import ConceptNode
from config import MAX_ASSOCIATIVE_NODES

logger = logging.getLogger(__name__)


class AssociativeMemory:
    """
    Colección de ConceptNodes con recuperación por relevancia de keywords.

    - Capped en MAX_ASSOCIATIVE_NODES: cuando se supera, se eliminan los nodos
      con menor poignancy (los menos importantes).
    - Recuperación: intersección de keywords entre query y nodos almacenados,
      desempate por poignancy.
    """

    def __init__(self):
        self._nodes: list[ConceptNode] = []

    # --- Escritura ---

    def add(self, node: ConceptNode) -> None:
        """Añade un nodo. Si se supera el límite, elimina los de menor poignancy."""
        self._nodes.append(node)
        if len(self._nodes) > MAX_ASSOCIATIVE_NODES:
            self._trim()
        logger.debug(f"AssociativeMemory: added {node}")

    def add_raw(
        self,
        subject: str,
        predicate: str,
        object_: str,
        poignancy: float = 5.0,
        keywords: Optional[list[str]] = None,
        meta: Optional[dict] = None,
    ) -> ConceptNode:
        """Crea y añade un ConceptNode directamente desde sus componentes SPO."""
        node = ConceptNode(
            subject=subject,
            predicate=predicate,
            object_=object_,
            poignancy=poignancy,
            keywords=keywords or [],
            meta=meta or {},
        )
        self.add(node)
        return node

    # --- Lectura ---

    def retrieve(self, query_keywords: list[str], top_k: int = 5) -> list[ConceptNode]:
        """
        Devuelve los top_k nodos más relevantes para los keywords dados.
        Relevancia = número de keywords en común. Desempate por poignancy.
        """
        if not query_keywords:
            return self._top_by_poignancy(top_k)

        query_set = set(kw.lower() for kw in query_keywords)

        scored = []
        for node in self._nodes:
            node_kw_set = set(kw.lower() for kw in node.keywords)
            # También buscamos en el texto SPO directamente
            spo_words = set(
                f"{node.subject} {node.predicate} {node.object_}".lower().split()
            )
            overlap = len(query_set & (node_kw_set | spo_words))
            if overlap > 0:
                scored.append((overlap, node.poignancy, node))

        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return [node for _, _, node in scored[:top_k]]

    def get_all(self) -> list[ConceptNode]:
        """Devuelve todos los nodos ordenados por poignancy descendente."""
        return sorted(self._nodes, key=lambda n: n.poignancy, reverse=True)

    def count(self) -> int:
        return len(self._nodes)

    # --- Persistencia ---

    def to_list(self) -> list[dict]:
        """Serializa todos los nodos para JSON."""
        return [n.to_dict() for n in self._nodes]

    def from_list(self, data: list[dict]) -> None:
        """Carga nodos desde lista de dicts (deserialización JSON)."""
        self._nodes = [ConceptNode.from_dict(d) for d in data]
        logger.info(f"AssociativeMemory: loaded {len(self._nodes)} nodes")

    # --- Interno ---

    def _trim(self) -> None:
        """Elimina los nodos de menor poignancy hasta respetar MAX_ASSOCIATIVE_NODES."""
        self._nodes.sort(key=lambda n: n.poignancy, reverse=True)
        removed = len(self._nodes) - MAX_ASSOCIATIVE_NODES
        self._nodes = self._nodes[:MAX_ASSOCIATIVE_NODES]
        logger.debug(f"AssociativeMemory: trimmed {removed} low-poignancy nodes")

    def _top_by_poignancy(self, top_k: int) -> list[ConceptNode]:
        return sorted(self._nodes, key=lambda n: n.poignancy, reverse=True)[:top_k]

    def __repr__(self) -> str:
        return f"AssociativeMemory({len(self._nodes)} nodes)"
