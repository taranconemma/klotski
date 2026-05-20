"""
rate_all.py — Avaluació massiva i recalibració de llindars d'eval.py

Avalua tots els puzzles descarregats, analitza la distribució real de les mètriques,
proposa una recalibració dels llindars d'eval.py de forma informada
i desa els resultats a puzzles/downloads/ratings.json.

Ús:
    python src/rate_all.py

Genera:
    puzzles/downloads/calibracio.json  — estadístics de valors concrets de totes les mètriques
    puzzles/downloads/ratings.json     — puntuacions originals i recalibrades de cada puzzle

No modifica mai eval.py. Al final mostra un bloc de codi llest per copiar-enganxar.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import date
from pathlib import Path

from eval import MAX_ESTATS, MAX_SOLUCIO, MAX_DIAMETRE, MAX_PARANYS, MAX_PONTS, MAX_ENGANY
from graph_tool.all import Graph, load_graph #type:ignore

from graph import carregar_o_construir_graf, LIMIT_NODES
from puzzle import Puzzle
from eval import puntua_puzzle


def extraure_valors_concrets(g: Graph, puzzle: Puzzle) -> dict:
    """Delega en puntua_puzzle d'eval.py per obtenir els valors bruts reals.
    Si el graf és buit (timeout o límit de nodes), retorna zeros.
    """
    num_nodes = g.num_vertices()
    zeros = {"num_nodes": num_nodes, "num_arestes": g.num_edges(), "num_goals": 0,
             "moviments_solucio": 0, "diametre": 0,
             "grau_mitja": 0.0, "eficiencia_cami": 0.0, "paranys_ponderat": 0.0,
             "ponts_al_cami": 0, "engany_gradient": 0}

    if num_nodes == 0 or num_nodes > LIMIT_NODES: return zeros

    node_inici     = next(v for v in g.vertices() if g.vp["is_start"][v])
    nodes_objectiu = [v for v in g.vertices() if g.vp["is_goal"][v]]

    _, _, valors_bruts = puntua_puzzle(g, puzzle, node_inici, nodes_objectiu)

    if not valors_bruts:
        return zeros

    return valors_bruts


# ─────────────────────────────────────────────────────────────────────────────
# ESTADÍSTICS DE DISTRIBUCIÓ
# ─────────────────────────────────────────────────────────────────────────────

def calcular_estadistics(valors: list[float]) -> dict:
    """Calcula mínim, màxim, mitjana i percentils d'una llista de valors."""
    if not valors:
        return {}
    sorted_v = sorted(valors)
    n = len(sorted_v)

    def percentil(p: float) -> float:
        idx = (p / 100) * (n - 1)
        low, high = int(idx), min(int(idx) + 1, n - 1)
        frac = idx - low
        return sorted_v[low] * (1 - frac) + sorted_v[high] * frac

    return {
        "min":    round(sorted_v[0], 4),
        "max":    round(sorted_v[-1], 4),
        "mitjana": round(sum(sorted_v) / n, 4),
        "p25":    round(percentil(25), 4),
        "p50":    round(percentil(50), 4),
        "p75":    round(percentil(75), 4),
        "p90":    round(percentil(90), 4),
    }


# ─────────────────────────────────────────────────────────────────────────────
# AVALUACIÓ AMB LLINDARS PERSONALITZATS (mateixa fórmula que eval.py)
# ─────────────────────────────────────────────────────────────────────────────

def puntua_amb_llindars(metriques: dict, llindars: dict) -> float:
    """Calcula la puntuació (0–5) amb llindars configurables.

    Usa exactament la mateixa fórmula i pesos que eval.py.
    """
    def normalitza_log(n: float, llindar: float) -> float:
        return min(math.log(n + 1) / math.log(llindar + 1), 1.0) if n > 0 else 0.0

    def normalitza_lin(v: float, llindar: float) -> float:
        return min(v / llindar, 1.0) if llindar > 0 else 0.0

    m1 = normalitza_log(metriques["num_nodes"],         llindars["estats"])
    m2 = normalitza_lin(metriques["moviments_solucio"], llindars["solucio"])
    m3 = normalitza_lin(metriques["diametre"],          llindars["diametre"])
    m4 = metriques.get("eficiencia_cami", 0.0)          # ja és 0–1
    m5 = normalitza_lin(metriques["paranys_ponderat"],  llindars["paranys"])
    m6 = normalitza_lin(metriques["ponts_al_cami"],     llindars["ponts"])
    m7 = normalitza_lin(metriques["engany_gradient"],   llindars["engany"])

    puntuacio_0_1 = (
        0.10 * m1 +
        0.30 * m2 +
        0.10 * m3 +
        0.10 * m4 +
        0.10 * m5 +
        0.10 * m6 +
        0.20 * m7
    )
    return round(puntuacio_0_1 * 5.0, 3)


# ─────────────────────────────────────────────────────────────────────────────
# CALIBRACIÓ
# ─────────────────────────────────────────────────────────────────────────────

def analitzar_calibracio(totes_metriques: list[dict]) -> dict:
    """Analitza la distribució real i proposa nous llindars (percentil 90)."""

    camps = {
        "estats":   "num_nodes",
        "solucio":  "moviments_solucio",
        "diametre": "diametre",
        "paranys":  "paranys_ponderat",
        "ponts":    "ponts_al_cami",
        "engany":   "engany_gradient",
    }
    llindars_actuals = {
        "estats":   MAX_ESTATS,
        "solucio":  MAX_SOLUCIO,
        "diametre": MAX_DIAMETRE,
        "paranys":  MAX_PARANYS,
        "ponts":    MAX_PONTS,
        "engany":   MAX_ENGANY,
    }

    estadistics: dict[str, dict] = {}
    nous_llindars: dict[str, float] = {}

    for clau, camp in camps.items():
        valors = [m[camp] for m in totes_metriques]
        stats = calcular_estadistics(valors)
        estadistics[clau] = stats
        nous_llindars[clau] = round(stats["p90"], 4) if stats else llindars_actuals[clau]

    def percentil_del_valor(valors: list[float], llindar: float) -> float:
        per_sota = sum(1 for v in valors if v < llindar)
        return round(100 * per_sota / len(valors), 1) if valors else 0.0

    def classifica(pct: float) -> str:
        if pct > 85: return "⚠️  MASSA LAX"
        if pct < 40: return "⚠️  MASSA EXIGENT"
        return "✅ BEN CALIBRAT"

    percentils_actuals: dict[str, float] = {}
    classificacio: dict[str, str] = {}
    for clau, camp in camps.items():
        valors = [m[camp] for m in totes_metriques]
        pct = percentil_del_valor(valors, llindars_actuals[clau])
        percentils_actuals[clau] = pct
        classificacio[clau] = classifica(pct)

    return {
        "estadistics":               estadistics,
        "llindars_actuals":          llindars_actuals,
        "percentil_llindars_actuals": percentils_actuals,
        "classificacio_llindars":    classificacio,
        "nous_llindars_proposats":   nous_llindars,
    }


# ─────────────────────────────────────────────────────────────────────────────
# IMPRESSIÓ DE RESULTATS
# ─────────────────────────────────────────────────────────────────────────────

def imprime_taula_calibracio(calibracio: dict) -> None:
    """Mostra la taula comparativa dels llindars per pantalla."""
    actuals = calibracio["llindars_actuals"]
    nous    = calibracio["nous_llindars_proposats"]
    pcts    = calibracio["percentil_llindars_actuals"]
    classis = calibracio["classificacio_llindars"]

    etiquetes = [
        ("estats",   "Nombre d'estats"),
        ("solucio",  "Moviments sol."),
        ("diametre", "Diàmetre"),
        ("paranys",  "Densitat paranys"),
        ("ponts",    "Ponts crítics"),
        ("engany",   "Engany gradient"),
    ]

    print()
    print("═" * 78)
    print("  ANÀLISI DE CALIBRACIÓ DELS LLINDARS")
    print("═" * 78)
    print(f"  {'MÈTRICA':<20} {'ACTUAL':>12} {'%TILE':>8} {'PROPOSAT':>12}  DIAGNÒSTIC")
    print("─" * 78)
    for clau, label in etiquetes:
        actual = actuals[clau]
        nou    = nous[clau]
        pct    = pcts[clau]
        diag   = classis[clau]
        # Formatem diferent si és enter o float
        if isinstance(actual, int) or actual == int(actual):
            print(f"  {label:<20} {int(actual):>12,} {pct:>7.1f}% {int(nou):>12,}  {diag}")
        else:
            print(f"  {label:<20} {actual:>12.4f} {pct:>7.1f}% {nou:>12.4f}  {diag}")
    print("═" * 78)


def imprime_histograma(ratings: dict, clau: str = "puntuacio_recalibrada") -> None:
    """Mostra un histograma en text de la distribució de puntuacions."""
    franges = [0] * 6
    for r in ratings.values():
        p = r.get(clau, 0)
        idx = min(int(p), 5)
        franges[idx] += 1

    print()
    print("═" * 50)
    print(f"  DISTRIBUCIÓ DE PUNTUACIONS ({clau})")
    print("═" * 50)
    total = sum(franges)
    for i, count in enumerate(franges):
        rang  = f"{i}-{i+1}" if i < 5 else "= 5"
        barra = "█" * count
        print(f"  {rang:>5} ⭐  {barra:<35} ({count}/{total})")
    print("═" * 50)


def imprime_bloc_codi(nous_llindars: dict, n_puzzles: int) -> None:
    """Mostra un bloc de Python llest per copiar-enganxar a eval.py."""
    avui = date.today().isoformat()
    nl = nous_llindars

    print()
    print("═" * 78)
    print("  BLOC DE CODI PER COPIAR I ENGANXAR A eval.py")
    print(f"  (calibrat el {avui} amb {n_puzzles} puzzles)")
    print("─" * 78)
    print()
    print(f"    # --- Calibració automàtica {avui} ({n_puzzles} puzzles) ---")
    print(f"    MAX_ESTATS:   int   = {int(nl['estats'])}   # nodes")
    print(f"    MAX_SOLUCIO:  int   = {int(nl['solucio'])}   # moviments")
    print(f"    MAX_DIAMETRE: int   = {int(nl['diametre'])}   # pseudo-diàmetre")
    print(f"    MAX_PARANYS:  float = {nl['paranys']}   # densitat paranys ponderada")
    print(f"    MAX_PONTS:    int   = {int(nl['ponts'])}   # ponts en el camí òptim")
    print(f"    MAX_ENGANY:   int   = {int(nl['engany'])}   # caselles d'allunyament màxim")
    print()
    print("═" * 78)


# ─────────────────────────────────────────────────────────────────────────────
# PROGRAMA PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    index_path = Path("puzzles/index.json")
    if not index_path.exists():
        print("No s'ha trobat puzzles/index.json. Executa primer 'make descarrega'.")
        sys.exit(1)

    with open(index_path) as f:
        index: dict[str, str] = json.load(f)

    n_total = len(index)
    print(f"Analitzant {n_total} puzzles...")
    print()

    llindars_actuals = {
        "estats":   MAX_ESTATS,
        "solucio":  MAX_SOLUCIO,
        "diametre": MAX_DIAMETRE,
        "paranys":  MAX_PARANYS,
        "ponts":    MAX_PONTS,
        "engany":   MAX_ENGANY,
    }

    ratings_path = Path("puzzles/downloads/ratings.json")
    cache_ratings = {}
    if ratings_path.exists():
        try:
            with open(ratings_path) as f:
                cache_ratings = json.load(f)
        except Exception:
            pass

    totes_metriques: list[dict] = []
    resultats_per_puzzle: dict  = {}
    errors: list[str]           = []

    for clau_curta, id_real in sorted(index.items()):
        fitxer = Path(f"puzzles/downloads/{clau_curta}.json")
        if not fitxer.exists():
            print(f"  ⚠️  {clau_curta}: fitxer no trobat, ometent.")
            errors.append(clau_curta)
            continue

        # Comprovem si ja tenim les mètriques calculades a la caché de ratings.json
        if clau_curta in cache_ratings and "metriques" in cache_ratings[clau_curta]:
            metriques = cache_ratings[clau_curta]["metriques"]
            print(f"  [{clau_curta}] Carregant de la caché... (nodes={metriques['num_nodes']:,} sol={metriques['moviments_solucio']})")
            totes_metriques.append(metriques)
            puntuacio_original = puntua_amb_llindars(metriques, llindars_actuals)
            resultats_per_puzzle[clau_curta] = {
                "id_real":            id_real,
                "metriques":          metriques,
                "puntuacio_original": puntuacio_original,
            }
            continue

        print(f"  [{clau_curta}] Processant...", end=" ", flush=True)

        try:
            g = carregar_o_construir_graf(fitxer)
            if g.num_vertices() == 0:
                metriques = {
                    "num_nodes": 0, "num_arestes": 0, "num_goals": 0,
                    "moviments_solucio": 0, "diametre": 0,
                    "grau_mitja": 0.0, "eficiencia_cami": 0.0, "paranys_ponderat": 0.0,
                    "ponts_al_cami": 0, "engany_gradient": 0
                }
            else:
                puzzle = Puzzle.from_json(fitxer.read_text())
                metriques = extraure_valors_concrets(g, puzzle)
        except Exception as e:
            metriques = {
                "num_nodes": 0, "num_arestes": 0, "num_goals": 0,
                "moviments_solucio": 0, "diametre": 0,
                "grau_mitja": 0.0, "eficiencia_cami": 0.0, "paranys_ponderat": 0.0,
                "ponts_al_cami": 0, "engany_gradient": 0
            }
            print(f"  Error inesperat ({type(e).__name__}: {e}). Assignant puntuació 0.")
            errors.append(clau_curta)

        totes_metriques.append(metriques)
        puntuacio_original = puntua_amb_llindars(metriques, llindars_actuals)

        resultats_per_puzzle[clau_curta] = {
            "id_real":            id_real,
            "metriques":          metriques,
            "puntuacio_original": puntuacio_original,
        }

        print(
            f"nodes={metriques['num_nodes']:,}  sol={metriques['moviments_solucio']}  "
            f"diam={metriques['diametre']}  "
            f"paranys={metriques['paranys_ponderat']:.4f}  "
            f"ponts={metriques['ponts_al_cami']}  "
            f"engany={metriques['engany_gradient']}  "
            f"→ {puntuacio_original:.2f}★"
        )

    if not totes_metriques:
        print("❌ No s'ha pogut analitzar cap puzzle.")
        sys.exit(1)

    # Calibració i recalcul amb nous llindars
    calibracio = analitzar_calibracio(totes_metriques)
    nous = calibracio["nous_llindars_proposats"]

    for clau_curta, data in resultats_per_puzzle.items():
        data["puntuacio_recalibrada"] = puntua_amb_llindars(data["metriques"], nous)

    # Desar fitxers
    calibracio_path = Path("puzzles/downloads/calibracio.json")
    with open(calibracio_path, "w") as f:
        json.dump(calibracio, f, indent=4)
    print(f"\n✅ Estadístics desats a {calibracio_path}")

    ratings_path = Path("puzzles/downloads/ratings.json")
    with open(ratings_path, "w") as f:
        json.dump(resultats_per_puzzle, f, indent=4)
    print(f"✅ Puntuacions desades a {ratings_path}")

    # Mostrar resultats finals
    imprime_taula_calibracio(calibracio)
    imprime_histograma(resultats_per_puzzle, "puntuacio_recalibrada")
    imprime_bloc_codi(nous, len(totes_metriques))

    if errors:
        print(f"\n⚠️  Puzzles omesos per error: {', '.join(errors)}")


if __name__ == "__main__":
    main()