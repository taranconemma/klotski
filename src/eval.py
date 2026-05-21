"""
eval.py — Avalua l'interès d'un puzzle de Klotski donat en .json.

Utilització:
    python src/eval.py puzzles/klotski.json

Què fa:
    1. Llegeix el puzzle des d'un fitxer .json
    2. Construeix el graf de l'espai d'estats (via graph.py)
    3. Mesura propietats del graf per determinar si el puzzle és interessant
    4. Imprimeix una puntuació entre 0 i 5 estrelles

Mesures implementades:
        1. Nombre d'estats       — complexitat general de l'espai
        2. Longitud solució      — dificultat principal percebuda
        3. Diàmetre              — profunditat màxima del graf
        4. Eficiència del camí   — sol·lució vs. espai total
        5. Densitat de paranys   — culs-de-sac propers a la meta
        6. Ponts crítics         — arestes obligatòries en el camí òptim
        7. Engany del gradient   — quant cal allunyar-se de la meta per resoldre'l
"""

import math
import sys
from numpy import full, where, minimum, inf
from pathlib import Path

from graph_tool.all import Graph, Vertex, load_graph, shortest_distance, shortest_path, pseudo_diameter, label_biconnected_components  #type:ignore
from collections import Counter

from graph import build_graph
from puzzle import Puzzle, State


# LLINDARS DE CALIBRACIÓ  
# Les funcions que avaluen els puzzles tenen uns llindars que es poden canviar
# en funció de com de bons són els puzzles que tenim. Això ens assegura que les
# puntuacions estan ben distribuïdes (no tots els puzzles tenen puntuacions molt
# altes ni molt baixes)
# Executant rate_all.py es pot obtenir una proposta de nous valors en funció de 
# última avaluació dels puzzles del repositori comú. 

from const import MAX_ESTATS, MAX_SOLUCIO, MAX_DIAMETRE, MAX_PARANYS, MAX_PONTS, MAX_ENGANY

# MESURES D'INTERÈS
# Cada funció rep el graf i informació del puzzle i retorna un valor entre
# 0 i 1, que després combinarem per obtenir la puntuació final.

def mesura_nombre_estats(graf: Graph) -> float:
    """ Mesura 1: Nombre d'estats (nodes del graf)

    Un puzzle amb molts estats possibles és més complex. Normalitzem amb una 
    escala logarítmica perquè el nombre d'estats creix exponencialment.

    Retorna: (nombre_estats, valor_normalitzat) """
    
    n = graf.num_vertices()
    valor = math.log(n + 1) / math.log(MAX_ESTATS + 1)
    return n, min(valor, 1.0)


def mesura_longitud_solucio(distancies_des_de_inici: object, nodes_objectiu: list[Vertex]) -> tuple[int, float]:
    """ Mesura 2: Longitud del camí mínim fins a la solució

    Un puzzle on la solució requereix molts passos és més difícil i
    per tant (fins a cert punt) més interessant.

    Retorna: (distancia_minima, valor_normalitzat) """
    dist_min = min(int(distancies_des_de_inici[node]) for node in nodes_objectiu)
    return dist_min, min(dist_min / MAX_SOLUCIO, 1.0)


def mesura_diametre(diametre: int) -> tuple[int, float]:
    """ Mesura 3: Diàmetre del graf

    El diàmetre és la distància màxima entre qualsevol parell de nodes.
    Un diàmetre gran significa que hi ha estats molt llunyans entre sí,
    cosa que suggereix un puzzle complex amb fases diferenciades.

    Retorna: (diametre, valor_normalitzat) """
    return diametre, min(diametre / MAX_DIAMETRE, 1.0)


def mesura_eficiencia_cami(graf: Graph, distancies_des_de_inici: object, nodes_objectiu: list[Vertex], diametre: int) -> tuple[float, float]:
    """ Mesura 4: Eficiència del camí

    Compara la longitud de la solució òptima amb el diàmetre total del graf.
    La fórmula és: eficiència = moviments_solució / diàmetre

    Un valor proper a 1.0 significa que per resoldre el puzzle cal recorre quasi
    tot el que el puzzle permet: cada moviment compta i no hi ha dreceres.
    Un valor proper a 0 indica que la solució és relativament curta respecte
    a la profunditat total del graf (fàcil de trobar).
    
    Retorna: (eficiencia_bruta, valor_normalitzat)
    """
    if graf.num_vertices() < 2 or not nodes_objectiu or diametre == 0: return 0.0, 0.0

    dist_min = min(int(distancies_des_de_inici[node]) for node in nodes_objectiu)
    eficiencia = round(dist_min / diametre, 4)
    return eficiencia, min(eficiencia, 1.0)


def mesura_densitat_paranys(graf: Graph) -> tuple[float, float]:
    """Mesura 5 — Densitat de paranys propers a la meta.

    Un "parany" és un node de grau 1 (s'hi entra però no es pot anar a cap lloc nou). 
    La mesura dona un pes diferent a cada parany per la seva proximitat a la solució 
    perquè un parany molt proper a l'objectiu és més interessant que un llunyà. 

    Retorna: (fraccio_bruta, valor_normalitzat)
    """
    n = graf.num_vertices()
    goal_indices = where(graf.vp["is_goal"].a)[0]
    if len(goal_indices) == 0:
        return 0.0, 0.0

    # Creem un node temporal super-origen (serà l'últim node)
    v_dummy = graf.add_vertex()
    for goal_idx in goal_indices:
        graf.add_edge(v_dummy, goal_idx)

    # Calculem distàncies des de v_dummy en un sol BFS
    dists_dummy = shortest_distance(graf, source=v_dummy)
    
    # Copiem l'array de distàncies excloent el v_dummy per restaurar l'estat original
    dists_min = dists_dummy.a[:-1] - 1
    
    # Eliminem el dummy i les seves arestes (com que és l'últim, és O(1))
    graf.remove_vertex(v_dummy)

    # Obtenim els graus de tots els vèrtexs
    graus = graf.get_out_degrees(graf.get_vertices())
    paranys = (graus == 1)
    
    # Calculem la suma dels pesos de forma: pes(p) = 1 / (1 + dist_al_goal_més_proper(p))
    suma_pesos = float(sum(1.0 / (1.0 + dists_min[paranys])))
    fraccio = suma_pesos / n
    return round(fraccio, 6), min(fraccio / MAX_PARANYS, 1.0)


def mesura_ponts_critics(graf: Graph, node_inici: Vertex, nodes_objectiu: list[Vertex], distancies_des_de_inici: object) -> tuple[int, float]:
    """ Mesura 6 — Ponts crítics en el camí.

    Un pont és una aresta que, si s'elimina, desconnecta el graf: no hi ha
    cap camí alternatiu. Si el camí òptim travessa molts ponts, el puzzle
    té moltes "decisions úniques" sense alternativa, cosa que el fa interessant.

    Retorna: (ponts_absoluts, valor_normalitzat) """
   
    if graf.num_vertices() < 2: return 0, 0.0

    # Els ponts comuniquen components biconectades, els trobem:
    comp_aresta, _, _ = label_biconnected_components(graf)
    counts = Counter(comp_aresta.a)

    # Camí òptim fins al goal més proper
    best_goal = min(nodes_objectiu, key=lambda v: int(distancies_des_de_inici[v]))
    _, path_edges = shortest_path(graf, node_inici, best_goal)

    # Comptem quants ponts hi ha al camí òptim
    ponts_al_cami = sum(1 for e in path_edges if counts[comp_aresta[e]] == 1)
    return ponts_al_cami, min(ponts_al_cami / MAX_PONTS, 1.0)


def heuristica_manhattan(puzzle: Puzzle, state: State) -> int:
    """Suma de distàncies de Manhattan de cada peça a la meta."""
    total = 0
    for i, pos_meta in puzzle.goals:
        px, py = state.positions[i]
        mx, my = pos_meta
        total += abs(px - mx) + abs(py - my)
    return total

def nodes_cami_optim(g: Graph, node_inici: Vertex, nodes_objectiu: list[Vertex], dist_inici: object) -> list[Vertex]:
    """Retorna els nodes del camí òptim des de l'inici al goal més proper."""
    best_goal = min(nodes_objectiu, key=lambda v: int(dist_inici[v]))
    nodes, _ = shortest_path(g, node_inici, best_goal)
    return nodes

def mesura_engany_gradient(graf: Graph, puzzle: Puzzle, node_inici: Vertex, nodes_objectiu: list[Vertex], distancies_des_de_inici: object) -> tuple[int, float]:
    """ Mesura 7 — Engany del gradient (miratge).

    Una heurística poc eficient és la distància de Manhattan de la peça objectiu
    a la seva meta. Mesurem fins a quin punt el camí òptim s'allunya
    d'aquesta heurística: si per resoldre el puzzle cal allunyar la peça
    objectiu de la meta, el puzzle és contraintuïtiu i satisfactori.

    Un valor alt vol dir que en algun punt del camí la peça objectiu estava
    molt més lluny de la meta que a l'inici: el jugador havia de "anar enrere"
    per avançar.

    Retorna un valor entre 0.0 i 1.0.
    """
    nodes_cami = nodes_cami_optim(graf, node_inici, nodes_objectiu, distancies_des_de_inici)
    if not nodes_cami:  return 0, 0.0

    # Heurística en cada pas del camí
    h_inicial = heuristica_manhattan(puzzle, graf.vp["state"][node_inici])
    h_max = max(heuristica_manhattan(puzzle, graf.vp["state"][v]) for v in nodes_cami)

    # Fórmula: engany = max(heuristica al llarg del camí) - heuristica_inicial
    engany = h_max - h_inicial
    return engany, min(engany / MAX_ENGANY, 1.0)


# FUNCIÓ PRINCIPAL DE PUNTUACIÓ
# Pondera els diferents criteris d'avaluació.

def puntua_puzzle(graf: Graph, puzzle: Puzzle, node_inici: Vertex, nodes_objectiu: list[Vertex]) -> tuple[float, dict[str, float], dict[str, float|int]]:
    """ Combina les vuit mesures en una puntuació final entre 0 i 5.

    Pesos (han de sumar 1.0):
            m1  Nombre d'estats     10%  (complexitat general)
            m2  Longitud solució    30%  (dificultat principal)
            m3  Diàmetre            10%  (profunditat)
            m4  Eficiència cami     10%  (exigència: sol·lució vs. espai total)
            m5  Densitat paranys    10%  (culs-de-sac propers a la meta)
            m6  Ponts crítics       10%  (decisionsúniques obligatòries)
            m7  Engany gradient     20%  (contraintuïtivitat)

    La longitud de la solució i l'engany del gradient pesen més perquè indiquen de forma
    més clara si un puzzle és divertit/interessant. 

    Retorna una puntuació de 0 a 5, un diccionari amb les puntuacions de cada mesura,
    i un diccionari amb els valors bruts sense normalitzar per usar-los estadísticament.
    """
    # Calculem les distàncies des de l'inici per reutilitzar-les
    dist_inici = shortest_distance(graf, source=node_inici)

    # Comprovem si el puzzle té solució (si algun node objectiu és accessible)
    if not nodes_objectiu:
        return 0.0, {k: 0.0 for k in ["estats", "solucio", "diametre", "eficiencia", "paranys", "ponts", "engany"]}, {}

    diametre_brut, _ = pseudo_diameter(graf)
    diametre_int = int(diametre_brut)

    v1, m1 = mesura_nombre_estats(graf)
    v2, m2 = mesura_longitud_solucio(dist_inici, nodes_objectiu)
    v3, m3 = mesura_diametre(diametre_int)
    v4, m4 = mesura_eficiencia_cami(graf, dist_inici, nodes_objectiu, diametre_int)
    v5, m5 = mesura_densitat_paranys(graf)
    v6, m6 = mesura_ponts_critics(graf, node_inici, nodes_objectiu, dist_inici)
    v7, m7 = mesura_engany_gradient(graf, puzzle, node_inici, nodes_objectiu, dist_inici)

    puntuacio_0_1 = 0.10*m1 + 0.30*m2 + 0.10*m3 + 0.10*m4 + 0.10*m5 + 0.10*m6 + 0.20*m7
    puntuacio_final = puntuacio_0_1 * 5.0
    
    valors_bruts = {
        "num_nodes": v1,
        "num_arestes": graf.num_edges(),
        "num_goals": len(nodes_objectiu),
        "moviments_solucio": v2,
        "diametre": v3,
        "grau_mitja": round((2 * graf.num_edges()) / v1, 4) if v1 > 0 else 0.0,
        "eficiencia_cami": v4,
        "paranys_ponderat": v5,
        "ponts_al_cami": v6,
        "engany_gradient": v7
    }

    detalls_normalitzats = {
        "estats": round(m1, 3),
        "solucio": round(m2, 3),
        "diametre": round(m3, 3),
        "eficiencia": round(m4, 3),
        "paranys": round(m5, 3),
        "ponts": round(m6, 3),
        "engany": round(m7, 3)
    }

    return puntuacio_final, detalls_normalitzats, valors_bruts



def main(fitxer: str) -> float:
    """Avalua un puzzle donat un fitxer JSON i retorna la puntuació."""

    puzzle = Puzzle.from_json(Path(fitxer).read_text())
    graphml_path = Path(fitxer).with_suffix(".graphml")

    if graphml_path.exists():
        graf = load_graph(str(graphml_path))
    else:
        print("Construint el graf...")
        graf = build_graph(puzzle)

    num_nodes = graf.num_vertices()
    if num_nodes == 0:
        print(f"\nEl graf és invàlid (buit per timeout o límit de nodes). S'assigna 0 a tot per seguretat.")
        puntuacio = 0.0
        detalls = {k: 0.0 for k in ["estats", "solucio", "diametre", "eficiencia", "paranys", "ponts", "engany"]}
    else:
        node_inici     = next(v for v in graf.vertices() if graf.vp["is_start"][v])
        nodes_objectiu = [v for v in graf.vertices() if graf.vp["is_goal"][v]]
        puntuacio, detalls, _ = puntua_puzzle(graf, puzzle, node_inici, nodes_objectiu)

    print(f"\n  AVALUACIÓ DEL PUZZLE:")
    etiquetes = [
        ("Nombre d'estats", "estats", "10%"),
        ("Longitud solució", "solucio", "30%"),
        ("Diàmetre", "diametre", "10%"),
        ("Eficiència camí", "eficiencia", "10%"),
        ("Densitat paranys", "paranys", "10%"),
        ("Ponts crítics", "ponts", "10%"),
        ("Engany del gradient", "engany", "20%")]
    for nom, clau, pes in etiquetes:
        print(f"  {nom}: {detalls[clau]:.3f}  ({pes})")
    print(f"  PUNTUACIÓ FINAL:  {puntuacio:.2f} / 5.00  ({round(puntuacio * 2) / 2:.1f}★) \n")

    return puntuacio

if __name__ == "__main__":
    main(sys.argv[1])