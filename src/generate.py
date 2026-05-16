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
import argparse
import os

# Importem les funcions dels nostres propis fitxers
# IMPORTANT: graph.py ha d'existir a src/ i exportar build_graph()
# IMPORTANT: puzzle.py ha d'existir a src/ i exportar:
#              - canonicalize(puzzle) → puzzle en format canònic
#              - is_solvable(puzzle)  → True/False
from graph import build_graph
from puzzle import canonicalize, is_solvable

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

def avalua_puzzle(puzzle):
    """
    Construeix el graf del puzzle i en calcula la puntuació.

    Retorna:
        (puntuació, detalls) on puntuació és un float entre 0 i 5,
        o (0.0, {}) si el puzzle no és resoluble o hi ha algun error.
    """
    try:
        # Primer comprovem si el puzzle és resoluble (evitem grafs inútils)
        # IMPORTANT: is_solvable() ha d'estar definida a puzzle.py
        if not is_solvable(puzzle):
            return 0.0, {}

        # Construïm el graf de l'espai d'estats
        graf, node_inici, nodes_objectiu = build_graph(puzzle)

        # Si no hi ha estats objectiu accessibles, puntuació 0
        if not nodes_objectiu:
            return 0.0, {}

        # Calculem la puntuació
        puntuacio, detalls = puntua_puzzle(puzzle, graf, node_inici, nodes_objectiu)
        return puntuacio, detalls

    except Exception as error:
        # Si hi ha algun error inesperat, continuem sense trencar el programa
        print(f"  [error avaluant puzzle: {error}]")
        return 0.0, {}


# -------------------------------------------------------------------------
# PROGRAMA PRINCIPAL
# -------------------------------------------------------------------------

def main():
    # Configurem els arguments de la línia de comandes
    parser = argparse.ArgumentParser(
        description="Genera puzzles de Klotski a l'atzar i selecciona els millors"
    )
    parser.add_argument(
        "--num", type=int, default=20,
        help="Quants puzzles generar en total (per defecte: 20)"
    )
    parser.add_argument(
        "--millors", type=int, default=3,
        help="Quants dels millors guardar (per defecte: 3)"
    )
    parser.add_argument(
        "--sortida", type=str, default="puzzles/generats/",
        help="On guardar els puzzles (per defecte: puzzles/generats/)"
    )
    parser.add_argument(
        "--W", type=int, default=4,
        help="Amplada del taulell (per defecte: 4)"
    )
    parser.add_argument(
        "--H", type=int, default=5,
        help="Alçada del taulell (per defecte: 5)"
    )

    args = parser.parse_args()

    # Creem el directori de sortida si no existeix
    os.makedirs(args.sortida, exist_ok=True)

    print(f"Generant {args.num} puzzles de {args.W}×{args.H}...")
    print(f"Guardarem els {args.millors} millors a: {args.sortida}")
    print()

    # Llista de (puntuació, puzzle) per ordenar al final
    resultats = []

    for i in range(args.num):
        print(f"  Puzzle {i+1}/{args.num}: ", end="", flush=True)

        # Pas 1: Generem un puzzle
        puzzle = genera_puzzle_aleatori(args.W, args.H)

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
    print(f"  TOP {args.millors} PUZZLES GENERATS")
    print(f"─" * 40)

    n_guardats = 0
    for rang, (puntuacio, puzzle) in enumerate(resultats[:args.millors]):
        nom_fitxer = f"generat_{rang+1:02d}.json"
        ruta = os.path.join(args.sortida, nom_fitxer)

        with open(ruta, "w") as f:
            json.dump(puzzle, f, indent=2)

        print(f"  #{rang+1}: {puntuacio:.2f} ⭐ → guardat a {ruta}")
        n_guardats += 1

    print(f"─" * 40)
    print(f"  Total generats: {len(resultats)}")
    print(f"  Total guardats: {n_guardats}")


if __name__ == "__main__":
    main()

