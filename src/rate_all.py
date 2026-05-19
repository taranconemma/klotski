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

from graph_tool.all import shortest_distance, shortest_path, label_components, label_biconnected_components, pseudo_diameter, Graph, load_graph #type:ignore

from graph import build_graph
from puzzle import Puzzle
from eval import MAX_ESTATS, MAX_SOLUCIO, MAX_DIAMETRE, MAX_PARANYS, MAX_PONTS, MAX_ENGANY, MAX_ABISME, heuristica_manhattan, nodes_cami_optim


def carregar_o_construir_graf(fitxer_json: Path) -> Graph:
    """Carrega el graf des del .graphml si existeix, altrament el construeix i el desa."""
    graphml_path = fitxer_json.with_suffix(".graphml")
    if graphml_path.exists():
        return load_graph(str(graphml_path))
    
    puzzle = Puzzle.from_json(fitxer_json.read_text())
    g = build_graph(puzzle)
    g.save(str(graphml_path))
    return g



def extraure_valors_concrets(g: Graph, puzzle: Puzzle) -> dict:
    """Extreu tots els valors concrets reals d'un graf (sense normalitzar).

    Retorna un diccionari amb:
        Clàssiques:
            num_nodes, num_arestes, num_goals
            moviments_solucio, diametre, eficiencia_cami
            fraccio_atzucacs, grau_mitja
        Originals:
            paranys_ponderat  — densitat de culs-de-sac propers a la meta
            ponts_al_cami     — nombre de ponts en el camí òptim
            engany_gradient   — màxim allunyament heurístic en el camí òptim
            cost_abisme       — pitjor cost de recuperació d'un error al camí
    """
    num_nodes   = g.num_vertices()
    num_arestes = g.num_edges()

    # Si està buit (per timeout) o té més de 400.000 nodes, assignem 0 a tot per evitar bloquejos
    if num_nodes == 0 or num_nodes > 400_000:
        return {
            "num_nodes":          num_nodes,
            "num_arestes":        num_arestes,
            "num_goals":          0,
            "moviments_solucio":  0,
            "diametre":           0,
            "fraccio_atzucacs":   0.0,
            "grau_mitja":         0.0,
            "eficiencia_cami":    0.0,
            "paranys_ponderat":   0.0,
            "ponts_al_cami":      0,
            "engany_gradient":    0,
            "cost_abisme":        0,
        }

    node_inici    = next(v for v in g.vertices() if g.vp["is_start"][v])
    nodes_objectiu = [v for v in g.vertices() if g.vp["is_goal"][v]]
    num_goals     = len(nodes_objectiu)

    if not nodes_objectiu:
        return {
            # Clàssiques
            "num_nodes":          num_nodes,
            "num_arestes":        num_arestes,
            "num_goals":          0,
            "moviments_solucio":  0,
            "diametre":           0,
            "fraccio_atzucacs":   0.0,
            "grau_mitja":         0.0,
            "eficiencia_cami":    0.0,
            # Originals
            "paranys_ponderat":   0.0,
            "ponts_al_cami":      0,
            "engany_gradient":    0,
            "cost_abisme":        0,
        }

    # ── Mètriques clàssiques ──────────────────────────────────────────────

    dist_inici = shortest_distance(g, source=node_inici)

    moviments_solucio = min(int(dist_inici[v]) for v in nodes_objectiu)

    diametre = 0
    if num_nodes >= 2:
        diametre, _ = pseudo_diameter(g)

    eficiencia_cami = round(moviments_solucio / diametre, 4) if diametre > 0 else 0.0

    etiquetes, _ = label_components(g)
    components_amb_goal: set[int] = {int(etiquetes[v]) for v in nodes_objectiu}
    atzucacs = sum(1 for v in g.vertices() if int(etiquetes[v]) not in components_amb_goal)
    fraccio_atzucacs = round(atzucacs / num_nodes, 4) if num_nodes > 0 else 0.0
    grau_mitja = round((2 * num_arestes) / num_nodes, 4) if num_nodes > 0 else 0.0

    # ── Mètrica 5: Densitat de paranys ───────────────────────────────────
    # Cada cul-de-sac es pondera per la seva proximitat al goal més proper.

    import numpy as np

    # Obtenim els índexs dels nodes objectiu directament des del graf
    goal_indices = np.where(g.vp["is_goal"].a)[0]
    
    # Distàncies mínimes a qualsevol objectiu inicialitzades amb infinit
    dists_min = np.full(num_nodes, np.inf)
    if len(goal_indices) > 0:
        for goal_idx in goal_indices:
            dg = shortest_distance(g, source=goal_idx)
            dists_min = np.minimum(dists_min, dg.a)

    # Obtenim els graus de tots els vèrtexs
    graus = g.get_out_degrees(g.get_vertices())
    
    # Filtrem només els culs-de-sac (grau 1)
    paranys = (graus == 1)
    
    # Calculem la suma dels pesos de forma vectoritzada
    suma_paranys = float(np.sum(1.0 / (1.0 + dists_min[paranys])))
    paranys_ponderat = round(suma_paranys / num_nodes, 6) if num_nodes > 0 else 0.0

    # ── Mètrica 6: Ponts crítics en el camí òptim ────────────────────────
    # Identifiquem ponts via components biconnectades.

    ponts_al_cami = 0
    if nodes_objectiu and num_nodes >= 2:
        from collections import Counter
        comp_aresta, _, _ = label_biconnected_components(g)
        counts = Counter(comp_aresta.a)

        best_goal = min(nodes_objectiu, key=lambda v: int(dist_inici[v]))
        _, path_edges = shortest_path(g, node_inici, best_goal)
        ponts_al_cami = sum(1 for e in path_edges if counts[comp_aresta[e]] == 1)

    # ── Mètrica 7: Engany del gradient ───────────────────────────────────
    # Màxim allunyament de la heurística de Manhattan al llarg del camí òptim.

    engany_gradient = 0
    if nodes_objectiu and g.vp.get("state"):
        nodes_cami = nodes_cami_optim(g, node_inici, nodes_objectiu, dist_inici)
        if nodes_cami:
            h_inicial = heuristica_manhattan(puzzle, g.vp["state"][node_inici])
            h_max = max(heuristica_manhattan(puzzle, g.vp["state"][v]) for v in nodes_cami if g.vp["state"][v] is not None)
            engany_gradient = h_max - h_inicial

    # ── Mètrica 8: L'abisme ──────────────────────────────────────────────
    # Pitjor cost (anar + tornar) de fer un pas en fals en el camí òptim.

    cost_abisme = 0
    if nodes_objectiu and num_nodes >= 3:
        nodes_cami = nodes_cami_optim(g, node_inici, nodes_objectiu, dist_inici)
        if len(nodes_cami) >= 3:
            nodes_cami_set = set(nodes_cami)

            for idx_cami, v in enumerate(nodes_cami[:-1]):
                for vei in v.out_neighbors():
                    if vei not in nodes_cami_set:
                        dist_vei_a_cami = shortest_distance(g, source=vei, target=nodes_cami[idx_cami + 1:], max_dist=40).min()
                        cost_abisme = max(cost_abisme, 1 + dist_vei_a_cami)

    return {
        # Clàssiques
        "num_nodes":          num_nodes,
        "num_arestes":        num_arestes,
        "num_goals":          num_goals,
        "moviments_solucio":  moviments_solucio,
        "diametre":           int(diametre),
        "fraccio_atzucacs":   fraccio_atzucacs,
        "grau_mitja":         grau_mitja,
        "eficiencia_cami":    eficiencia_cami,
        # Originals
        "paranys_ponderat":   paranys_ponderat,
        "ponts_al_cami":      ponts_al_cami,
        "engany_gradient":    engany_gradient,
        "cost_abisme":        cost_abisme,
    }


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
    m8 = normalitza_lin(metriques["cost_abisme"],       llindars["abisme"])

    puntuacio_0_1 = (
        0.10 * m1 +
        0.25 * m2 +
        0.10 * m3 +
        0.10 * m4 +
        0.10 * m5 +
        0.10 * m6 +
        0.15 * m7 +
        0.10 * m8
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
        "abisme":   "cost_abisme",
    }
    llindars_actuals = {
        "estats":   MAX_ESTATS,
        "solucio":  MAX_SOLUCIO,
        "diametre": MAX_DIAMETRE,
        "paranys":  MAX_PARANYS,
        "ponts":    MAX_PONTS,
        "engany":   MAX_ENGANY,
        "abisme":   MAX_ABISME,
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
        ("abisme",   "L'abisme"),
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
    print(f"    MAX_ABISME:   int   = {int(nl['abisme'])}   # cost màxim de recuperació")
    print()
    print("═" * 78)


# ─────────────────────────────────────────────────────────────────────────────
# PROGRAMA PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

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

    llindars_actuals = {
        "estats":   MAX_ESTATS,
        "solucio":  MAX_SOLUCIO,
        "diametre": MAX_DIAMETRE,
        "paranys":  MAX_PARANYS,
        "ponts":    MAX_PONTS,
        "engany":   MAX_ENGANY,
        "abisme":   MAX_ABISME,
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
            g      = carregar_o_construir_graf(fitxer)
            puzzle = Puzzle.from_json(fitxer.read_text())
            metriques = extraure_valors_concrets(g, puzzle)
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
            f"abisme={metriques['cost_abisme']}  "
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