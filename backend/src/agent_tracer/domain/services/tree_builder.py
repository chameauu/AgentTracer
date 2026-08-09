from __future__ import annotations
from collections import defaultdict
from ..entities import TraceNode
from ..value_objects import SpanType


class TreeBuilder:
    """Pure functions for assembling and traversing trace trees."""

    @staticmethod
    def build_tree(nodes: list[TraceNode]) -> list[TraceNode]:
        """Link children to parents and return the root nodes.
        Nodes may arrive in any order. A node whose parent_id is not
        present in the list is treated as a root (orphan-safe).
        """
        by_id = {node.id: node for node in nodes}
        # Pass 1: clear children so build_tree is idempotent (safe to call
        # twice on the same nodes). Must happen before linking, otherwise a
        # parent processed after its children would wipe their links.
        for node in nodes:
            node.children.clear()
        # Pass 2: link children to parents.
        roots: list[TraceNode] = []
        for node in nodes:
            if node.parent_id and node.parent_id in by_id:
                by_id[node.parent_id].children.append(node)
            else:
                roots.append(node)
        return roots

    @staticmethod
    def flatten_tree(roots: list[TraceNode]) -> list[TraceNode]:
        """Depth-first traversal of the tree(s), roots first."""
        result: list[TraceNode] = []

        def visit(node: TraceNode) -> None:
            result.append(node)
            for child in node.children:
                visit(child)

        for root in roots:
            visit(root)
        return result

    @staticmethod
    def find_node(roots: list[TraceNode], node_id: str) -> TraceNode | None:
        """Search the tree(s) for a node by id."""
        for node in TreeBuilder.flatten_tree(roots):
            if node.id == node_id:
                return node
        return None

    @staticmethod
    def count_nodes(roots: list[TraceNode]) -> int:
        """Total number of nodes across all trees."""
        return len(TreeBuilder.flatten_tree(roots))

    @staticmethod
    def count_by_type(roots: list[TraceNode]) -> dict[str, int]:
        """Histogram of span types, e.g. {'step': 3, 'tool_call': 5}."""
        counts: dict[str, int] = defaultdict(int)
        for node in TreeBuilder.flatten_tree(roots):
            counts[node.span_type.value] += 1
        return dict(counts)
