"""
Carrega el graf generat per graph.py i troba el camí mínim (BFS) des de
l'estat inicial fins a qualsevol estat final. Guarda els moviments en
format .sol.json.

Ús:     python src/solve.py puzzles/nom_puzzle.graphml
"""

import json
import sys
from pathlib import Path

from graph_tool.all import Graph, Vertex, find_vertex, shortest_distance, shortest_path, load_graph


def solve(g: Graph) -> list[tuple[int, str, int]] | None:
    """
    Troba el camí mínim des del node inicial fins a un dels nodes finals.

    Retorna la llista de moviments [(peça, direcció, distància), ...]
    o None si el puzzle no té solució.
    """

    # Trobem el node inicial i els nodes finals
    starts: list[Vertex] = find_vertex(g, g.vp["is_start"], True)
    goals: list[Vertex] = find_vertex(g, g.vp["is_goal"], True)

    # Si no hi ha nodes inicials o finals, retornem None
    if not starts or not goals:
        return None

    # Triem el primer node inicial i fem BFS per calcular totes les distàncies
    start_v = starts[0]
    dist = shortest_distance(g, start_v)

    # Triem l'objectiu més proper
    best_goal = min(goals, key=lambda v: dist[v])

    # Reconstruïm el camí i retornem els moviments en el format adient
    _, path_edges = shortest_path(g, start_v, best_goal)
    return [(int(g.ep["piece"][e]), str(g.ep["direction"][e]), int(g.ep["distance"][e])) for e in path_edges]



def main() -> None:
    graphml_path = Path(sys.argv[1])

    # El fitxer de sortida es generarà automàticament canviant l'extensió a .sol.json
    output_path = graphml_path.with_suffix("").with_suffix(".sol.json")

    # Si la solució ja existeix, no fem res
    if output_path.exists():
        print("La solució ja existeix.")
        return

    g = load_graph(str(graphml_path))
    # Mostrem per pantalla alguna informació rellevant del graf
    print(f"Nodes: {g.num_vertices()}, Arestes: {g.num_edges()}")

    moves = solve(g)

    if moves is None:
        print("El puzzle no té solució.")
        return

    print(f"Solució: {len(moves)} moviments")

    # Escrivim la solució al fitxer de sortida
    # Format: [[peça, direcció, distància], ...]
    Path(output_path).write_text(json.dumps([[p, d, dist] for p, d, dist in moves]))


if __name__ == "__main__":
    main()