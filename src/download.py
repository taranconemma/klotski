import urllib.request
import json
import os

BASE_URL = "https://klotski.pauek.dev"

# 1. Obtenir els 100 IDs
with urllib.request.urlopen(f"{BASE_URL}/api/puzzles") as r:
    ids: list[str] = json.load(r)
print(len(ids))

# 2. Descarregar cada puzzle
os.makedirs("puzzles", exist_ok=True)

a = 0
for id in ids:
    with urllib.request.urlopen(f"{BASE_URL}/api/puzzles/{id}") as r:
        puzzle = json.load(r)
    

    # with open(f"puzzles/{id}.json", "w") as f:
    with open(f"puzzles/{a:02}.json", "w") as f:
        json.dump(puzzle, f)
    a += 1
    
    print(f"Descarregant puzzle {id}")


#ALTERNATIVA: demanant imports directament (s'ha d'instal·lar requests)
# import requests
# import json
# import os

# BASE_URL = "https://klotski.pauek.dev"

# # 1. Obtenir els 100 IDs
# response = requests.get(f"{BASE_URL}/api/puzzles")
# ids : list[str] = response.json()

# # 2. Descarregar cada puzzle
# os.makedirs("puzzles", exist_ok=True)

# for id in ids:
#     response = requests.get(f"{BASE_URL}/api/puzzles/{id}")
#     puzzle = response.json()
    
#     with open(f"puzzles/{id}.json", "w") as f:
#         json.dump(puzzle, f)
    
#     print(f"Descarregant puzzle {id}")