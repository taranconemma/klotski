import urllib.request
import json
import os

BASE_URL = "https://klotski.pauek.dev"

# 1. Obtenir els 100 IDs
with urllib.request.urlopen(f"{BASE_URL}/api/puzzles") as r:
    ids: list[str] = json.load(r)
print(len(ids))

# 2. Descarregar cada puzzle
os.makedirs("puzzles/downloads", exist_ok=True)

index_puzzles = {}
a = 1
for id in ids:
    with urllib.request.urlopen(f"{BASE_URL}/api/puzzles/{id}") as r:
        puzzle = json.load(r)
    
    with open(f"puzzles/downloads/{a:02}.json", "w") as f:
        json.dump(puzzle, f)
    
    # Guardem la relació (00 -> id) al diccionari per referència (i per fer rate automàtic)
    index_puzzles[f"{a:02}"] = id
    a += 1
    
    print(f"Descarregant puzzle {a:02} (ID: {id})")

# Al final del bucle, guardem el diccionari en un fitxer
with open("puzzles/index.json", "w") as f:
    json.dump(index_puzzles, f, indent=4)
print("Índex guardat a puzzles/index.json")