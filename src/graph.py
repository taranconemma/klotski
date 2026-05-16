# graph.py. Donat un puzzle, guarda el graf resultant. graph-tool permet guardar el 
# graf en un fitxer .graphml, que facilita l'intercanvi amb les altres eines.
# graph.py. Donat un puzzle, guarda el graf resultant. graph-tool permet guardar el
# graf en un fitxer .graphml, que facilita l'intercanvi amb les altres eines.

"""
Construeix el graf d'estats d'un puzzle Klotski i el guarda en .graphml.

Cada node és un estat (disposició de les peces). Dos nodes estan connectats
per una aresta si es pot passar d'un estat a l'altre movent una sola peça
un pas en una direcció (N, E, S, W).

Ús:
    python src/graph.py puzzles/sample1.json
    python src/graph.py puzzles/sample1.json -o output.graphml
"""

import sys
from collections import deque
from pathlib import Path

from graph_tool.all import * #importem directament les funcions que utilitzarem

from logic import possible_moves, apply_move, is_goal
from puzzle import Puzzle, State, Piece, Coord

# Tipus per a la clau canònica d'un estat (hashable)
StateKey = tuple[Coord, ...]


def state_key(puzzle: Puzzle, state: State) -> StateKey:
    """
    Retorna una clau que identifica un estat.
    Peces amb la mateixa forma s'ordenen per posició, de manera que
    estats que només difereixen en l'intercanvi de peces iguals
    tenen la mateixa clau.
    
    Aquesta optimització redueix el nombre de nodes en un factor exacte de k!
    (on k és el nombre de peces no-objectiu iguals). Això és així perquè, en ser
    indistingibles, passem de comptar les posicions com a permutacions P(n,k) a
    comptar-les com a combinacions C(n,k). La relació P(n,k) = C(n,k) * k! demostra
    que eliminem exactament les k! formes redundants d'ordenar aquestes peces.
    """
    positions = list(state.positions) #ho hem de fer mutable

    # Excloem les peces objectiu perquè intercanviar-les amb d'altres faria que es detectessin victòries falses al puzzle.
    goal_indices: set[int] = {i for i, _ in puzzle.goals}

    # Agrupa els índexs de peces per forma
    groups: dict[Piece, list[int]] = {} #la llista conté els indexs de les peces que son iguals que la clau
    for i, piece in enumerate(puzzle.pieces):
        if i not in goal_indices:
            groups.setdefault(piece, []).append(i) #posem totes les peces al diccionari inicialitzant la llista quan veiem una per primer cop

    # Dins de cada grup, ordena les posicions
    for indices in groups.values():
        sorted_positions = sorted(positions[i] for i in indices) #ordenem les posicions de les peces repetides perquè l'estat que queda sempre sigui el mateix si hi ha peces iguals intercambiades
        for i, pos in zip(indices, sorted_positions):            #ordenem per la coordenada x i si hi ha empat per la y
            positions[i] = pos #com que anem agafant els indexos a partir del diccionari sabem que tots els que ordenem i posem son peces iguals

    return tuple(positions)


def build_graph(puzzle: Puzzle) -> Graph:
    """
    Construeix el graf d'estats del puzzle amb BFS.

    Propietats dels nodes:
        state    - posicions de les peces (objecte Python)
        is_start - cert si és l'estat inicial
        is_goal  - cert si satisfà els objectius

    Propietats de les arestes:
        piece     - índex de la peça moguda
        direction - direcció del moviment (N/E/S/W)
        distance  - nombre de caselles mogudes (sempre 1)

    Propietat global del graf:
        puzzle - JSON del puzzle (per poder-lo recuperar des de 3D_view.py)
    """
    g = Graph(directed=False) #fem servir el 'tipus' Graph del mòdul graph_tool per facilitar la visulitzacióposterior amb 3D_view.py
    
    # Propietats dels nodes: cada node tindrà aquestes variables (son com atributs) i els hem de 'declarar'
    vp_state    = g.new_vertex_property("object") 
    vp_is_start = g.new_vertex_property("bool") 
    vp_is_goal  = g.new_vertex_property("bool")

    # Propietats de les arestes: el mateix que amb els nodes
    ep_piece     = g.new_edge_property("int")
    ep_direction = g.new_edge_property("string")
    ep_distance  = g.new_edge_property("int")

    # Propietat global: JSON del puzzle (necessari per 3D_view.py)
    gp_puzzle = g.new_graph_property("string")
    gp_puzzle[g] = puzzle.to_json() #a aquesta ja li assignem un valor
    g.graph_properties["puzzle"] = gp_puzzle

    key_to_v: dict[StateKey, Vertex] = {}

    def get_or_create(state: State) -> Vertex:
        """
        Retorna el vèrtex corresponent a un estat donat.
        Si l'estat no ha estat visitat prèviament, crea un nou vèrtex al graf,
        li assigna les propietats corresponents i l'afegeix al diccionari d'estats.
        """
        k = state_key(puzzle, state) #obtenim la clau que identifica estats sense diferenciar quan peces iguals estan intercambiades de lloc
        if k not in key_to_v:
            v = g.add_vertex()
            key_to_v[k] = v
            vp_state[v]    = state
            vp_is_start[v] = False
            vp_is_goal[v]  = is_goal(puzzle, state)
        return key_to_v[k]

    # BFS des de l'estat inicial
    start_v = get_or_create(puzzle.start)
    vp_is_start[start_v] = True

    queue: deque[State] = deque([puzzle.start])
    visited: set[StateKey] = {state_key(puzzle, puzzle.start)}
    added_edges: set[tuple[StateKey, StateKey]] = set()

    while queue:
        current = queue.popleft()
        current_key = state_key(puzzle, current)
        current_v = key_to_v[current_key]

        for piece_idx, direction, dist in possible_moves(puzzle, current):
            next_state = apply_move(puzzle, current, (piece_idx, direction, dist))
            next_key   = state_key(puzzle, next_state)

            next_v = get_or_create(next_state)

            edge_key = tuple(sorted((current_key, next_key)))
            if edge_key not in added_edges:
                added_edges.add(edge_key)
                e = g.add_edge(current_v, next_v)
                ep_piece[e]     = piece_idx
                ep_direction[e] = direction
                ep_distance[e]  = dist

            if next_key not in visited:
                visited.add(next_key)
                queue.append(next_state)

    # Registrar propietats al graf
    g.vertex_properties["state"]    = vp_state
    g.vertex_properties["is_start"] = vp_is_start
    g.vertex_properties["is_goal"]  = vp_is_goal
    g.edge_properties["piece"]      = ep_piece
    g.edge_properties["direction"]  = ep_direction
    g.edge_properties["distance"]   = ep_distance

    return g


def print_summary(puzzle: Puzzle, g: Graph) -> None:
    n_goals = sum(1 for v in g.vertices() if g.vp["is_goal"][v])
    print(f"Taulell:         {puzzle.W}×{puzzle.H}")
    print(f"Peces:           {len(puzzle.pieces)}")
    print(f"Nodes (estats):  {g.num_vertices()}")
    print(f"Arestes:         {g.num_edges()}")
    print(f"Nodes finals:    {n_goals}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Ús: python {sys.argv[0]} <puzzle.json> [-o sortida.graphml]")
        sys.exit(1)

    json_path = Path(sys.argv[1])
    puzzle = Puzzle.from_json(json_path.read_text())

    # Fitxer de sortida: -o <fitxer> o per defecte <nom>.graphml
    if "-o" in sys.argv:
        output_path = Path(sys.argv[sys.argv.index("-o") + 1])
    else:
        output_path = json_path.with_suffix(".graphml")

    print(f"Construint el graf per: {json_path}")
    g = build_graph(puzzle)
    print_summary(puzzle, g)

    g.save(str(output_path))
    print(f"Graf guardat a: {output_path}")