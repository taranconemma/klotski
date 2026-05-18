"""
rate.py — Donat un identificador de puzzle del repositori, envia una 
valoració entre 0 i 5 estrelles.

Utilització:
    python src/rate.py <id_puzzle> <puntuació> <el_teu_token>
"""

import sys
import json
import os
import urllib.request
import urllib.error
from pathlib import Path
from eval import main as eval_main

SERVIDOR = "https://klotski.pauek.dev"

def envia_valoracio(id_puzzle: str, puntuacio: float, token: str) -> bool:
    """ Envia una valoració per a un puzzle al servidor.

    Paràmetres:
        id_puzzle  (str):   Identificador del puzzle
        puntuacio  (float o int): Valor entre 0.0 i 5.0
        token      (str):   Token personal d'autenticació

    Retorna True si l'enviament ha anat bé, False si hi ha hagut algun error. """

    url = f"{SERVIDOR}/api/puzzles/{id_puzzle}/votes"
    cos_json = json.dumps({"stars": int(puntuacio)}).encode("utf-8")
    peticio = urllib.request.Request(url, data=cos_json, method="POST", headers={ "Content-Type": "application/json", "Authorization": f"Bearer {token}", })
    
    with urllib.request.urlopen(peticio) as _:
        print(f"Valoració enviada correctament")
        print(f"    Puzzle: {id_puzzle}")
        print(f"    Puntuació: {int(puntuacio)} / 5.0")
        return True


def main():

    id_puzzle = sys.argv[1]

    # PUJADA MASSIVA DE RATINGS
    if id_puzzle == "all":

        ratings_path = Path("puzzles/downloads/ratings.json")
        if not ratings_path.exists():
            print("No existeis el fitxer ratings.json amb totes les valoracions per enviar.")
            sys.exit(1)

        with open(ratings_path) as f:
            ratings = json.load(f)

        token = sys.argv[2]

        for clau_curta, data in sorted(ratings.items()):
            id_real = data["id_real"]
            puntuacio_float = data.get("puntuacio_recalibrada", data.get("puntuacio_original", 0.0))
            puntuacio = int(round(puntuacio_float))

            print(f"\n[{clau_curta}] Enviant valoració de {puntuacio} estrelles.")
    
    #PUJADA D'UN ÚNIC PUZZLE

    if os.path.exists("puzzles/index.json"):
        with open("puzzles/index.json") as f:
            index_puzzles = json.load(f)  
        if id_puzzle in index_puzzles:
            id_real = index_puzzles[id_puzzle]
            fitxer_puzzle = f"puzzles/downloads/{id_puzzle}.json"
    
    if sys.argv[2] == "auto":
        print("Calculant puntuació...")
        puntuacio_float = eval_main(fitxer_puzzle)
        puntuacio = int(round(puntuacio_float))
        print(f"Puntuació: {puntuacio} ({puntuacio_float})\n")
    else: puntuacio = int(round(float(sys.argv[2])))
        
    token = sys.argv[3]
    print(f"Enviant valoració: Puzzle: {id_real}, Puntuació: {puntuacio} \n")
    envia_valoracio(id_real, puntuacio, token)


if __name__ == "__main__":
    main()