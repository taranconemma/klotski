"""
Genera un GIF animat a partir d'un trencaclosques i la seva solució.

Ús:
    python movie.py <puzzle.json> <solution.sol.json> [output.gif]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pygame
from PIL import Image

from puzzle import Puzzle
from logic import Move, apply_move, is_goal, DELTAS
from play import (
    draw_board,
    CELL,
    MARGIN_TOP,
    MARGIN_SIDE,
    BG_COLOR,
    SOLVED_COLOR,
    BORDER_W,
)

# Paràmetres de l'animació
FPS = 24
MOVE_MS = 400
FRAMES_PER_MOVE = FPS * MOVE_MS // 1000  # ~10
HOLD_MS = 1000
HOLD_FRAMES = FPS * HOLD_MS // 1000  # 24

# Marge inferior igual als altres costats (sense text d'ajuda interactiva)
MARGIN_BOTTOM_MOVIE = MARGIN_TOP


def ease_in_out(t: float) -> float:
    """Interpolació cúbica ease-in-out (suau a l'inici i al final)."""
    if t < 0.5:
        return 4 * t * t * t
    return 1 - (-2 * t + 2) ** 3 / 2


def surface_to_pil(surface: pygame.Surface) -> Image.Image:
    """Converteix una Surface de PyGame a una Image de PIL."""
    data = pygame.image.tostring(surface, "RGB")
    return Image.frombytes("RGB", surface.get_size(), data)


def render_movie(
    puzzle: Puzzle,
    moves: list[Move],
    output_path: str,
) -> None:
    """Renderitza l'animació de la solució i la desa com a GIF."""
    pygame.init()

    screen_w = puzzle.W * CELL + 2 * MARGIN_SIDE
    screen_h = puzzle.H * CELL + 2 * MARGIN_TOP  # marges simètrics
    screen = pygame.Surface((screen_w, screen_h))

    # Zona on draw_board escriu text d'ajuda interactiva (no el volem al GIF)
    cover_y = MARGIN_TOP + puzzle.H * CELL + BORDER_W

    frames: list[Image.Image] = []
    state = puzzle.start

    def capture(
        dragging: int | None = None,
        offset: tuple[float, float] = (0.0, 0.0),
        solved: bool = False,
    ) -> Image.Image:
        draw_board(screen, puzzle, state, dragging, offset, solved)
        bg = SOLVED_COLOR if solved else BG_COLOR
        pygame.draw.rect(screen, bg, (0, cover_y, screen_w, screen_h - cover_y))
        return surface_to_pil(screen)

    # Mantenir l'estat inicial visible
    initial_frame = capture()
    for _ in range(HOLD_FRAMES):
        frames.append(initial_frame)

    # Animar cada moviment
    for piece_idx, direction, dist in moves:
        dx, dy = DELTAS[direction]
        target_ox = float(dx * CELL * dist)
        target_oy = float(dy * CELL * dist)

        for f in range(FRAMES_PER_MOVE):
            t = ease_in_out((f + 1) / FRAMES_PER_MOVE)
            frames.append(
                capture(
                    dragging=piece_idx,
                    offset=(target_ox * t, target_oy * t),
                )
            )

        state = apply_move(puzzle, state, (piece_idx, direction, dist))

    # Mantenir l'estat final visible
    solved = is_goal(puzzle, state)
    final_frame = capture(solved=solved)
    for _ in range(HOLD_FRAMES):
        frames.append(final_frame)

    pygame.quit()

    # Desar com a GIF animat
    duration_ms = 1000 // FPS
    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=duration_ms,
        loop=0,
    )


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(
            f"Ús: python {sys.argv[0]} <puzzle.json> <solution.sol.json> [output.gif]"
        )
        sys.exit(1)

    puzzle_path = Path(sys.argv[1])
    solution_path = Path(sys.argv[2])

    puzzle = Puzzle.from_json(puzzle_path.read_text())
    # El format és [peça, direcció, distància]. Si només hi ha 2 elements,
    # la distància és implícitament 1 (compatibilitat amb el format antic).
    raw_moves = json.loads(solution_path.read_text())
    moves: list[Move] = [(m[0], m[1], m[2] if len(m) >= 3 else 1) for m in raw_moves]

    output = sys.argv[3] if len(sys.argv) >= 4 else puzzle_path.stem + ".gif"

    total_frames = 2 * HOLD_FRAMES + len(moves) * FRAMES_PER_MOVE
    print(f"Puzzle: {puzzle.W}×{puzzle.H}, {len(puzzle.pieces)} peces")
    print(f"Solució: {len(moves)} moviments")
    print(f"Frames: {total_frames} ({total_frames / FPS:.1f}s)")

    render_movie(puzzle, moves, output)
    print(f"Guardat: {output}")
