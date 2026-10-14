from collections import defaultdict
from collections.abc import Iterable
from uuid import UUID


def has_cycle(
    edges: Iterable[tuple[UUID, UUID]],
    new_edge: tuple[UUID, UUID] | None = None,
) -> bool:
    """Détecte un cycle dans un graphe orienté de tâches."""

    graph: dict[UUID, set[UUID]] = defaultdict(set)
    for source, target in edges:
        graph[source].add(target)
    if new_edge is not None:
        graph[new_edge[0]].add(new_edge[1])

    visiting: set[UUID] = set()
    visited: set[UUID] = set()

    def visit(node: UUID) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        if any(visit(child) for child in graph[node]):
            return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in list(graph))
