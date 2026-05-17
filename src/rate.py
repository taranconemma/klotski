# rate.py. Donat un identificador de puzzle del repositori, 
# envia una valoració entre 0 i 5 estrelles.

"""
rate.py — Envia la valoració d'un puzzle al repositori de Klotski

Uso:
    python src/rate.py <id_puzzle> <puntuació> <el_teu_token>

    O bé amb el token en una variable d'entorn (recomanat, més segur):
        export KLOTSKI_TOKEN="el_teu_token_aqui"
        python src/rate.py klotski 4.5

Arguments:
    id_puzzle   Identificador del puzzle al repositori (ex: "klotski", "sample1") o el seu índex numèric ("50")
    puntuació   Valor entre 0.0 i 5.0 (p.ex. 3.5), o la paraula "auto" per auto-avaluar
    token       El token personal per autenticar-se (opcional si s'usa la variable d'entorn KLOTSKI_TOKEN)

Què fa:
    Fa una petició HTTP POST al servidor https://klotski.pauek.dev
    amb l'identificador del puzzle, el token i la puntuació.
    El servidor guarda la vostra valoració (o la sobreescriu si ja n'hi havia una).

Per qué és útil:
    Permet contribuir al rànking col·laboratiu dels puzzles.
    Totes les valoracions dels estudiants s'acumulen i generen
    una mitjana que classifica els puzzles del millor al pitjor.

IMPORTANT:
    Necessiteu un token personal que us donarà el professor per email.
    No compartiu el token amb ningú — identifica les vostres contribucions.
"""

import sys
import json
import os
import urllib.request
import urllib.error
from pathlib import Path

# URL base del servidor de la pràctica
SERVIDOR = "https://klotski.pauek.dev"


def envia_valoracio(id_puzzle, puntuacio, token):
    """
    Envia una valoració per a un puzzle al servidor.

    Paràmetres:
        id_puzzle  (str):   Identificador del puzzle (ex: "klotski")
        puntuacio  (float o int): Valor entre 0.0 i 5.0
        token      (str):   Token personal d'autenticació

    Retorna:
        True si l'enviament ha anat bé, False si hi ha hagut algun error.
    """
    # Comprovem que la puntuació és vàlida
    if not (0.0 <= puntuacio <= 5.0):
        print(f"Error: la puntuació ha de ser entre 0.0 i 5.0 (rebuda: {puntuacio})")
        return False

    # Construïm la URL de l'endpoint
    # Segons el README: POST /api/puzzles/[ID]/votes
    url = f"{SERVIDOR}/api/puzzles/{id_puzzle}/votes"

    # Preparem el cos de la petició en format JSON
    # El servidor espera la clau 'stars' i que el valor sigui un INT
    dades = {
        "stars": int(puntuacio)
    }
    cos_json = json.dumps(dades).encode("utf-8")  # Convertim a bytes

    # Creem la petició HTTP amb les capçaleres necessàries
    # La capçalera "Authorization" porta el token per identificar-nos
    peticio = urllib.request.Request(
        url,
        data=cos_json,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }
    )

    # Fem la petició i gestionem els possibles errors
    try:
        with urllib.request.urlopen(peticio) as resposta:
            codi = resposta.getcode()
            cos_resposta = resposta.read().decode("utf-8")

            if codi == 200 or codi == 201:
                print(f"✅ Valoració enviada correctament!")
                print(f"   Puzzle: {id_puzzle}")
                print(f"   Puntuació: {int(puntuacio)} / 5.0")

                # Intentem mostrar la resposta del servidor si és JSON
                try:
                    resposta_json = json.loads(cos_resposta)
                    print(f"   Resposta: {resposta_json}")
                except json.JSONDecodeError:
                    pass  # Si no és JSON, no passa res

                return True
            else:
                print(f"❌ El servidor ha retornat codi inesperat: {codi}")
                return False

    except urllib.error.HTTPError as error:
        # Error HTTP (p.ex. 401 Unauthorized, 404 Not Found, etc.)
        missatge = error.read().decode("utf-8")
        print(f"❌ Error HTTP {error.code}: {error.reason}")
        print(f"   Detalls: {missatge}")

        if error.code == 401:
            print("   → El token és incorrecte o ha caducat.")
        elif error.code == 404:
            print(f"   → El puzzle '{id_puzzle}' no existeix al servidor.")

        return False

    except urllib.error.URLError as error:
        # Error de connexió (p.ex. sense internet, servidor caigut)
        print(f"❌ Error de connexió: {error.reason}")
        print("   → Comproveu que teniu connexió a internet.")
        return False


# -------------------------------------------------------------------------
# PROGRAMA PRINCIPAL
# -------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Uso: python src/rate.py <id_puzzle> <puntuació> [token]")
        print("     python src/rate.py all [token]")
        print("Exemple: python src/rate.py klotski 4.5 el_teu_token")
        sys.exit(1)

    id_puzzle = sys.argv[1]

    # --- PUJADA MASSIVA DE RATINGS ---
    if id_puzzle == "all":
        ratings_path = Path("puzzles/downloads/ratings.json")
        if not ratings_path.exists():
            print("❌ Error: No s'ha trobat puzzles/downloads/ratings.json.")
            print("   Has d'executar primer 'make rate_all' per generar i recalibrar els ratings.")
            sys.exit(1)

        with open(ratings_path) as f:
            ratings = json.load(f)

        token = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("KLOTSKI_TOKEN")
        if not token:
            print("❌ Error: cal proporcionar el token d'autenticació.")
            print("   Opció 1: python src/rate.py all <token>")
            print("   Opció 2: export KLOTSKI_TOKEN='token' i després executar")
            sys.exit(1)

        print(f"Subint valoracions de {len(ratings)} puzzles...")
        exitos = 0
        errors = 0

        for clau_curta, data in sorted(ratings.items()):
            id_real = data["id_real"]
            puntuacio_float = data.get("puntuacio_recalibrada", data.get("puntuacio_original", 0.0))
            puntuacio = int(round(puntuacio_float))

            print(f"\n[{clau_curta}] Enviant valoració de {puntuacio} estrelles (recalibrada: {puntuacio_float:.2f})...")
            if envia_valoracio(id_real, puntuacio, token):
                exitos += 1
            else:
                errors += 1

        print()
        print("══════════════════════════════════════════════════════════════════════")
        print("  RESUM DE LA PUJADA MASSIVA")
        print("══════════════════════════════════════════════════════════════════════")
        print(f"  Enviats correctament: {exitos}")
        print(f"  Amb errors:           {errors}")
        print("══════════════════════════════════════════════════════════════════════")
        if errors > 0:
            sys.exit(1)
        sys.exit(0)

    # --- PUJADA D'UN ÚNIC PUZZLE ---
    if len(sys.argv) < 3:
        print("❌ Error: cal especificar la puntuació per a un únic puzzle.")
        print("Uso: python src/rate.py <id_puzzle> <puntuació> [token]")
        sys.exit(1)

    # Comprovem si ens han passat un índex numèric (ex: '50') i busquem el seu ID real
    id_real = id_puzzle
    fitxer_puzzle = f"puzzles/{id_puzzle}.json"
    
    if os.path.exists("puzzles/index.json"):
        with open("puzzles/index.json") as f:
            index_puzzles = json.load(f)
            
        clau = id_puzzle
        if id_puzzle.isdigit():
            clau = f"{int(id_puzzle):02d}"  # Per si passem "5" en comptes de "05"
            
        if clau in index_puzzles:
            id_real = index_puzzles[clau]
            fitxer_puzzle = f"puzzles/downloads/{clau}.json"
    
    if sys.argv[2] == "auto":
        print("Calculant puntuació automàticament...")
        from eval import main as eval_main
        puntuacio_float = eval_main(fitxer_puzzle)
        puntuacio = int(round(puntuacio_float))
        print(f"Puntuació convertida a enter: {puntuacio}")
        print()
    else:
        try:
            puntuacio = int(round(float(sys.argv[2])))
        except ValueError:
            print("❌ Error: la puntuació ha de ser un número decimal (ex: 4.5) o 'auto'")
            sys.exit(1)

    # Obtenim el token: tercer argument o variable d'entorn
    token = sys.argv[3] if len(sys.argv) > 3 else os.environ.get("KLOTSKI_TOKEN")

    if not token:
        print("❌ Error: cal proporcionar el token d'autenticació.")
        print("   Opció 1: python src/rate.py <id> <puntuació> <token>")
        print("   Opció 2: export KLOTSKI_TOKEN='token' i després executar")
        sys.exit(1)

    print("Enviant valoració al servidor...")
    print(f"  Puzzle (ID real): {id_real}")
    print(f"  Puntuació: {puntuacio} / 5.0")
    print()

    # Enviem la valoració
    exit_correcte = envia_valoracio(id_real, puntuacio, token)

    # Sortim amb codi d'error si no ha anat bé
    # (útil per si rate.py es crida des d'un altre script)
    if not exit_correcte:
        sys.exit(1)


if __name__ == "__main__":
    main()
