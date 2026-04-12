"""
Renderitza un trencaclosques (Puzzle) com a imatge PNG.

Cada peça es dibuixa amb un color diferent sobre un taulell amb
quadrícula. Les parets es mostren en gris fosc, i les caselles
buides en blanc.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from puzzle import Puzzle, State

# Mida d'una casella en píxels
CELL = 60

# Colors
BG_COLOR = (240, 240, 240)
GRID_COLOR = (180, 180, 180)
WALL_COLOR = (60, 60, 60)

# Paleta de colors per a les peces (fins a 20, es recicla si cal)
PIECE_PALETTE: list[tuple[int, int, int]] = [
    (76, 175, 80),    # verd
    (33, 150, 243),   # blau
    (255, 193, 7),    # groc
    (156, 39, 176),   # violeta
    (255, 87, 34),    # taronja
    (0, 188, 212),    # cian
    (233, 30, 99),    # rosa
    (121, 85, 72),    # marró
    (63, 81, 181),    # indi
    (139, 195, 74),   # llima
    (255, 152, 0),    # taronja fosc
    (103, 58, 183),   # violeta fosc
    (0, 150, 136),    # verd fosc
    (244, 67, 54),    # vermell
    (3, 169, 244),    # blau clar
    (205, 220, 57),   # groc-verd
    (255, 235, 59),   # groc clar
    (96, 125, 139),   # gris blavós
    (38, 166, 154),   # verd menta
    (239, 108, 0),    # mandarina
]


def piece_color(index: int) -> tuple[int, int, int]:
    """Retorna el color de la peça amb índex donat."""
    return PIECE_PALETTE[index % len(PIECE_PALETTE)]


def render_board(puzzle: Puzzle, state: State) -> Image.Image:
    """Renderitza l'estat d'un puzzle com a imatge PIL."""
    w_px = puzzle.W * CELL + 1
    h_px = puzzle.H * CELL + 1
    img = Image.new("RGB", (w_px, h_px), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Dibuixa les parets
    for wx, wy in puzzle.walls:
        x0, y0 = wx * CELL, wy * CELL
        draw.rectangle([x0, y0, x0 + CELL, y0 + CELL], fill=WALL_COLOR)

    # Dibuixa les peces
    for i, piece_shape in enumerate(puzzle.pieces):
        px, py = state.positions[i]
        color = piece_color(i)

        for dx, dy in piece_shape.coords:
            cx, cy = px + dx, py + dy
            x0, y0 = cx * CELL, cy * CELL
            draw.rectangle([x0 + 1, y0 + 1, x0 + CELL - 1, y0 + CELL - 1], fill=color)

    # Quadrícula per sobre
    for col in range(puzzle.W + 1):
        x = col * CELL
        draw.line([(x, 0), (x, h_px - 1)], fill=GRID_COLOR, width=1)
    for row in range(puzzle.H + 1):
        y = row * CELL
        draw.line([(0, y), (w_px - 1, y)], fill=GRID_COLOR, width=1)

    return img


def render_puzzle(
    puzzle: Puzzle,
    path: str | Path,
    *,
    state: State | None = None,
) -> None:
    """
    Renderitza un puzzle i el desa com a PNG.

    Si no es dóna un estat, fa servir l'estat inicial.
    """
    if state is None:
        state = puzzle.start
    img = render_board(puzzle, state)
    img.save(str(path))


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print(f"Ús: python3 {sys.argv[0]} <fitxer.json>")
        sys.exit(1)

    json_path = Path(sys.argv[1])
    json_text = json_path.read_text()
    name = json_path.stem
    puzzle = Puzzle.from_json(json_text)

    out_path = Path(f"{name}.png")
    render_puzzle(puzzle, out_path)
    print(out_path)
