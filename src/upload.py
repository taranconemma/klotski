import urllib.request
import json

BASE_URL = "https://klotski.pauek.dev"
TOKEN = "tu_token_aqui"

# 1. Llegir el puzzle
with open("puzzles/algun_puzzle.json", "r") as f:
    puzzle = json.load(f)

# 2. Enviar el puzzle
data = json.dumps(puzzle).encode("utf-8")

request = urllib.request.Request(
    f"{BASE_URL}/api/puzzles",
    data=data,
    method="POST",
    headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {TOKEN}",
    }
)

with urllib.request.urlopen(request) as response:
    rebudes = json.load(response)
    print(rebudes)