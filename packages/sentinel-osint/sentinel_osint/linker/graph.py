

from __future__ import annotations

import networkx as nx


class IdentityGraph:
    """NetworkX-backed identity graph. Nodes = RawRecord IDs, edges = discovered links."""

    def __init__(self) -> None:
        self._g = nx.Graph()

    def add_record(self, record_id: str, metadata: dict) -> None:
        self._g.add_node(record_id, **metadata)

    def link(self, id_a: str, id_b: str, reason: str, confidence: float) -> None:
        """Add or strengthen a link between two records."""
        if confidence < 0.20:
            return  # Never link below 0.20 — risk of false merges
        if self._g.has_edge(id_a, id_b):
            existing = self._g[id_a][id_b]["confidence"]
            self._g[id_a][id_b]["confidence"] = max(existing, confidence)
        else:
            self._g.add_edge(id_a, id_b, reason=reason, confidence=confidence)

    def profiles(self) -> list[list[str]]:
        """Return connected components with 2+ nodes (each = one profile)."""
        return [list(c) for c in nx.connected_components(self._g) if len(c) >= 2]

    @property
    def node_count(self) -> int:
        return self._g.number_of_nodes()

    @property
    def edge_count(self) -> int:
        return self._g.number_of_edges()
