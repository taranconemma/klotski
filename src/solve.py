# solve.py. Resol el puzzle donant lloc a un fitxer amb els moviments (vegeu el format 
# a una secció més endavant) necessaris per moure peça a peça desde la posició fins 
# arribar a la final.



# solve.py. Resol el puzzle donant lloc a un fitxer amb els moviments necessaris
# per moure peça a peça des de la posició inicial fins arribar a la final.

"""
Carrega el graf generat per graph.py i troba el camí mínim (BFS) des de
l'estat inicial fins a qualsevol estat final. Guarda els moviments en
format .sol.json.

Ús:
    python src/solve.py puzzles/sample1.graphml
    python src/solve.py puzzles/sample1.graphml -o solucio.sol.json
"""

import json
import sys
from pathlib import Path

import graph_tool.all as gt  # type: ignore[import-untyped]

from graph import state_key
from puzzle import Puzzle


def solve(g: gt.Graph, puzzle: Puzzle) -> list[tuple[int, str, int]] | None:
    """
    Troba el camí mínim des del node inicial fins a un node final.

    Retorna la llista de moviments [(peça, direcció, distància), ...]
    o None si el puzzle no té solució.
    """
    # Trobem el node inicial i els nodes finals
    start_v = None
    goal_vs = []
    for v in g.vertices():
        if g.vp["is_start"][v]:
            start_v = v
        if g.vp["is_goal"][v]:
            goal_vs.append(v)

    if start_v is None or not goal_vs:
        return None

    # BFS sobre el graf per trobar el camí mínim
    # (graph-tool té shortest_path però BFS manual ens dona el camí d'arestes)
    dist, pred = gt.shortest_distance(g, start_v, pred_map=True)

    # Triem el node final més proper
    best_goal = min(goal_vs, key=lambda v: dist[v])
    if dist[best_goal] == 2**31 - 1:  # no assolible
        return None

    # Reconstruïm el camí d'arestes des de start fins a best_goal
    path_vertices = []
    v = best_goal
    while v != start_v:
        path_vertices.append(v)
        v = g.vertex(pred[v])
    path_vertices.append(start_v)
    path_vertices.reverse()

    # Convertim el camí de vèrtexs a moviments (peça, direcció, distància)
    moves = []
    for i in range(len(path_vertices) - 1):
        src = path_vertices[i]
        tgt = path_vertices[i + 1]

        # Busquem l'aresta entre src i tgt
        e = g.edge(src, tgt)
        piece     = int(g.ep["piece"][e])
        direction = str(g.ep["direction"][e])
        distance  = int(g.ep["distance"][e])
        moves.append((piece, direction, distance))

    return moves


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Ús: python {sys.argv[0]} <puzzle.graphml> [-o solucio.sol.json]")
        sys.exit(1)

    graphml_path = Path(sys.argv[1])
    if not graphml_path.exists():
        print(f"Error: no s'ha trobat {graphml_path}")
        sys.exit(1)

    # Fitxer de sortida
    if "-o" in sys.argv:
        output_path = Path(sys.argv[sys.argv.index("-o") + 1])
    else:
        output_path = graphml_path.with_suffix("").with_suffix(".sol.json")

    if output_path.exists():
        print(f"✅ La solució ja existeix: {output_path}")
        print("   (Ometent la cerca...)")
        sys.exit(0)

    print(f"Carregant graf: {graphml_path}")
    g = gt.load_graph(str(graphml_path))
    print(f"Nodes: {g.num_vertices()}, Arestes: {g.num_edges()}")

    puzzle = Puzzle.from_json(g.gp["puzzle"])

    moves = solve(g, puzzle)

    if moves is None:
        print("El puzzle no té solució.")
        sys.exit(1)

    print(f"Solució trobada: {len(moves)} moviments")

    # Format: [[peça, direcció, distància], ...]
    output = [[p, d, dist] for p, d, dist in moves]
    Path(output_path).write_text(json.dumps(output))
    print(f"Solució guardada a: {output_path}")