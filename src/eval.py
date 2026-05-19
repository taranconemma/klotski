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
        8. L'abisme              — cost de recuperar-se d'un error en el camí òptim
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

MAX_ESTATS:    int   = 10_000  # nodes
MAX_SOLUCIO:   int   = 30      # moviments fins a la solució més curta
MAX_DIAMETRE:  int   = 50      # pseudo-diàmetre del graf
MAX_PARANYS:   float = 0.30    # fracció de nodes que son culs-de-sac propers
MAX_PONTS:     int   = 15      # ponts crítics en el camí òptim
MAX_ENGANY:    int   = 20      # caselles d'allunyament màxim de l'objectiu
MAX_ABISME:    int   = 40      # cost de caure + tornar des del pitjor punt del camí


# MESURES D'INTERÈS
# Cada funció rep el graf i informació del puzzle i retorna un valor entre
# 0 i 1, que després combinarem per obtenir la puntuació final.

def mesura_nombre_estats(graf: Graph) -> float:
    """ Mesura 1: Nombre d'estats (nodes del graf)

    Un puzzle amb molts estats possibles és més complex. Normalitzem amb una 
    escala logarítmica perquè el nombre d'estats creix exponencialment.

    Retorna un valor entre 0.0 i 1.0 """
    
    valor = math.log(graf.num_vertices() + 1) / math.log(MAX_ESTATS + 1)
    return min(valor, 1.0)


def mesura_longitud_solucio(distancies_des_de_inici: object, nodes_objectiu: list[Vertex]) -> float:
    """ Mesura 2: Longitud del camí mínim fins a la solució

    Un puzzle on la solució requereix molts passos és més difícil i
    per tant (fins a cert punt) més interessant.

    Retorna un valor entre 0.0 i 1.0 """
    dist_min = min(int(distancies_des_de_inici[node]) for node in nodes_objectiu)
    return min(dist_min / MAX_SOLUCIO, 1.0)


def mesura_diametre(graf: Graph) -> float:
    """ Mesura 3: Diàmetre del graf

    El diàmetre és la distància màxima entre qualsevol parell de nodes.
    Un diàmetre gran significa que hi ha estats molt llunyans entre sí,
    cosa que suggereix un puzzle complex amb fases diferenciades.

    Retorna un valor entre 0.0 i 1.0 """
    # pseudo_diameter és una aproximació ràpida del diàmetre real
    # (el diàmetre exacte és molt lent de calcular)
    diametre, _ = pseudo_diameter(graf)
    return min(diametre / MAX_DIAMETRE, 1.0)


def mesura_eficiencia_cami(graf: Graph, distancies_des_de_inici: object, nodes_objectiu: list[Vertex]) -> float:
    """ Mesura 4: Eficiència del camí

    Compara la longitud de la solució òptima amb el diàmetre total del graf.
    La fórmula és: eficiència = moviments_solució / diàmetre

    Un valor proper a 1.0 significa que per resoldre el puzzle cal recorre quasi
    tot el que el puzzle permet: cada moviment compta i no hi ha dreceres.
    Un valor proper a 0 indica que la solució és relativament curta respecte
    a la profunditat total del graf (fàcil de trobar).

    Retorna un valor entre 0.0 i 1.0
    """
    if graf.num_vertices() < 2 or not nodes_objectiu: return 0.0

    diametre, _ = pseudo_diameter(graf)
    if diametre == 0: return 0.0 # no podem dividir entre 0
    dist_min = min(int(distancies_des_de_inici[node]) for node in nodes_objectiu)
    return min(dist_min / diametre, 1.0)


def mesura_densitat_paranys(graf: Graph) -> float:
    """Mesura 5 — Densitat de paranys propers a la meta.

    Un "parany" és un node de grau 1 (s'hi entra però no es pot anar a cap lloc nou). 
    La mesura dona un pes diferent a cada parany per la seva proximitat a la solució 
    perquè un parany molt proper a l'objectiu és més interessant que un llunyà. 

    Retorna un valor entre 0.0 i 1.0.
    """
    n = graf.num_vertices()
    goal_indices = where(graf.vp["is_goal"].a)[0]

    # Distàncies mínimes a qualsevol objectiu inicialitzades amb infinit
    dists_min = full(n, inf)
    for goal_idx in goal_indices:
        dists = shortest_distance(graf, source=goal_idx)
        dists_min = minimum(dists_min, dists.a)

    # Obtenim els graus de tots els vèrtexs
    graus = graf.get_out_degrees(graf.get_vertices())
    paranys = (graus == 1)
    
    # Calculem la suma dels pesos de forma: pes(p) = 1 / (1 + dist_al_goal_més_proper(p))
    suma_pesos = float(sum(1.0 / (1.0 + dists_min[paranys])))
    fraccio = suma_pesos / n
    return min(fraccio / MAX_PARANYS, 1.0)


def mesura_ponts_critics( graf: Graph, node_inici: Vertex, nodes_objectiu: list[Vertex], distancies_des_de_inici: object) -> float:
    """ Mesura 6 — Ponts crítics en el camí.

    Un pont és una aresta que, si s'elimina, desconnecta el graf: no hi ha
    cap camí alternatiu. Si el camí òptim travessa molts ponts, el puzzle
    té moltes "decisions úniques" sense alternativa, cosa que el fa interessant.

    Retorna un valor entre 0.0 i 1.0. """
   
    if graf.num_vertices() < 2: return 0.0

    # Els ponts comuniquen components biconectades, els trobem:
    comp_aresta, _, _ = label_biconnected_components(graf)
    counts = Counter(comp_aresta.a)

    # Camí òptim fins al goal més proper
    best_goal = min(nodes_objectiu, key=lambda v: int(distancies_des_de_inici[v]))
    _, path_edges = shortest_path(graf, node_inici, best_goal)

    # Comptem quants ponts hi ha al camí òptim
    ponts_al_cami = sum(1 for e in path_edges if counts[comp_aresta[e]] == 1)
    return min(ponts_al_cami / MAX_PONTS, 1.0)


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

def mesura_engany_gradient(graf: Graph, puzzle: Puzzle, node_inici: Vertex, nodes_objectiu: list[Vertex], distancies_des_de_inici: object) -> float:
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
    if not nodes_cami:  return 0.0

    # Heurística en cada pas del camí
    h_inicial = heuristica_manhattan(puzzle, graf.vp["state"][node_inici])
    h_max = max(heuristica_manhattan(puzzle, graf.vp["state"][v]) for v in nodes_cami)

    # Fórmula: engany = max(heuristica al llarg del camí) - heuristica_inicial
    engany = h_max - h_inicial
    return min(engany / MAX_ENGANY, 1.0)


def mesura_labisme(graf: Graph, node_inici: Vertex, nodes_objectiu: list[Vertex], distancies_des_de_inici: object) -> float:
    """ Mesura 8 — L'abisme: cost de recuperar-se d'un error en el camí òptim.

    Per a cada node del camí òptim, calculem el cost de fer un moviment
    equivocat (sortir del camí) i tornar-hi. Concretament, per cada node n
    del camí i cada veí v que no és al camí:

        cost_error(n, v) = 1 (anar a v) + distància(v → camí_òptim)

    On distància(v → camí) és el mínim de dist(v, node_camí) per tots els
    nodes restants del camí. Ens quedem amb el pitjor cas: el punt del camí
    on un pas en fals es més costós.

    Un puzzle on qualsevol error costa 30+ moviments per recuperar-se és
    molt més complicat i interessant.

    Retorna un valor entre 0.0 i 1.0.
    """

    nodes_cami = nodes_cami_optim(graf, node_inici, nodes_objectiu, distancies_des_de_inici)
    if len(nodes_cami) < 3: return 0.0

    nodes_cami_set = set(nodes_cami)
    pitjor_cost = 0

    for idx_cami, v in enumerate(nodes_cami[:-1]):
        for vei in v.out_neighbors():
            if vei not in nodes_cami_set:
                # Cost de sortir al veí (1 moviment) i tornar al camí més proper
                # (des del punt actual fins al final, no des de l'inici)
                dist_vei_a_cami = shortest_distance(graf, source=vei, target=nodes_cami[idx_cami + 1:], max_dist=MAX_ABISME).min()
                pitjor_cost = max(pitjor_cost, 1 + dist_vei_a_cami)

    return min(pitjor_cost / MAX_ABISME, 1.0)


# FUNCIÓ PRINCIPAL DE PUNTUACIÓ
# Pondera els diferents criteris d'avaluació.

def puntua_puzzle(graf: Graph, puzzle: Puzzle, node_inici: Vertex, nodes_objectiu: list[Vertex]) -> tuple[float, dict[str, float]]:
    """ Combina les vuit mesures en una puntuació final entre 0 i 5.

    Pesos (han de sumar 1.0):
            m1  Nombre d'estats     10%  (complexitat general)
            m2  Longitud solució    25%  (dificultat principal)
            m3  Diàmetre            10%  (profunditat)
            m4  Eficiència cami     10%  (exigència: sol·lució vs. espai total)
            m5  Densitat paranys    10%  (culs-de-sac propers a la meta)
            m6  Ponts crítics       10%  (decisionsúniques obligatòries)
            m7  Engany gradient     15%  (contraintuïtivitat)
            m8  L'abisme            10%  (cost de recuperar-se d'un error)

    La longitud de la solució i l'engany del gradient pesen més perquè indiquen de forma
    més clara si un puzzle és divertit/interessant.

    Retorna una puntuació de 0 a 5 i un diccionari amb les puntuacions de cada mesura.
    """
    num_nodes = graf.num_vertices()
    if num_nodes > 400_000:
        print(f"\nEl graf és massa gran ({num_nodes:,} nodes). S'assigna 0 a tot per seguretat.")
        return 0.0, {k: 0.0 for k in ["estats", "solucio", "diametre", "eficiencia", "paranys", "ponts", "engany", "abisme"]}

    # Calculem les distàncies des de l'inici per reutilitzar-les
    dist_inici = shortest_distance(graf, source=node_inici)

    # Comprovem si el puzzle té solució (si algun node objectiu és accessible)
    if not nodes_objectiu:
        return 0.0, {k: 0.0 for k in ["estats", "solucio", "diametre", "eficiencia", "paranys", "ponts", "engany", "abisme"]}

    m1 = mesura_nombre_estats(graf)
    m2 = mesura_longitud_solucio(dist_inici, nodes_objectiu)
    m3 = mesura_diametre(graf)
    m4 = mesura_eficiencia_cami(graf, dist_inici, nodes_objectiu)
    m5 = mesura_densitat_paranys(graf)
    m6 = mesura_ponts_critics(graf, node_inici, nodes_objectiu, dist_inici)
    m7 = mesura_engany_gradient(graf, puzzle, node_inici, nodes_objectiu, dist_inici)
    m8 = mesura_labisme(graf, node_inici, nodes_objectiu, dist_inici)

    puntuacio_0_1 = 0.10*m1 + 0.25*m2 + 0.10*m3 + 0.10*m4 + 0.10*m5 + 0.10*m6 + 0.15*m7 + 0.10*m8
    puntuacio_final = puntuacio_0_1 * 5.0

    return puntuacio_final, {
        "estats": round(m1, 3),
        "solucio": round(m2, 3),
        "diametre": round(m3, 3),
        "eficiencia": round(m4, 3),
        "paranys": round(m5, 3),
        "ponts": round(m6, 3),
        "engany": round(m7, 3),
        "abisme": round(m8, 3)
    }



def main(fitxer: str) -> float:
    """Avalua un puzzle donat un fitxer JSON i retorna la puntuació."""

    puzzle = Puzzle.from_json(Path(fitxer).read_text())
    graphml_path = Path(fitxer).with_suffix(".graphml")

    if graphml_path.exists():
        graf = load_graph(str(graphml_path))
    else:
        print("Construint el graf...")
        graf = build_graph(puzzle)

    node_inici     = next(v for v in graf.vertices() if graf.vp["is_start"][v])
    nodes_objectiu = [v for v in graf.vertices() if graf.vp["is_goal"][v]]

    puntuacio, detalls = puntua_puzzle(graf, puzzle, node_inici, nodes_objectiu)

    print(f"\n  AVALUACIÓ DEL PUZZLE:")
    etiquetes = [
        ("Nombre d'estats", "estats", "10%"),
        ("Longitud solució", "solucio", "25%"),
        ("Diàmetre", "diametre", "10%"),
        ("Eficiència camí", "eficiencia", "10%"),
        ("Densitat paranys", "paranys", "10%"),
        ("Ponts crítics", "ponts", "10%"),
        ("Engany del gradient", "engany", "15%"),
        ("L'abisme", "abisme", "10%")]
    for nom, clau, pes in etiquetes:
        print(f"  {nom}: {detalls[clau]:.3f}  ({pes})")
    print(f"  PUNTUACIÓ FINAL:  {puntuacio:.2f} / 5.00  ({round(puntuacio * 2) / 2:.1f}★) \n")

    return puntuacio


if __name__ == "__main__":
    main(sys.argv[1])