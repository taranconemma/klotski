"""
Donat un puzzle, guarda el graf resultant. graph-tool permet guardar el graf en 
un fitxer .graphml, que facilita l'intercanvi amb les altres eines (com ara el 
solve.py o l'eval.py).

Cada node és un estat (disposició de les peces). Dos nodes estan connectats
per una aresta si es pot passar d'un estat a l'altre movent una sola peça
un pas en una direcció (N, E, S, W). Per més detalls: consultar el README.

Ús:
    python src/graph.py puzzles/sample1.json
"""

import sys
import time
from collections import deque
from pathlib import Path

from graph_tool.all import Graph, Vertex, load_graph  # type:ignore

from logic import possible_moves, apply_move, is_goal
from puzzle import Puzzle, State, Piece, Coord

from const import TIMEOUT_ACTIVAT, TIMEOUT_SEGONS, LIMIT_NODES

# Tipus per a la clau d'un estat (no es repeteix per peces iguals intercanviades)
StateKey = tuple[Coord, ...]

def state_key(puzzle: Puzzle, state: State) -> StateKey:
    """
    Retorna una clau que identifica un estat.
    Peces amb la mateixa forma s'ordenen per posició, de manera que estats que només 
    difereixen en l'intercanvi de peces iguals tenen la mateixa clau.
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
    g = Graph(directed=False)
    
    # Creem i registrem les propietats per utilitzar-les després a 3D_view.py, solve.py i eval.py
    g.vp.state = g.new_vertex_property("object") 
    g.vp.is_start = g.new_vertex_property("bool") 
    g.vp.is_goal = g.new_vertex_property("bool")
    g.ep.piece = g.new_edge_property("int")
    g.ep.direction = g.new_edge_property("string")
    g.ep.distance = g.new_edge_property("int")
    g.gp.puzzle = g.new_graph_property("string")
    g.gp.puzzle = puzzle.to_json()

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
            g.vp.state[v] = state
            g.vp.is_start[v] = False
            g.vp.is_goal[v] = is_goal(puzzle, state)
        return key_to_v[k]

    # BFS des de l'estat inicial: l'hem de construir per poder-lo recórrer després amb les funcions pròpies de graph_tool
    start_v = get_or_create(puzzle.start)
    g.vp.is_start[start_v] = True

    queue: deque[State] = deque([puzzle.start])
    visited: set[StateKey] = {state_key(puzzle, puzzle.start)}

    t_inici = time.monotonic()  # Instant d'inici del BFS

    while queue:
        current = queue.popleft()
        current_key = state_key(puzzle, current)
        current_v = key_to_v[current_key]

        # Comprovació de timeout i límit de nodes
        # Si ha passat massa temps o el graf és massa gran, aturem i retornem buit
        if TIMEOUT_ACTIVAT and (time.monotonic() - t_inici) > TIMEOUT_SEGONS:
            print(f"\nError de temps: El graf ha tardat més de {TIMEOUT_SEGONS // 60} minuts i s'ha aturat. Retorna graf buit.")
            return Graph()
            
        if g.num_vertices() > LIMIT_NODES:
            print(f"\nError de nodes: El graf ha superat el límit de {LIMIT_NODES:,} nodes ({g.num_vertices():,}). Retorna graf buit.")
            return Graph()

        for piece_idx, direction, dist in possible_moves(puzzle, current):
            next_state = apply_move(puzzle, current, (piece_idx, direction, dist))
            next_key   = state_key(puzzle, next_state)
            next_v = get_or_create(next_state)

            # Com que el graf no és dirigit hem de vigilar de no posar una aresta endavant i un altre cop endarrere
            if g.edge(current_v, next_v) is None:
                e = g.add_edge(current_v, next_v)
                g.ep.piece[e] = piece_idx
                g.ep.direction[e] = direction
                g.ep.distance[e] = dist

            if next_key not in visited:
                visited.add(next_key)
                queue.append(next_state)
    return g


def carregar_o_construir_graf(fitxer_json: Path) -> Graph:
    """
    Carrega el graf des del .graphml si existeix.
    Si no existeix, intenta construir-lo de forma segura. Si hi ha qualsevol error
    (format JSON invàlid, timeout o excés de nodes), desa un graf buit al fitxer per
    evitar tornar-lo a intentar en el futur, i retorna el graf buit.
    """
    graphml_path = fitxer_json.with_suffix(".graphml")
    if graphml_path.exists():
        return load_graph(str(graphml_path))
    
    g = Graph()
    g.vp.state = g.new_vertex_property("object") 
    g.vp.is_start = g.new_vertex_property("bool") 
    g.vp.is_goal = g.new_vertex_property("bool")
    g.gp.puzzle = g.new_graph_property("string")
    g.gp.puzzle = "{}"

    try:
        puzzle = Puzzle.from_json(fitxer_json.read_text())
        built_g = build_graph(puzzle)
        if built_g.num_vertices() == 0:
            # Timeout o límit de nodes
            g.save(str(graphml_path))
            return g
        g = built_g
    except Exception as e:
        print(f"\n[graph.py] Error de validesa o de construcció per {fitxer_json.name}: {e}. Desant graf buit.")
        g.save(str(graphml_path))
        return g
    
    g.save(str(graphml_path))
    return g


def print_summary(puzzle: Puzzle, g: Graph) -> None:
    ''' Mostra per pantalla informació rellevant sobre el puzzle i del graf que s'ha construït. '''
    n_goals = sum(1 for v in g.vertices() if g.vp["is_goal"][v])
    print(f"Taulell:         {puzzle.W}×{puzzle.H}")
    print(f"Peces:           {len(puzzle.pieces)}")
    print(f"Nodes (estats):  {g.num_vertices()}")
    print(f"Arestes:         {g.num_edges()}")
    print(f"Nodes finals:    {n_goals}")


def main() -> None:
    json_path = Path(sys.argv[1])
    g = carregar_o_construir_graf(json_path)
    if g.num_vertices() == 0:
        print("\n El graf no s'ha pogut construir o s'ha aturat per límit de temps/nodes. S'ha desat buit.")
        sys.exit(1)
    
    puzzle = Puzzle.from_json(json_path.read_text())
    print_summary(puzzle, g)

if __name__ == "__main__":
    main()