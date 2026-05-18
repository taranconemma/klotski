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
from pathlib import Path

from graph_tool.all import Graph, Vertex, load_graph, shortest_distance, shortest_path, pseudo_diameter, label_biconnected_components

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



# MESURES CLÀSSIQUES 
# MESURES D'INTERÈS
# Cada funció rep el graf i informació del puzzle i retorna un valor entre
# 0 i 1, que després combinarem per obtenir la puntuació final.

def mesura_nombre_estats(graf: Graph) -> float:
    """ Mesura 1: Nombre d'estats (nodes del graf)

    Un puzzle amb molts estats possibles és més complex. Normalitzem amb una 
    escala logarítmica perquè el nombre d'estats creix exponencialment.

    Retorna un valor entre 0.0 i 1.0 """
    
    n = graf.num_vertices()
    if n == 0: return 0.0 # No podem dividir per 0
    valor = math.log(n + 1) / math.log(MAX_ESTATS + 1) # Escala log: log(n) / log(MAX_ESTATS)
    return min(valor, 1.0) # Tallem a 1.0 per si és més gran del màxim esperat


def mesura_longitud_solucio(graf: Graph, node_inici: int, nodes_objectiu: list[int]) -> float:
    """ Mesura 2: Longitud del camí mínim fins a la solució

    Un puzzle on la solució requereix molts passos és més difícil i
    per tant (fins a cert punt) més interessant.

    Retorna un valor entre 0.0 i 1.0 """
    
    if not nodes_objectiu: return 0.0 # No hi ha solució

    # Calculem la distància mínima des de l'inici fins a tots els objectius
    # shortest_distance retorna una llista amb la distància a cada node
    distancies = shortest_distance(graf, source=node_inici)

    # Busquem la distància mínima entre tots els nodes objectiu i retornem el valor normalitzat
    dist_min = min(int(distancies[node]) for node in nodes_objectiu)
    return min(dist_min / MAX_SOLUCIO, 1.0)


def mesura_diametre(graf: Graph) -> float:
    """ Mesura 3: Diàmetre del graf

    El diàmetre és la distància màxima entre qualsevol parell de nodes.
    Un diàmetre gran significa que hi ha estats molt llunyans entre sí,
    cosa que suggereix un puzzle complex amb fases diferenciades.

    Retorna un valor entre 0.0 i 1.0 """
    if graf.num_vertices() < 2: return 0.0
    # pseudo_diameter és una aproximació ràpida del diàmetre real
    # (el diàmetre exacte és molt lent de calcular)
    diametre, _ = pseudo_diameter(graf)
    return min(diametre / MAX_DIAMETRE, 1.0)


def mesura_eficiencia_cami(graf: Graph, node_inici: int, nodes_objectiu: list[int]) -> float:
    """
    Mesura 4: Eficiència del camí

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
    if diametre == 0: return 0.0

    distancies = shortest_distance(graf, source=node_inici) # Calcular la distància a l'objectiu
    dist_min = min(int(distancies[node]) for node in nodes_objectiu)

    return min(dist_min / diametre, 1.0)


def mesura_densitat_paranys(
    graf: Graph,
    nodes_objectiu: list[Vertex],
    distancies_des_de_inici: object | None = None,
    node_inici: Vertex | None = None,
) -> float:
    """Mesura 5 — Densitat de paranys propers a la meta.

    Un "parany" és un node de grau 1 (cul-de-sac: s'hi entra però no es pot
    anar a cap lloc nou). La mesura pesa cada parany per la seva proximitat
    a la solució: un cul-de-sac molt proper a la meta és molt més cruel que
    un de llunyà, perquè t'hi pots caure quan quasi ho tens.

    Fórmula per cada parany p:
        pes(p) = 1 / (1 + dist_al_goal_més_proper(p))

    Puntuació final = suma(pesos) / num_nodes, normalitzada per MAX_PARANYS.

    Retorna un valor entre 0.0 i 1.0.
    """
    if not nodes_objectiu or graf.num_vertices() == 0:
        return 0.0

    # Distàncies des de cada node goal cap a la resta del graf
    # (graf no dirigit: és el mateix que des de cada node al goal)
    dist_al_goal: dict[int, int] = {}
    for goal_v in nodes_objectiu:
        dists = shortest_distance(graf, source=goal_v)
        for v in graf.vertices():
            idx = int(v)
            d = int(dists[v])
            if idx not in dist_al_goal or d < dist_al_goal[idx]:
                dist_al_goal[idx] = d

    INF = 2**31 - 1
    suma_pesos = 0.0
    for v in graf.vertices():
        if v.out_degree() == 1:  # cul-de-sac
            d = dist_al_goal.get(int(v), INF)
            if d < INF:
                suma_pesos += 1.0 / (1.0 + d)

    n = graf.num_vertices()
    fraccio = suma_pesos / n if n > 0 else 0.0
    return min(fraccio / MAX_PARANYS, 1.0)


def mesura_ponts_critics(
    graf: Graph,
    node_inici: Vertex,
    nodes_objectiu: list[Vertex],
) -> float:
    """Mesura 6 — Ponts crítics en el camí òptim.

    Un pont és una aresta que, si s'elimina, desconnecta el graf: no hi ha
    cap camí alternatiu. Si el camí òptim travessa molts ponts, el puzzle
    té moltes "decisions úniques" sense alternativa, cosa que el fa tensat.

    Metodologia:
        1. Calculem totes les arestes pont del graf (biconnected components).
        2. Trobem el camí òptim fins al goal.
        3. Comptem quantes arestes del camí òptim són ponts.

    Retorna un valor entre 0.0 i 1.0.
    """
    if not nodes_objectiu or graf.num_vertices() < 2:
        return 0.0

    # label_biconnected_components etiqueta arestes; les que estan soles
    # (component d'una sola aresta) són ponts.
    comp_aresta, _, _ = label_biconnected_components(graf)

    # Comptem quantes arestes hi ha a cada component biconnectada
    compte_per_comp: dict[int, int] = {}
    for e in graf.edges():
        c = int(comp_aresta[e])
        compte_per_comp[c] = compte_per_comp.get(c, 0) + 1

    # Una aresta és pont si és l'única de la seva component biconnectada
    arestes_pont: set[tuple[int, int]] = set()
    for e in graf.edges():
        c = int(comp_aresta[e])
        if compte_per_comp[c] == 1:
            s, t = int(e.source()), int(e.target())
            arestes_pont.add((min(s, t), max(s, t)))

    # Camí òptim fins al goal més proper
    dist_des_inici = shortest_distance(graf, source=node_inici)
    best_goal = min(nodes_objectiu, key=lambda v: int(dist_des_inici[v]))
    _, path_edges = shortest_path(graf, node_inici, best_goal)

    # Comptem ponts en el camí òptim
    ponts_al_cami = 0
    for e in path_edges:
        s, t = int(e.source()), int(e.target())
        if (min(s, t), max(s, t)) in arestes_pont:
            ponts_al_cami += 1

    return min(ponts_al_cami / MAX_PONTS, 1.0)


def _heuristica_manhattan(puzzle: Puzzle, state: State) -> int:
    """Suma de distàncies de Manhattan de cada peça objectiu a la seva meta."""
    total = 0
    for i, pos_meta in puzzle.goals:
        px, py = state.positions[i]
        mx, my = pos_meta
        total += abs(px - mx) + abs(py - my)
    return total


def mesura_engany_gradient(
    graf: Graph,
    puzzle: Puzzle,
    node_inici: Vertex,
    nodes_objectiu: list[Vertex],
) -> float:
    """Mesura 7 — Engany del gradient (miratge).

    Una heurística naïf és la distància de Manhattan de la peça objectiu
    a la seva meta. Mesurem fins a quin punt el camí òptim s'allunya
    d'aquesta heurística: si per resoldre el puzzle cal allunyar la peça
    objectiu de la meta, el puzzle és contraintuïtiu i satisfactori.

    Fórmula:
        engany = max(heuristica al llarg del camí) - heuristica_inicial

    Un valor alt vol dir que en algun punt del camí la peça objectiu estava
    molt més lluny de la meta que a l'inici: el jugador havia de "anar enrere"
    per avançar.

    Retorna un valor entre 0.0 i 1.0.
    """
    if not nodes_objectiu or not graf.vp.get("state"):
        return 0.0

    dist_des_inici = shortest_distance(graf, source=node_inici)
    best_goal = min(nodes_objectiu, key=lambda v: int(dist_des_inici[v]))
    _, path_edges = shortest_path(graf, node_inici, best_goal)

    if not path_edges:
        return 0.0

    # Recollim els nodes del camí (en ordre)
    nodes_cami: list[Vertex] = [node_inici]
    for e in path_edges:
        # Com el graf no és dirigit, el node destí és el que no hem visitat
        s, t = e.source(), e.target()
        nodes_cami.append(t if t != nodes_cami[-1] else s)

    # Heurística en cada pas del camí
    h_inicial = _heuristica_manhattan(puzzle, graf.vp["state"][node_inici])
    h_max = h_inicial
    for v in nodes_cami[1:]:
        estat = graf.vp["state"][v]
        if estat is not None:
            h = _heuristica_manhattan(puzzle, estat)
            if h > h_max:
                h_max = h

    engany = h_max - h_inicial  # quantes caselles més lluny hem d'anar
    return min(engany / MAX_ENGANY, 1.0)


def mesura_labisme(
    graf: Graph,
    node_inici: Vertex,
    nodes_objectiu: list[Vertex],
) -> float:
    """Mesura 8 — L'abisme: cost de recuperar-se d'un error en el camí òptim.

    Per a cada node del camí òptim, calculem el cost de fer un moviment
    equivocat (sortir del camí) i tornar-hi. Concretament, per cada node n
    del camí i cada veí v que no és al camí:

        cost_error(n, v) = 1 (anar a v) + distància(v → camí_òptim)

    On distància(v → camí) és el mínim de dist(v, node_camí) per tots els
    nodes restants del camí. Ens quedem amb el pitjor cas: el punt del camí
    on un pas en fals és més costós.

    Un puzzle on qualsevol error costa 30+ moviments per recuperar-se és
    molt més dur psicològicament.

    Retorna un valor entre 0.0 i 1.0.
    """
    if not nodes_objectiu or graf.num_vertices() < 3:
        return 0.0

    dist_des_inici = shortest_distance(graf, source=node_inici)
    best_goal = min(nodes_objectiu, key=lambda v: int(dist_des_inici[v]))
    _, path_edges = shortest_path(graf, node_inici, best_goal)

    if len(path_edges) < 2:
        return 0.0

    # Construïm el camí com a llista ordenada de nodes i un set per cerques ràpides
    nodes_cami: list[Vertex] = [node_inici]
    for e in path_edges:
        s, t = e.source(), e.target()
        nodes_cami.append(t if t != nodes_cami[-1] else s)

    nodes_cami_ids: set[int] = {int(v) for v in nodes_cami}

    # Per cada node del camí (excepte el final), mirem els veïns fora del camí
    pitjor_cost = 0
    INF = 2**31 - 1

    for idx_cami, v in enumerate(nodes_cami[:-1]):
        # Distàncies des de v a tots els nodes
        dists_des_de_v = shortest_distance(graf, source=v)

        for vei in v.out_neighbors():
            if int(vei) in nodes_cami_ids:
                continue  # el veí és al camí, no és un error

            # Cost de sortir al veí (1 moviment) i tornar al camí més proper
            # (des del punt actual fins al final, no des de l'inici)
            dist_vei_a_cami = min(
                int(shortest_distance(graf, source=vei)[u])
                for u in nodes_cami[idx_cami + 1:]
            )

            if dist_vei_a_cami < INF:
                cost_total = 1 + dist_vei_a_cami
                if cost_total > pitjor_cost:
                    pitjor_cost = cost_total

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
    # Calculem les distàncies des de l'inici per reutilitzar-les
    dist_inici = shortest_distance(graf, source=node_inici)

    m1 = mesura_nombre_estats(graf)
    m2 = mesura_longitud_solucio(graf, node_inici, nodes_objectiu, dist_inici)
    m3 = mesura_diametre(graf)
    m4 = mesura_eficiencia_cami(graf, node_inici, nodes_objectiu, dist_inici)
    m5 = mesura_densitat_paranys(graf, nodes_objectiu, dist_inici, node_inici)
    m6 = mesura_ponts_critics(graf, node_inici, nodes_objectiu)
    m7 = mesura_engany_gradient(graf, puzzle, node_inici, nodes_objectiu)
    m8 = mesura_labisme(graf, node_inici, nodes_objectiu)

    puntuacio_0_1 = 0.10*m1 + 0.25*m2 + 0.10*m3 + 0.10*m4 + 0.10*m5 + 0.10*m6 + 0.15*m7 + 0.10*m8
    puntuacio_final = puntuacio_0_1 * 5.0

    return puntuacio_final, {"estats": round(m1, 3), "solucio": round(m2, 3), "diametre": round(m3, 3), "eficiencia": round(m4, 3), "paranys": round(m5, 3), "ponts": round(m6, 3), "engany": round(m7, 3), "abisme": round(m8, 3)}


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
    etiquetes = [("Nombre d'estats", "10%"), ("Longitud solució", "25%"), ("Diàmetre", "10%"), ("Eficiència camí", "10%"), ("Densitat paranys", "10%"), ("Ponts crítics", "10%"), ("Engany del gradient", "15%"), ("L'abisme", "10%")]
    for nom, clau, pes in etiquetes:
        print(f"  {nom}: {detalls[clau]:.3f}  ({pes})")
    print(f"  PUNTUACIÓ FINAL:  {puntuacio:.2f} / 5.00  ({round(puntuacio * 2) / 2:.1f}★)")

    return puntuacio


if __name__ == "__main__":
    main(sys.argv[1])