# generate.py. Donats certs paràmetre (completament lliures), genera un 
# nou puzzle que guarda en un fitxer .json

"""
generate.py — Genera puzzles de Klotski a l'atzar i selecciona els millors

Uso:
    python src/generate.py --num 20 --millors 3 --sortida puzzles/generats/

Arguments opcionals:
    --num N        Quants puzzles generar en total (per defecte: 20)
    --millors N    Quants dels millors guardar (per defecte: 3)
    --sortida DIR  On guardar els puzzles seleccionats (per defecte: puzzles/generats/)
    --W N          Amplada del taulell (per defecte: 4)
    --H N          Alçada del taulell (per defecte: 5)

Què fa:
    1. Genera N puzzles a l'atzar amb el format correcte
    2. Avalua cadascun amb les mesures de eval.py
    3. Guarda els M millors en fitxers .json al directori indicat

Per qué és útil:
    Un generador completament aleatori rarament produeix puzzles bons.
    Per tant, generem molts i ens quedem els millors, deixant que
    la funció d'avaluació (eval.py) faci el filtratge.
"""

import sys
import json
import random
import os

# Importem les funcions dels nostres propis fitxers
# IMPORTANT: graph.py ha d'existir a src/ i exportar build_graph()
from graph import build_graph
from puzzle import Puzzle

# Importem la funció de puntuació d'eval.py
# (la importem directament per no haver de cridar un subprocess)
from eval import puntua_puzzle


# -------------------------------------------------------------------------
# FORMES DE POLIOMIN
# -------------------------------------------------------------------------
# Cada peça és una llista de coordenades relatives a (0,0).
# Coordenades en format [x, y] (x = columna, y = fila).
# Només fem servir formes fins a mida 4 (poliominós).

FORMES_DISPONIBLES = [
    # Mida 1 (monominó)
    [[0, 0]],

    # Mida 2 (dominó)
    [[0, 0], [1, 0]],   # horitzontal
    [[0, 0], [0, 1]],   # vertical

    # Mida 3 (trominós)
    [[0, 0], [1, 0], [2, 0]],          # línia horitzontal
    [[0, 0], [0, 1], [0, 2]],          # línia vertical
    [[0, 0], [1, 0], [0, 1]],          # L dalt-esquerra
    [[0, 0], [1, 0], [1, 1]],          # L dalt-dreta

    # Mida 4 (tetrominós simples — sense totes les rotacions per simplicitat)
    [[0, 0], [1, 0], [2, 0], [3, 0]],  # línia horitzontal 4
    [[0, 0], [0, 1], [0, 2], [0, 3]],  # línia vertical 4
    [[0, 0], [1, 0], [0, 1], [1, 1]],  # quadrat 2x2
    [[0, 0], [1, 0], [2, 0], [0, 1]],  # L gran
]


# -------------------------------------------------------------------------
# GENERACIÓ D'UN PUZZLE A L'ATZAR
# -------------------------------------------------------------------------

def canonicalize(puzzle_dict: dict) -> dict:
    pieces = puzzle_dict["pieces"]
    start = puzzle_dict["start"]
    pairs = list(zip(pieces, start))
    indexed_pairs = list(enumerate(pairs))
    indexed_pairs.sort(key=lambda x: x[1])
    
    new_pieces = []
    new_start = []
    old_to_new = {}
    for new_idx, (old_idx, (piece, pos)) in enumerate(indexed_pairs):
        new_pieces.append(piece)
        new_start.append(pos)
        old_to_new[old_idx] = new_idx
        
    new_goals = []
    for g in puzzle_dict.get("goals", []):
        new_goals.append({"i": old_to_new[g["i"]], "pos": g["pos"]})
    
    puzzle_dict["pieces"] = new_pieces
    puzzle_dict["start"] = new_start
    puzzle_dict["goals"] = sorted(new_goals, key=lambda g: (g["i"], g["pos"]))
    return puzzle_dict

def genera_puzzle_aleatori(W, H, n_peces_min=3, n_peces_max=6):
    """
    Genera un puzzle vàlid a l'atzar.

    Estratègia:
        1. Escollim quantes peces hi haurà i quines formes tindran
        2. Col·loquem les peces en posicions aleatòries sense solapar-se
        3. La primera peça és sempre l'objectiu (a col·locar a [0,0])
        4. Canonicalitzem el puzzle

    Retorna:
        Un diccionari amb el format JSON estàndard del puzzle,
        o None si no s'ha pogut generar un puzzle vàlid.
    """
    n_peces = random.randint(n_peces_min, n_peces_max)

    # Intentem col·locar les peces fins a MAX_INTENTS vegades
    MAX_INTENTS = 200
    for _ in range(MAX_INTENTS):

        peces = []      # formes de les peces (coordenades relatives)
        posicions = []  # posicions inicials de cada peça (cantonada top-left)

        caselles_ocupades = set()  # conjunt de [x, y] ja ocupats

        col·locades = 0
        intents_peça = 0

        while col·locades < n_peces and intents_peça < MAX_INTENTS:
            intents_peça += 1

            # Escollim una forma aleatòria
            forma = random.choice(FORMES_DISPONIBLES)

            # Posició aleatòria dins del taulell
            pos_x = random.randint(0, W - 1)
            pos_y = random.randint(0, H - 1)

            # Calculem les caselles absolutes que ocuparia aquesta peça
            caselles = [
                (pos_x + dx, pos_y + dy)
                for dx, dy in forma
            ]

            # Comprovem que:
            # (a) totes les caselles estan dins del taulell
            # (b) cap casella ja està ocupada
            dins_taulell = all(0 <= x < W and 0 <= y < H for x, y in caselles)
            sense_solapament = all(c not in caselles_ocupades for c in caselles)

            if dins_taulell and sense_solapament:
                peces.append(forma)
                posicions.append([pos_x, pos_y])
                caselles_ocupades.update(caselles)
                col·locades += 1

        if col·locades < n_peces_min:
            continue  # No hem pogut col·locar prou peces, tornem a intentar

        # La peça objectiu és la primera (índex 0)
        # L'objectiu és que arribi a la cantonada [0, 0]
        objectius = [{"i": 0, "pos": [0, 0]}]

        # Construïm el puzzle en format estàndard
        puzzle = {
            "W": W,
            "H": H,
            "walls": [],        # Sense parets per simplicitat
            "pieces": peces,
            "start": posicions,
            "goals": objectius,
        }

        # Canonicalitzem (per assegurar el format correcte)
        # IMPORTANT: canonicalize() ha d'estar definida a puzzle.py
        puzzle = canonicalize(puzzle)

        return puzzle

    # Si no hem pogut generar un puzzle en MAX_INTENTS, retornem None
    return None


# -------------------------------------------------------------------------
# AVALUACIÓ D'UN PUZZLE GENERAT
# -------------------------------------------------------------------------

def avalua_puzzle(puzzle_dict):
    """
    Construeix el graf del puzzle i en calcula la puntuació.

    Retorna:
        (puntuació, detalls) on puntuació és un float entre 0 i 5,
        o (0.0, {}) si el puzzle no és resoluble o hi ha algun error.
    """
    # Convertim el diccionari al format d'objecte Puzzle del projecte
    puzzle_obj = Puzzle.from_json(json.dumps(puzzle_dict))

    # Construïm el graf de l'espai d'estats
    graf = build_graph(puzzle_obj)
    
    # Extraiem el node inicial i els nodes objectiu
    node_inici = next(v for v in graf.vertices() if graf.vp["is_start"][v])
    nodes_objectiu = [v for v in graf.vertices() if graf.vp["is_goal"][v]]

    # Si no hi ha estats objectiu accessibles, puntuació 0
    if not nodes_objectiu:
        return 0.0, {}

    # Calculem la puntuació
    puntuacio, detalls = puntua_puzzle(puzzle_obj, graf, node_inici, nodes_objectiu)
    return puntuacio, detalls


# -------------------------------------------------------------------------
# PROGRAMA PRINCIPAL
# -------------------------------------------------------------------------

def main():
    # Valors per defecte
    num = 20
    millors = 3
    sortida = "puzzles/generats/"
    W = 4
    H = 5

    # Llegim arguments si ens els passen (python generate.py num millors sortida W H)
    if len(sys.argv) > 1: num = int(sys.argv[1])
    if len(sys.argv) > 2: millors = int(sys.argv[2])
    if len(sys.argv) > 3: sortida = sys.argv[3]
    if len(sys.argv) > 4: W = int(sys.argv[4])
    if len(sys.argv) > 5: H = int(sys.argv[5])

    # Creem el directori de sortida si no existeix
    os.makedirs(sortida, exist_ok=True)

    print(f"Generant {num} puzzles de {W}×{H}...")
    print(f"Guardarem els {millors} millors a: {sortida}")
    print()

    # Llista de (puntuació, puzzle) per ordenar al final
    resultats = []

    for i in range(num):
        print(f"  Puzzle {i+1}/{num}: ", end="", flush=True)

        # Pas 1: Generem un puzzle
        puzzle = genera_puzzle_aleatori(W, H)

        if puzzle is None:
            print("no s'ha pogut generar")
            continue

        # Pas 2: Avaluem el puzzle
        puntuacio, detalls = avalua_puzzle(puzzle)

        print(f"puntuació = {puntuacio:.2f} ⭐")

        resultats.append((puntuacio, puzzle))

    # Pas 3: Ordenem els resultats de millor a pitjor
    resultats.sort(key=lambda x: x[0], reverse=True)

    # Pas 4: Guardem els M millors
    print()
    print(f"─" * 40)
    print(f"  TOP {millors} PUZZLES GENERATS")
    print(f"─" * 40)

    n_guardats = 0
    for rang, (puntuacio, puzzle) in enumerate(resultats[:millors]):
        nom_fitxer = f"generat_{rang+1:02d}.json"
        ruta = os.path.join(sortida, nom_fitxer)

        with open(ruta, "w") as f:
            json.dump(puzzle, f, indent=2)

        print(f"  #{rang+1}: {puntuacio:.2f} ⭐ → guardat a {ruta}")
        n_guardats += 1

    print(f"─" * 40)
    print(f"  Total generats: {len(resultats)}")
    print(f"  Total guardats: {n_guardats}")


if __name__ == "__main__":
    main()

