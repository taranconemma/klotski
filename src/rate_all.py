"""
rate_all.py — Avaluació massiva i recalibració de llindars d'eval.py

Avalua tots els puzzles descarregats, analitza la distribució real de les mètriques,
proposa una recalibració dels llindars d'eval.py de forma informada
i desa els resultats a puzzles/downloads/ratings.json.

Ús:
    python src/rate_all.py

Genera:
    puzzles/downloads/calibracio.json  — estadístics bruts de totes les mètriques
    puzzles/downloads/ratings.json     — puntuacions originals i recalibrades de cada puzzle

No modifica mai eval.py. Al final mostra un bloc de codi llest per copiar-enganxar.
"""

import json
import math
import sys
from datetime import date
from pathlib import Path

import graph_tool.all as gt
from graph_tool.all import shortest_distance, label_components, pseudo_diameter

from graph import build_graph, TIMEOUT_SEGONS
from puzzle import Puzzle


# -------------------------------------------------------------------------
# LLINDARS ACTUALS D'EVAL.PY (hard-coded aquí per poder comparar-los)
# -------------------------------------------------------------------------

LLINDAR_ESTATS    = 10_000   # log(n) / log(LLINDAR) → 1.0
LLINDAR_SOLUCIO   = 30       # passos → 1.0
LLINDAR_DIAMETRE  = 50       # diametre → 1.0
# La mesura de components connexes no té llindar (és fraccio_gran directament)


# -------------------------------------------------------------------------
# CÀRREGA DEL GRAF (reutilitzant la caché de .graphml)
# -------------------------------------------------------------------------

def carregar_o_construir_graf(fitxer_json: Path) -> gt.Graph:
    """Carrega el graf des del .graphml si existeix, altrament el construeix."""
    graphml_path = fitxer_json.with_suffix(".graphml")
    if graphml_path.exists():
        return gt.load_graph(str(graphml_path))
    else:
        puzzle = Puzzle.from_json(fitxer_json.read_text())
        g = build_graph(puzzle)  # Pot llençar TimeoutError si TIMEOUT_ACTIVAT=True a graph.py
        g.save(str(graphml_path))
        return g


# -------------------------------------------------------------------------
# EXTRACCIÓ DE MÈTRIQUES EN BRUT
# -------------------------------------------------------------------------

def extraure_metriques_brutes(g: gt.Graph) -> dict:
    """
    Extreu les mètriques numèriques reals d'un graf (sense normalitzar).

    Retorna un diccionari amb:
        - num_nodes: nombre de nodes
        - num_arestes: nombre d'arestes
        - moviments_solucio: longitud del camí mínim fins a un node goal
        - diametre: pseudo-diàmetre del graf
        - fraccio_component_gran: fracció de nodes a la component connexa més gran
        - fraccio_atzucacs: fracció de nodes des dels quals NO es pot arribar a cap goal
        - grau_mitja: nombre mitjà d'arestes per node
    """
    num_nodes   = g.num_vertices()
    num_arestes = g.num_edges()

    # Node inicial i nodes objectiu
    node_inici   = next(v for v in g.vertices() if g.vp["is_start"][v])
    nodes_goal   = [v for v in g.vertices() if g.vp["is_goal"][v]]
    num_goals    = len(nodes_goal)

    # Longitud de la solució òptima (BFS des de l'inici)
    dist_from_start = shortest_distance(g, source=node_inici)
    moviments_solucio = 0
    if nodes_goal:
        moviments_solucio = min(
            int(dist_from_start[v]) for v in nodes_goal
            if int(dist_from_start[v]) < 2**30
        )

    # Diàmetre
    diametre, _ = pseudo_diameter(g) if num_nodes >= 2 else (0, None)

    # Component connexa dominant
    _, histograma = label_components(g)
    component_gran   = max(histograma) if histograma else 0
    fraccio_component_gran = component_gran / num_nodes if num_nodes > 0 else 0.0

    # Atzucacs: nodes des dels quals no es pot arribar a cap goal
    # Fem un BFS invers: des de tots els goals cap enrere
    # Si un node no és assolible des de cap goal (en graf no dirigit = mateixa component),
    # no pot guanyar. Com és no dirigit, usem la distància des de cada goal.
    # Un node és un atzucac si cap camí que passi per ell porta a un goal.
    # Aproximació: nodes a components sense cap goal.
    etiquetes, histograma_comp = label_components(g)
    components_amb_goal: set[int] = set()
    for v in nodes_goal:
        components_amb_goal.add(int(etiquetes[v]))

    atzucacs = sum(
        1 for v in g.vertices()
        if int(etiquetes[v]) not in components_amb_goal
    )
    fraccio_atzucacs = atzucacs / num_nodes if num_nodes > 0 else 0.0

    # Grau mitjà
    grau_mitja = (2 * num_arestes) / num_nodes if num_nodes > 0 else 0.0

    return {
        "num_nodes":             num_nodes,
        "num_arestes":           num_arestes,
        "num_goals":             num_goals,
        "moviments_solucio":     moviments_solucio,
        "diametre":              int(diametre),
        "fraccio_component_gran": round(fraccio_component_gran, 4),
        "fraccio_atzucacs":      round(fraccio_atzucacs, 4),
        "grau_mitja":            round(grau_mitja, 4),
        "eficiencia_cami":       round(moviments_solucio / diametre, 4) if diametre > 0 else 0.0,
    }


# -------------------------------------------------------------------------
# ESTADÍSTICS DE DISTRIBUCIÓ
# -------------------------------------------------------------------------

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
        "min":    round(sorted_v[0], 2),
        "max":    round(sorted_v[-1], 2),
        "mitjana": round(sum(sorted_v) / n, 2),
        "p25":    round(percentil(25), 2),
        "p50":    round(percentil(50), 2),
        "p75":    round(percentil(75), 2),
        "p90":    round(percentil(90), 2),
    }


# -------------------------------------------------------------------------
# AVALUACIÓ AMB LLINDARS PERSONALITZATS
# -------------------------------------------------------------------------

def puntua_amb_llindars(metriques: dict, llindar_estats: float,
                         llindar_solucio: float, llindar_diametre: float) -> float:
    """
    Calcula la puntuació (0–5) igual que eval.py però amb llindars configurables.
    Usa exactament la mateixa fórmula i pesos que eval.py.
    """
    n = metriques["num_nodes"]
    m1 = min(math.log(n + 1) / math.log(llindar_estats + 1), 1.0) if n > 0 else 0.0

    dist = metriques["moviments_solucio"]
    m2 = min(dist / llindar_solucio, 1.0) if llindar_solucio > 0 else 0.0

    m3 = metriques["fraccio_component_gran"]

    d = metriques["diametre"]
    m4 = min(d / llindar_diametre, 1.0) if llindar_diametre > 0 else 0.0

    # Eficiència del camí: moviments_solucio / diametre (sense llindar extern, ja és 0–1)
    m5 = metriques.get("eficiencia_cami", 0.0)

    # Mateixos pesos que eval.py: 20 + 35 + 15 + 15 + 15 = 100%
    puntuacio_0_1 = 0.20 * m1 + 0.35 * m2 + 0.15 * m3 + 0.15 * m4 + 0.15 * m5
    return round(puntuacio_0_1 * 5.0, 3)


# -------------------------------------------------------------------------
# CALIBRACIÓ: ANÀLISI DE PERCENTILS I PROPOSTA DE NOUS LLINDARS
# -------------------------------------------------------------------------

def analitzar_calibracio(totes_metriques: list[dict]) -> dict:
    """
    Analitza la distribució real de les mètriques i proposa nous llindars
    basant-se en el percentil 80 de cada distribució.
    """
    # Recollim valors bruts
    nodes_vals        = [m["num_nodes"]         for m in totes_metriques]
    solucio_vals      = [m["moviments_solucio"] for m in totes_metriques]
    diametre_vals     = [m["diametre"]          for m in totes_metriques]
    eficiencia_vals   = [m["eficiencia_cami"]   for m in totes_metriques]

    stats_nodes       = calcular_estadistics(nodes_vals)
    stats_solucio     = calcular_estadistics(solucio_vals)
    stats_diametre    = calcular_estadistics(diametre_vals)
    stats_eficiencia  = calcular_estadistics(eficiencia_vals)

    # Percentil en el qual cau el llindar actual (quants puzzles estan PER SOTA del llindar)
    def percentil_del_valor(valors: list, llindar: float) -> float:
        per_sota = sum(1 for v in valors if v < llindar)
        return round(100 * per_sota / len(valors), 1) if valors else 0.0

    pct_llindar_estats   = percentil_del_valor(nodes_vals,    LLINDAR_ESTATS)
    pct_llindar_solucio  = percentil_del_valor(solucio_vals,  LLINDAR_SOLUCIO)
    pct_llindar_diametre = percentil_del_valor(diametre_vals, LLINDAR_DIAMETRE)

    def classifica_llindar(pct: float) -> str:
        if pct > 85:   return "⚠️  MASSA LAX (massa fàcil d'arribar a 1.0)"
        if pct < 40:   return "⚠️  MASSA EXIGENT (gairebé ningú arriba a 1.0)"
        return "✅ BEN CALIBRAT"

    # Nous llindars proposats: percentil 80 del dataset real
    nous_llindars = {
        "llindar_estats":   round(stats_nodes["p90"]),
        "llindar_solucio":  round(stats_solucio["p90"]),
        "llindar_diametre": round(stats_diametre["p90"]),
    }

    return {
        "estadistics": {
            "nodes":      stats_nodes,
            "solucio":    stats_solucio,
            "diametre":   stats_diametre,
            "eficiencia": stats_eficiencia,
        },
        "llindars_actuals": {
            "estats":   LLINDAR_ESTATS,
            "solucio":  LLINDAR_SOLUCIO,
            "diametre": LLINDAR_DIAMETRE,
        },
        "percentil_llindars_actuals": {
            "estats":   pct_llindar_estats,
            "solucio":  pct_llindar_solucio,
            "diametre": pct_llindar_diametre,
        },
        "classificacio_llindars": {
            "estats":   classifica_llindar(pct_llindar_estats),
            "solucio":  classifica_llindar(pct_llindar_solucio),
            "diametre": classifica_llindar(pct_llindar_diametre),
        },
        "nous_llindars_proposats": nous_llindars,
    }


# -------------------------------------------------------------------------
# IMPRESSIÓ DE RESULTATS
# -------------------------------------------------------------------------

def imprime_taula_calibracio(calibracio: dict) -> None:
    """Mostra per pantalla la taula comparativa dels llindars."""
    actuals = calibracio["llindars_actuals"]
    nous    = calibracio["nous_llindars_proposats"]
    pcts    = calibracio["percentil_llindars_actuals"]
    classis = calibracio["classificacio_llindars"]

    print()
    print("═" * 70)
    print("  ANÀLISI DE CALIBRACIÓ DELS LLINDARS")
    print("═" * 70)
    print(f"  {'MÈTRICA':<18} {'ACTUAL':>10} {'%TILE ACTUAL':>14} {'PROPOSAT':>10}  DIAGNÒSTIC")
    print("─" * 70)
    for key, label in [("estats", "Nombre d'estats"), ("solucio", "Moviments sol."), ("diametre", "Diàmetre")]:
        print(f"  {label:<18} {actuals[key]:>10,} {pcts[key]:>13.1f}% {nous['llindar_' + key]:>10,}  {classis[key]}")
    print("═" * 70)


def imprime_histograma(ratings: dict, clau: str = "puntuacio_recalibrada") -> None:
    """Mostra un histograma en text de la distribució de puntuacions."""
    franges = [0] * 6  # 0–1, 1–2, 2–3, 3–4, 4–5, =5
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
        rang = f"{i}-{i+1}" if i < 5 else "= 5"
        barra = "█" * count
        print(f"  {rang:>5} ⭐  {barra:<35} ({count}/{total})")
    print("═" * 50)


def imprime_bloc_codi(nous_llindars: dict, n_puzzles: int) -> None:
    """Mostra un bloc de Python llest per copiar-enganxar a eval.py."""
    avui = date.today().isoformat()
    print()
    print("═" * 70)
    print("  BLOC DE CODI PER COPIAR I ENGANXAR A eval.py")
    print(f"  (calibrat el {avui} amb {n_puzzles} puzzles)")
    print("─" * 70)
    print()
    print(f"    # --- Calibració automàtica {avui} ({n_puzzles} puzzles) ---")
    print(f"    max_esperat = {nous_llindars['llindar_estats']:,}   # mesura_nombre_estats()")
    print(f"    max_esperat = {nous_llindars['llindar_solucio']}   # mesura_longitud_solucio()")
    print(f"    max_esperat = {nous_llindars['llindar_diametre']}   # mesura_diametre()")
    print()
    print("═" * 70)


# -------------------------------------------------------------------------
# PROGRAMA PRINCIPAL
# -------------------------------------------------------------------------

def main() -> None:
    index_path = Path("puzzles/index.json")
    if not index_path.exists():
        print("❌ No s'ha trobat puzzles/index.json. Executa primer 'make descarrega'.")
        sys.exit(1)

    with open(index_path) as f:
        index: dict[str, str] = json.load(f)

    n_total = len(index)
    print(f"Analitzant {n_total} puzzles...")
    print()

    totes_metriques: list[dict]    = []
    resultats_per_puzzle: dict = {}
    errors: list[str] = []

    for clau_curta, id_real in sorted(index.items()):
        fitxer = Path(f"puzzles/downloads/{clau_curta}.json")
        if not fitxer.exists():
            print(f"  ⚠️  {clau_curta}: fitxer no trobat, ometent.")
            errors.append(clau_curta)
            continue

        print(f"  [{clau_curta}] Processant...", end=" ", flush=True)

        try:
            g = carregar_o_construir_graf(fitxer)
            metriques = extraure_metriques_brutes(g)
        except TimeoutError as e:
            print(f"⏱️  {e}")
            errors.append(clau_curta)
            continue
        except ValueError as e:
            print(f"❌  Puzzle invàlid ({e}), ometent.")
            errors.append(clau_curta)
            continue
        except Exception as e:
            print(f"❌  Error inesperat ({type(e).__name__}: {e}), ometent.")
            errors.append(clau_curta)
            continue

        totes_metriques.append(metriques)

        # Puntuació original (amb llindars actuals)
        puntuacio_original = puntua_amb_llindars(
            metriques, LLINDAR_ESTATS, LLINDAR_SOLUCIO, LLINDAR_DIAMETRE
        )

        resultats_per_puzzle[clau_curta] = {
            "id_real":            id_real,
            "metriques":          metriques,
            "puntuacio_original": puntuacio_original,
            # La puntuació recalibrada s'afegirà més tard
        }

        print(f"nodes={metriques['num_nodes']:,}  sol={metriques['moviments_solucio']}  "
              f"diam={metriques['diametre']}  ef={metriques['eficiencia_cami']:.2f}  "
              f"atzucacs={metriques['fraccio_atzucacs']:.2%}  "
              f"→ {puntuacio_original:.2f}★")

    if not totes_metriques:
        print("❌ No s'ha pogut analitzar cap puzzle.")
        sys.exit(1)

    # Calibració
    calibracio = analitzar_calibracio(totes_metriques)
    nous = calibracio["nous_llindars_proposats"]

    # Recalcular puntuacions amb nous llindars
    for clau_curta, data in resultats_per_puzzle.items():
        data["puntuacio_recalibrada"] = puntua_amb_llindars(
            data["metriques"],
            nous["llindar_estats"],
            nous["llindar_solucio"],
            nous["llindar_diametre"],
        )

    # Desar fitxers
    calibracio_path = Path("puzzles/downloads/calibracio.json")
    with open(calibracio_path, "w") as f:
        json.dump(calibracio, f, indent=4)
    print(f"\n✅ Estadístics desats a {calibracio_path}")

    ratings_path = Path("puzzles/downloads/ratings.json")
    with open(ratings_path, "w") as f:
        json.dump(resultats_per_puzzle, f, indent=4)
    print(f"✅ Puntuacions desades a {ratings_path}")

    # Mostrar resultats
    imprime_taula_calibracio(calibracio)
    imprime_histograma(resultats_per_puzzle, "puntuacio_recalibrada")
    imprime_bloc_codi(nous, len(totes_metriques))

    if errors:
        print(f"\n⚠️  Puzzles omesos per error: {', '.join(errors)}")


if __name__ == "__main__":
    main()
