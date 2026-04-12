"""
Visualitzador 3D del graf d'estats d'un trencaclosques.

Carrega un fitxer .graphml generat per graph.py, el converteix
al format JSON que espera 3d-force-graph, i serveix una pàgina
HTML amb la visualització 3D Force-Directed.

Opcionalment, si es passa un fitxer .sol.json generat per solve.py,
es ressalten les arestes del camí de la solució en groc.

Ús:
    python 3D_view.py <graf.graphml> [<solució.sol.json>] [--port PORT]
"""

from __future__ import annotations

import json
import sys
import threading
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

import graph_tool.all as gt  # type: ignore[import-untyped]

from graph import state_key, StateKey
from logic import Move, replay_moves
from puzzle import Puzzle

def solution_edges(
    g: gt.Graph, puzzle: Puzzle, moves: list[Move],
) -> set[tuple[str, str]]:
    """
    Retorna el conjunt d'arestes (source_id, target_id) del camí
    de la solució, reproduint els moviments des de l'estat inicial.
    """
    state_prop = g.vp["state"]

    # Mapa clau canònica → id de vèrtex
    key_to_id: dict[StateKey, str] = {}
    for v in g.vertices():
        key_to_id[state_key(puzzle, state_prop[v])] = str(int(v))

    states = replay_moves(puzzle, moves)
    edges: set[tuple[str, str]] = set()
    for i in range(len(states) - 1):
        src = key_to_id[state_key(puzzle, states[i])]
        tgt = key_to_id[state_key(puzzle, states[i + 1])]
        edges.add((src, tgt))

    return edges


def graphml_to_json(
    g: gt.Graph,
    path_edges: set[tuple[str, str]] | None = None,
) -> dict:
    """Converteix un graf graph_tool al format JSON de 3d-force-graph."""
    is_goal = g.vp.get("is_goal")
    is_start = g.vp.get("is_start")

    nodes = []
    for v in g.vertices():
        node: dict = {"id": str(int(v))}
        if is_goal is not None:
            node["is_goal"] = bool(is_goal[v])
        if is_start is not None:
            node["is_start"] = bool(is_start[v])
        nodes.append(node)

    links = []
    for e in g.edges():
        src = str(int(e.source()))
        tgt = str(int(e.target()))
        link: dict = {"source": src, "target": tgt}
        if path_edges is not None:
            link["is_path"] = (src, tgt) in path_edges or (tgt, src) in path_edges
        links.append(link)

    return {"nodes": nodes, "links": links}


VIEWER_HTML = """\
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Graf d'estats — Visualitzador 3D</title>
    <style>
        body { margin: 0; overflow: hidden; }
        #info {
            position: absolute;
            top: 10px;
            left: 10px;
            color: #ccc;
            font-family: sans-serif;
            font-size: 13px;
            pointer-events: none;
            text-shadow: 0 0 4px #000;
        }
    </style>
    <script src="https://cdn.jsdelivr.net/npm/3d-force-graph@1"></script>
</head>
<body>
    <div id="3d-graph"></div>
    <div id="info"></div>

    <script>
        fetch("./graph.json")
            .then(r => r.json())
            .then(data => {
                const hasGoals = data.nodes.some(n => n.is_goal);
                const hasPath = data.links.some(l => l.is_path);
                const nPath = hasPath ? data.links.filter(l => l.is_path).length : 0;
                const info = document.getElementById("info");
                info.textContent =
                    data.nodes.length + " nodes, " +
                    data.links.length + " links" +
                    (hasGoals ? " (goal nodes in green)" : "") +
                    (hasPath ? " — solution: " + nPath + " moves (yellow)" : "");

                const Graph = new ForceGraph3D(document.getElementById("3d-graph"))
                    .graphData(data)
                    .d3AlphaDecay(0.005)
                    .d3VelocityDecay(0.3)
                    .cooldownTime(30000)
                    .warmupTicks(100)
                    .backgroundColor("#000000")
                    .nodeRelSize(8)
                    .nodeVal(n => n.is_start ? 5 : n.is_goal ? 3 : 1)
                    .nodeColor(n => n.is_start ? "#ffcc00" : n.is_goal ? "#00cc66" : "#4466cc")
                    .nodeOpacity(0.9)
                    .linkColor(l => hasPath && l.is_path ? "#ffcc00" : "#334488")
                    .linkOpacity(l => hasPath && l.is_path ? 1.0 : 0.7)
                    .linkWidth(l => hasPath && l.is_path ? 2 : 0.5);
            });
    </script>
</body>
</html>
"""


class ViewerHandler(SimpleHTTPRequestHandler):
    """Handler que serveix el HTML i el JSON del graf en memòria."""

    graph_json: str = "{}"

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            content = VIEWER_HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == "/graph.json":
            content = self.graph_json.encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        pass  # Silencia els logs per defecte


def serve_graph(
    graphml_path: str,
    solution_path: str | None = None,
    port: int = 8000,
) -> None:
    """Carrega el graf, arrenca el servidor i obre el navegador."""
    path = Path(graphml_path)
    if not path.exists():
        print(f"Error: no s'ha trobat {path}", file=sys.stderr)
        sys.exit(1)

    print(f"Carregant {path}...")
    g = gt.load_graph(str(path))
    print(f"Graf: {g.num_vertices()} vèrtexs, {g.num_edges()} arestes")

    puzzle = Puzzle.from_json(g.gp["puzzle"])

    path_edges: set[tuple[str, str]] | None = None
    if solution_path is not None:
        sol_path = Path(solution_path)
        if not sol_path.exists():
            print(f"Error: no s'ha trobat {sol_path}", file=sys.stderr)
            sys.exit(1)
        # El format és [peça, direcció, distància]. Si només hi ha 2 elements,
        # la distància és implícitament 1 (compatibilitat amb el format antic).
        raw_moves = json.loads(sol_path.read_text())
        moves = [(m[0], m[1], m[2] if len(m) >= 3 else 1) for m in raw_moves]
        path_edges = solution_edges(g, puzzle, moves)
        print(f"Solució: {len(moves)} moviments")

    data = graphml_to_json(g, path_edges)
    ViewerHandler.graph_json = json.dumps(data)

    while True:
        try:
            server = HTTPServer(("localhost", port), ViewerHandler)
            break
        except OSError:
            port += 1
    url = f"http://localhost:{port}"
    print(f"Servidor a {url}  (Ctrl+C per aturar)")

    threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nAturat.")
        server.server_close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Visualitzador 3D del graf d'estats d'un trencaclosques",
    )
    parser.add_argument("graphml", help="Fitxer .graphml generat per graph.py")
    parser.add_argument("solution", nargs="?", default=None, help="Fitxer .sol.json generat per solve.py (opcional)")
    parser.add_argument("--port", type=int, default=8000, help="Port del servidor (per defecte 8000)")
    args = parser.parse_args()

    serve_graph(args.graphml, args.solution, args.port)
