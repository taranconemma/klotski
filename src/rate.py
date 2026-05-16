# rate.py. Donat un identificador de puzzle del repositori, 
# envia una valoració entre 0 i 5 estrelles.

"""
rate.py — Envia la valoració d'un puzzle al repositori de Klotski

Uso:
    python src/rate.py <id_puzzle> <puntuació> --token <el_teu_token>

    O bé amb el token en una variable d'entorn (recomanat, més segur):
        export KLOTSKI_TOKEN="el_teu_token_aqui"
        python src/rate.py klotski 4.5

Arguments:
    id_puzzle   Identificador del puzzle al repositori (ex: "klotski", "sample1")
    puntuació   Valor entre 0.0 i 5.0 (p.ex. 3.5)

Opcions:
    --token     El token personal per autenticar-se
                (alternativament, poseu-lo a la variable d'entorn KLOTSKI_TOKEN)

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
import argparse
import os
import urllib.request
import urllib.error


# URL base del servidor de la pràctica
SERVIDOR = "https://klotski.pauek.dev"


def envia_valoracio(id_puzzle, puntuacio, token):
    """
    Envia una valoració per a un puzzle al servidor.

    Paràmetres:
        id_puzzle  (str):   Identificador del puzzle (ex: "klotski")
        puntuacio  (float): Valor entre 0.0 i 5.0
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
    dades = {
        "rating": puntuacio
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
                print(f"   Puntuació: {puntuacio} / 5.0")

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
    # Configurem els arguments de la línia de comandes
    parser = argparse.ArgumentParser(
        description="Envia la valoració d'un puzzle al repositori de Klotski"
    )
    parser.add_argument(
        "id_puzzle",
        help="Identificador del puzzle al repositori (ex: 'klotski', 'sample1')"
    )
    parser.add_argument(
        "puntuacio",
        type=float,
        help="Puntuació entre 0.0 i 5.0 (p.ex. 3.5)"
    )
    parser.add_argument(
        "--token",
        type=str,
        default=None,
        help="Token personal d'autenticació (o poseu-lo a KLOTSKI_TOKEN)"
    )

    args = parser.parse_args()

    # Obtenim el token: primer mirem l'argument --token,
    # si no hi és, mirem la variable d'entorn KLOTSKI_TOKEN
    token = args.token or os.environ.get("KLOTSKI_TOKEN")

    if not token:
        print("❌ Error: cal proporcionar el token d'autenticació.")
        print("   Opció 1: python src/rate.py <id> <puntuació> --token <token>")
        print("   Opció 2: export KLOTSKI_TOKEN='token' i després executar")
        sys.exit(1)

    # Validació bàsica de la puntuació
    if not (0.0 <= args.puntuacio <= 5.0):
        print(f"❌ Error: la puntuació ha de ser entre 0.0 i 5.0")
        sys.exit(1)

    print(f"Enviant valoració al servidor...")
    print(f"  Puzzle:    {args.id_puzzle}")
    print(f"  Puntuació: {args.puntuacio} / 5.0")
    print()

    # Enviem la valoració
    exit_correcte = envia_valoracio(args.id_puzzle, args.puntuacio, token)

    # Sortim amb codi d'error si no ha anat bé
    # (útil per si rate.py es crida des d'un altre script)
    if not exit_correcte:
        sys.exit(1)


if __name__ == "__main__":
    main()
