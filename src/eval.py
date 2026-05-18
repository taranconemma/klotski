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
from graph_tool.all import Graph, load_graph, shortest_distance, pseudo_diameter

from graph import build_graph
from puzzle import Puzzle
from pathlib import Path


# LLINDARS DE CALIBRACIÓ  
# Les funcions que avaluen els puzzles tenen uns llindars que es poden canviar
# en funció de com de bons són els puzzles que tenim. Això ens assegura que les
# puntuacions estan ben distribuïdes (no tots els puzzles tenen puntuacions molt
# altes ni molt baixes)
# Executant rate_all.py es pot obtenir una proposta de nous valors en funció de 
# última avaluació dels puzzles del repositori comú. 

MAX_ESTATS:   int = 10_000   # nodes
MAX_SOLUCIO:  int = 30       # moviments fins a la solució més curta
MAX_DIAMETRE: int = 50       # pseudo-diàmetre del graf (més fàcil de calcular que el diàmetre real)


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
    """
    Mesura 3: Diàmetre del graf

    El diàmetre és la distància màxima entre qualsevol parell de nodes.
    Un diàmetre gran significa que hi ha estats molt llunyans entre sí,
    cosa que suggereix un puzzle complex amb fases diferenciades.

    Retorna un valor entre 0.0 i 1.0
    """
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


# FUNCIÓ PRINCIPAL DE PUNTUACIÓ
# Pondera els diferents criteris d'avaluació.

def puntua_puzzle(graf: Graph, node_inici: int, nodes_objectiu: list[int]) -> tuple[float, dict[str, float]]:
    """
    Combina les quatre mesures en una puntuació final entre 0 i 5.

    Pesos de cada mesura (han de sumar 1.0):
        - Nombre d'estats:     25%  (complexitat general)
        - Longitud solució:    45%  (dificultat principal)
        - Diàmetre:            15%  (profunditat)
        - Eficiència del camí: 15%  (exigència: solució vs. espai total)

    La longitud de la solució pesa més perquè és el criteri
    més directament relacionat amb la dificultat percebuda.

    Retorna una tupla amb la puntuació final i un diccionari amb les mesures.
    """
    m1 = mesura_nombre_estats(graf)
    m2 = mesura_longitud_solucio(graf, node_inici, nodes_objectiu)
    m3 = mesura_diametre(graf)
    m4 = mesura_eficiencia_cami(graf, node_inici, nodes_objectiu)

    puntuacio_0_1 = 0.25 * m1 + 0.45 * m2 + 0.15 * m3 + 0.15 * m4  # Combinació ponderada
    puntuacio_final = puntuacio_0_1 * 5.0 # Passem a escala 0–5

    return puntuacio_final, { "estats": round(m1, 3), "solucio": round(m2, 3), "diametre": round(m3, 3), "eficiencia": round(m4, 3) }


def main(fitxer: str) -> float:
    """
    Funció per avaluar un puzzle donat un fitxer JSON.
    """
    puzzle = Puzzle.from_json(Path(fitxer).read_text())
    graphml_path = Path(fitxer).with_suffix(".graphml")
    
    if graphml_path.exists():
        graf = load_graph(str(graphml_path))
    else:
        print(f"Construint el graf...")
        graf = build_graph(puzzle)
    
    # Extraiem el node inicial i els nodes objectiu i calculem la puntuació
    node_inici = next(v for v in graf.vertices() if graf.vp["is_start"][v])
    nodes_objectiu = [v for v in graf.vertices() if graf.vp["is_goal"][v]]
    puntuacio, detalls = puntua_puzzle(graf, node_inici, nodes_objectiu)

    # Mostrem els resultats per pantalla
    print(f"\n AVALUACIÓ DEL PUZZLE")
    print(f"  Nombre d'estats (normalitzat): {detalls['estats']:.3f}")
    print(f"  Longitud solució (normalitzada): {detalls['solucio']:.3f}")
    print(f"  Diàmetre (normalitzat):        {detalls['diametre']:.3f}")
    print(f"  Eficiència del camí (normalitzada):     {detalls['eficiencia']:.3f}")
    print(f"  PUNTUACIÓ FINAL: {puntuacio:.2f} / 5.00")
    print(f"  PUNTUACIÓ ARRODONIDA: {round(puntuacio * 2) / 2 :.1f} / 5")

    return puntuacio

if __name__ == "__main__":
    main(sys.argv[1])
