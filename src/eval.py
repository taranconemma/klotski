"""
eval.py — Avalua l'interès d'un puzzle de Klotski donat en .json.

Utilització:
    python src/eval.py puzzles/klotski.json

Què fa:
    1. Llegeix el puzzle des d'un fitxer .json
    2. Construeix el graf de l'espai d'estats (via graph.py)
    3. Mesura propietats del graf per determinar si el puzzle és interessant
    4. Imprimeix una puntuació entre 0 i 5 estrelles

Per qué és útil:
    No tots els puzzles generats a l'atzar són interessants.
    Volem puzzles que tinguin molts estats possibles, que la solució
    sigui llarga i que hi hagi "zones" diferenciades (fases del puzzle).
    Les mesures de graf ens ho diuen de forma prou objectiva.
"""

import sys
import math

# graph-tool és la llibreria de grafs del projecte
# Importem només el que necessitem
from graph_tool.all import (
    Graph,
    graph_tool,
    shortest_distance,
    label_components,
    pseudo_diameter,
)

from graph import build_graph
from puzzle import Puzzle
from pathlib import Path


# -------------------------------------------------------------------------
# LLINDARS DE CALIBRACIÓ  ← MODIFICA AQUESÎs VALORS AMB ELS DE rate_all.py
# -------------------------------------------------------------------------
# Quan executis 'make rate_all', el programa et dirà quins valors posar aquí.
# El criteri és que el llindar correspongui al percentil 80-90 del teu conjunt
# de puzzles, de manera que només el 10-20% més complex arribi a puntuació màxima.

MAX_ESTATS:   int = 10_000   # nodes  (escala logarítmica)
MAX_SOLUCIO:  int = 30       # moviments fins a la solució òptima
MAX_DIAMETRE: int = 50       # pseudo-diàmetre del graf

# -------------------------------------------------------------------------
# MESURES D'INTERÈS
# -------------------------------------------------------------------------
# Cada funció rep el graf i informació del puzzle i retorna un valor entre
# 0.0 i 1.0, que després combinarem per obtenir la puntuació final.

def mesura_nombre_estats(graf):
    """
    Mesura 1: Nombre d'estats (nodes del graf)

    Un puzzle amb molts estats possibles és més complex.
    Normalitzem amb una escala logarítmica perquè els valors
    poden variar molt (de 10 a 100.000).

    Retorna un valor entre 0.0 i 1.0
    """
    n = graf.num_vertices()
    if n == 0:
        return 0.0

    # Escala log: log(n) / log(MAX_ESTATS)
    valor = math.log(n + 1) / math.log(MAX_ESTATS + 1)

    # Tallem a 1.0 per si és més gran del màxim esperat
    return min(valor, 1.0)


def mesura_longitud_solucio(graf, node_inici, nodes_objectiu):
    """
    Mesura 2: Longitud del camí mínim fins a la solució

    Un puzzle on la solució requereix molts passos és més difícil i
    per tant (fins a cert punt) més interessant.

    Retorna un valor entre 0.0 i 1.0
    """
    if not nodes_objectiu:
        return 0.0

    # Calculem la distància mínima des de l'inici fins a tots els objectius
    # shortest_distance retorna un array amb la distància a cada node
    distancies = shortest_distance(graf, source=node_inici)

    # Busquem la distància mínima entre tots els nodes objectiu
    dist_min = min(
        int(distancies[node]) for node in nodes_objectiu
        if int(distancies[node]) < 2**30  # 2^30 és "infinit" per graph-tool
    ) if nodes_objectiu else 0

    # Normalitzem: MAX_SOLUCIO passos o més = puntuació màxima
    valor = dist_min / MAX_SOLUCIO

    return min(valor, 1.0)


def mesura_components_connexes(graf):
    """
    Mesura 3: Nombre de components connexes del graf no dirigit

    Si el graf té una sola component, tots els estats es poden assolir.
    Un puzzle amb molts estats accessibles des de l'inici és millor.
    Però si hi ha moltes components petites, pot ser senyal de fragments
    desconnectats poc interessants.

    Per tant: penalitzem si hi ha moltes components petites,
    i premiem si hi ha una gran component dominant.

    Retorna un valor entre 0.0 i 1.0
    """
    # label_components etiqueta cada node amb el número de la seva component
    etiquetes, histograma = label_components(graf)

    n_components = len(histograma)
    n_total = graf.num_vertices()

    if n_total == 0:
        return 0.0

    # La mida de la component més gran
    component_gran = max(histograma)

    # Fracció de nodes que estan a la component gran
    fraccio_gran = component_gran / n_total

    # Volem que la majoria d'estats siguin accessibles → premi si fraccio_gran ≈ 1
    return fraccio_gran


def mesura_diametre(graf):
    """
    Mesura 4: Diàmetre del graf

    El diàmetre és la distància màxima entre qualsevol parell de nodes.
    Un diàmetre gran significa que hi ha estats molt "llunyans" entre sí,
    cosa que suggereix un puzzle complex amb fases diferenciades.

    Retorna un valor entre 0.0 i 1.0
    """
    if graf.num_vertices() < 2:
        return 0.0

    # pseudo_diameter és una aproximació ràpida del diàmetre real
    # (el diàmetre exacte és molt lent de calcular)
    diametre, _ = pseudo_diameter(graf)

    # Normalitzem: MAX_DIAMETRE o més = puntuació màxima
    valor = diametre / MAX_DIAMETRE

    return min(valor, 1.0)


def mesura_eficiencia_cami(graf, node_inici, nodes_objectiu) -> float:
    """
    Mesura 5: Eficiència del camí

    Compara la longitud de la solució òptima amb el diàmetre total del graf.
    La fórmula és: eficiència = moviments_solució / diàmetre

    Un valor proper a 1.0 significa que per resoldre el puzzle cal recorre quasi
    tot el que el puzzle permet: cada moviment compta i no hi ha dreceres.
    Un valor proper a 0 indica que la solució és relativament curta respecte
    a la profunditat total del graf (fàcil de trobar).

    Retorna un valor entre 0.0 i 1.0
    """
    if graf.num_vertices() < 2 or not nodes_objectiu:
        return 0.0

    diametre, _ = pseudo_diameter(graf)
    if diametre == 0:
        return 0.0

    distancies = shortest_distance(graf, source=node_inici)
    dist_min = min(
        int(distancies[node]) for node in nodes_objectiu
        if int(distancies[node]) < 2**30
    ) if nodes_objectiu else 0

    return min(dist_min / diametre, 1.0)


# -------------------------------------------------------------------------
# FUNCIÓ PRINCIPAL DE PUNTUACIÓ
# -------------------------------------------------------------------------

def puntua_puzzle(puzzle, graf, node_inici, nodes_objectiu) -> tuple[float, dict[str, float]]:
    """
    Combina les cinc mesures en una puntuació final entre 0 i 5.

    Pesos de cada mesura (han de sumar 1.0):
        - Nombre d'estats:     20%  (complexitat general)
        - Longitud solució:    35%  (dificultat principal)
        - Component connexa:   15%  (accessibilitat)
        - Diàmetre:            15%  (profunditat)
        - Eficiència del camí: 15%  (exigència: solució vs. espai total)

    La longitud de la solució pesa més perquè és el criteri
    més directament relacionat amb la dificultat percebuda.

    Retorna una tupla amb la puntuació final i un diccionari amb les mesures.
    """
    m1 = mesura_nombre_estats(graf)
    m2 = mesura_longitud_solucio(graf, node_inici, nodes_objectiu)
    m3 = mesura_components_connexes(graf)
    m4 = mesura_diametre(graf)
    m5 = mesura_eficiencia_cami(graf, node_inici, nodes_objectiu)

    # Combinació ponderada
    puntuacio_0_1 = 0.20 * m1 + 0.35 * m2 + 0.15 * m3 + 0.15 * m4 + 0.15 * m5

    # Passem a escala 0–5
    puntuacio_final = puntuacio_0_1 * 5.0

    return puntuacio_final, {
        "estats":     round(m1, 3),
        "solucio":    round(m2, 3),
        "connexio":   round(m3, 3),
        "diametre":   round(m4, 3),
        "eficiencia": round(m5, 3),
    }


# -------------------------------------------------------------------------
# PROGRAMA PRINCIPAL
# -------------------------------------------------------------------------

def main(fitxer=None):
    # Comprovem que ens han passat un fitxer com a argument o per paràmetre
    if fitxer is None:
        if len(sys.argv) != 2:
            print("Uso: python src/eval.py <fitxer_puzzle.json>")
            sys.exit(1)
        fitxer = sys.argv[1]

    # Pas 1: Carreguem el puzzle des del fitxer JSON
    print(f"Carregant puzzle: {fitxer}")
    puzzle = Puzzle.from_json(Path(fitxer).read_text())

    # Pas 2: Construïm o carreguem el graf de l'espai d'estats
    graphml_path = Path(fitxer).with_suffix(".graphml")
    
    if graphml_path.exists():
        print(f"Carregant el graf existent des de {graphml_path}...")
        import graph_tool.all as gt
        graf = gt.load_graph(str(graphml_path))
    else:
        print("Construint el graf d'estats (pot trigar uns segons)...")
        try:
            graf = build_graph(puzzle)
        except TimeoutError as e:
            print(f"\n⏱️  {e}")
            sys.exit(1)
    
    # Extraiem el node inicial i els nodes objectiu
    node_inici = next(v for v in graf.vertices() if graf.vp["is_start"][v])
    nodes_objectiu = [v for v in graf.vertices() if graf.vp["is_goal"][v]]

    print(f"  → {graf.num_vertices()} estats (nodes)")
    print(f"  → {graf.num_edges()} transicions (arestes)")
    print(f"  → {len(nodes_objectiu)} estat(s) objectiu")

    # Pas 3: Calculem la puntuació
    puntuacio, detalls = puntua_puzzle(puzzle, graf, node_inici, nodes_objectiu)

    # Pas 4: Mostrem els resultats
    print()
    print("─" * 40)
    print("  AVALUACIÓ DEL PUZZLE")
    print("─" * 40)
    print(f"  Nombre d'estats (norm.): {detalls['estats']:.3f}")
    print(f"  Longitud solució (norm.): {detalls['solucio']:.3f}")
    print(f"  Fracció component gran:  {detalls['connexio']:.3f}")
    print(f"  Diàmetre (norm.):        {detalls['diametre']:.3f}")
    print(f"  Eficiència del camí:     {detalls['eficiencia']:.3f}")
    print("─" * 40)
    estrelles = round(puntuacio * 2) / 2  # arrodoniment a 0.5 en 0.5
    print(f"  PUNTUACIÓ FINAL: {puntuacio:.2f} / 5.00  ({'⭐' * int(estrelles)})")
    print("─" * 40)

    # Retornem la puntuació per si algú importa aquesta funció (p.ex. generate.py)
    return puntuacio


if __name__ == "__main__":
    main()
