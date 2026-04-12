"""Tests per als poliòminós (dòmino, triòmino, tetròmino) i la seva normalització."""

import json
import pytest

from puzzle import Coord, Piece, Puzzle, State


# --- Helpers ---


def rotate_cw(coords: list[Coord]) -> list[Coord]:
    """Rotació 90° en sentit horari: (x,y) -> (-y, x), després normalitza."""
    rotated = [(-y, x) for x, y in coords]
    min_x = min(x for x, y in rotated)
    min_y = min(y for x, y in rotated)
    return [(x - min_x, y - min_y) for x, y in rotated]


def all_rotations(coords: list[Coord]) -> list[Piece]:
    """Retorna les 4 rotacions d'una peça com a Pieces normalitzades, en ordre."""
    pieces = set()
    c = list(coords)
    for _ in range(4):
        pieces.add(Piece.normalized(c))
        c = rotate_cw(c)
    return sorted(pieces)


# =====================================================================
#  Monòmino (1 casella)
# =====================================================================


class TestMonomino:
    def test_unica_forma(self):
        p = Piece((0, 0))
        assert p.coords == ((0, 0),)

    def test_normalitzacio(self):
        p = Piece.normalized([(5, 3)])
        assert p.coords == ((0, 0),)

    def test_rotacions(self):
        assert all_rotations([(0, 0)]) == [Piece((0, 0))]


# =====================================================================
#  Dòminos (2 caselles) — 1 forma lliure, 2 orientacions fixes
# =====================================================================


DOMINO_H = Piece((0, 0), (1, 0))  # horizontal
DOMINO_V = Piece((0, 0), (0, 1))  # vertical


class TestDomino:
    def test_formes(self):
        assert DOMINO_H.coords == ((0, 0), (1, 0))
        assert DOMINO_V.coords == ((0, 0), (0, 1))

    def test_rotacions(self):
        rots = all_rotations([(0, 0), (1, 0)])
        assert len(rots) == 2
        assert rots == sorted([DOMINO_V, DOMINO_H])

    def test_ordre(self):
        # (0,0),(0,1) < (0,0),(1,0) perquè al 2n element (0,1) < (1,0)
        assert DOMINO_V < DOMINO_H

    def test_normalitzacio_des_de_offset(self):
        p = Piece.normalized([(3, 7), (4, 7)])
        assert p == DOMINO_H


# =====================================================================
#  Triòminós (3 caselles) — 2 formes lliures, 6 orientacions fixes
# =====================================================================

# I-triòmino: recte
TRIOMINO_I_H = Piece((0, 0), (1, 0), (2, 0))  # horitzontal
TRIOMINO_I_V = Piece((0, 0), (0, 1), (0, 2))  # vertical

# L-triòmino: 4 orientacions
TRIOMINO_L_0 = Piece((0, 0), (0, 1), (1, 0))
TRIOMINO_L_90 = Piece((0, 0), (1, 0), (1, 1))
TRIOMINO_L_180 = Piece((0, 1), (1, 0), (1, 1))
TRIOMINO_L_270 = Piece((0, 0), (0, 1), (1, 1))


class TestTriominoI:
    def test_formes(self):
        assert TRIOMINO_I_H.coords == ((0, 0), (1, 0), (2, 0))
        assert TRIOMINO_I_V.coords == ((0, 0), (0, 1), (0, 2))

    def test_rotacions(self):
        rots = all_rotations([(0, 0), (1, 0), (2, 0)])
        assert len(rots) == 2
        assert rots == sorted([TRIOMINO_I_V, TRIOMINO_I_H])

    def test_ordre(self):
        assert TRIOMINO_I_V < TRIOMINO_I_H


class TestTriominoL:
    def test_4_rotacions(self):
        rots = all_rotations([(0, 0), (0, 1), (1, 0)])
        assert len(rots) == 4
        expected = sorted([TRIOMINO_L_0, TRIOMINO_L_90, TRIOMINO_L_180, TRIOMINO_L_270])
        assert rots == expected

    def test_ordre_rotacions(self):
        # Verifiquem l'ordre lexicogràfic entre les 4 rotacions
        assert TRIOMINO_L_0 < TRIOMINO_L_270  # (0,0),(0,1),(1,0) < (0,0),(0,1),(1,1)
        assert TRIOMINO_L_270 < TRIOMINO_L_90  # (0,0),(0,1),(1,1) < (0,0),(1,0),(1,1)
        assert TRIOMINO_L_90 < TRIOMINO_L_180  # (0,0),(1,0),(1,1) < (0,1),(1,0),(1,1)

    def test_normalitzacio(self):
        # L des de coordenades amb offset
        p = Piece.normalized([(10, 20), (10, 21), (11, 20)])
        assert p == TRIOMINO_L_0


# =====================================================================
#  Tetròminós (4 caselles) — 5 formes lliures, 19 orientacions fixes
# =====================================================================

# I-tetròmino: 2 orientacions
TETRO_I_H = Piece((0, 0), (1, 0), (2, 0), (3, 0))
TETRO_I_V = Piece((0, 0), (0, 1), (0, 2), (0, 3))

# O-tetròmino: 1 orientació
TETRO_O = Piece((0, 0), (0, 1), (1, 0), (1, 1))

# T-tetròmino: 4 orientacions
TETRO_T_0 = Piece((0, 0), (1, 0), (1, 1), (2, 0))  # T cap avall
TETRO_T_90 = Piece((0, 0), (0, 1), (0, 2), (1, 1))  # T cap a la dreta
TETRO_T_180 = Piece((0, 1), (1, 0), (1, 1), (2, 1))  # T cap amunt
TETRO_T_270 = Piece((0, 1), (1, 0), (1, 1), (1, 2))  # T cap a l'esquerra

# S-tetròmino: 2 orientacions
TETRO_S_0 = Piece((0, 1), (1, 0), (1, 1), (2, 0))
TETRO_S_90 = Piece((0, 0), (0, 1), (1, 1), (1, 2))

# Z-tetròmino: 2 orientacions
TETRO_Z_0 = Piece((0, 0), (1, 0), (1, 1), (2, 1))
TETRO_Z_90 = Piece((0, 1), (0, 2), (1, 0), (1, 1))

# L-tetròmino: 4 orientacions
TETRO_L_0 = Piece((0, 0), (0, 1), (0, 2), (1, 2))
TETRO_L_90 = Piece((0, 0), (0, 1), (1, 0), (2, 0))
TETRO_L_180 = Piece((0, 0), (1, 0), (1, 1), (1, 2))
TETRO_L_270 = Piece((0, 1), (1, 1), (2, 0), (2, 1))

# J-tetròmino: 4 orientacions
TETRO_J_0 = Piece((0, 0), (0, 1), (0, 2), (1, 0))
TETRO_J_90 = Piece((0, 0), (1, 0), (2, 0), (2, 1))
TETRO_J_180 = Piece((0, 2), (1, 0), (1, 1), (1, 2))
TETRO_J_270 = Piece((0, 0), (0, 1), (1, 1), (2, 1))


class TestTetrominoI:
    def test_rotacions(self):
        rots = all_rotations([(0, 0), (1, 0), (2, 0), (3, 0)])
        assert len(rots) == 2
        assert rots == sorted([TETRO_I_V, TETRO_I_H])


class TestTetrominoO:
    def test_rotacions(self):
        rots = all_rotations([(0, 0), (1, 0), (0, 1), (1, 1)])
        assert len(rots) == 1
        assert rots == [TETRO_O]


class TestTetrominoT:
    def test_rotacions(self):
        rots = all_rotations([(0, 0), (1, 0), (2, 0), (1, 1)])
        assert len(rots) == 4
        assert rots == sorted([TETRO_T_0, TETRO_T_90, TETRO_T_180, TETRO_T_270])


class TestTetrominoS:
    def test_rotacions(self):
        rots = all_rotations([(1, 0), (2, 0), (0, 1), (1, 1)])
        assert len(rots) == 2
        assert rots == sorted([TETRO_S_0, TETRO_S_90])

    def test_S_diferent_de_Z(self):
        s_rots = set(all_rotations([(1, 0), (2, 0), (0, 1), (1, 1)]))
        z_rots = set(all_rotations([(0, 0), (1, 0), (1, 1), (2, 1)]))
        assert s_rots.isdisjoint(z_rots)


class TestTetrominoZ:
    def test_rotacions(self):
        rots = all_rotations([(0, 0), (1, 0), (1, 1), (2, 1)])
        assert len(rots) == 2
        assert rots == sorted([TETRO_Z_0, TETRO_Z_90])


class TestTetrominoL:
    def test_rotacions(self):
        rots = all_rotations([(0, 0), (0, 1), (0, 2), (1, 2)])
        assert len(rots) == 4
        assert rots == sorted([TETRO_L_0, TETRO_L_90, TETRO_L_180, TETRO_L_270])

    def test_L_diferent_de_J(self):
        l_rots = set(all_rotations([(0, 0), (0, 1), (0, 2), (1, 2)]))
        j_rots = set(all_rotations([(0, 0), (0, 1), (0, 2), (1, 0)]))
        assert l_rots.isdisjoint(j_rots)


class TestTetrominoJ:
    def test_rotacions(self):
        rots = all_rotations([(0, 0), (0, 1), (0, 2), (1, 0)])
        assert len(rots) == 4
        assert rots == sorted([TETRO_J_0, TETRO_J_90, TETRO_J_180, TETRO_J_270])


class TestTotalOrientacionsFixes:
    def test_19_tetrominoes(self):
        tots = set()
        for coords in [
            [(0, 0), (1, 0), (2, 0), (3, 0)],  # I
            [(0, 0), (1, 0), (0, 1), (1, 1)],  # O
            [(0, 0), (1, 0), (2, 0), (1, 1)],  # T
            [(1, 0), (2, 0), (0, 1), (1, 1)],  # S
            [(0, 0), (1, 0), (1, 1), (2, 1)],  # Z
            [(0, 0), (0, 1), (0, 2), (1, 2)],  # L
            [(0, 0), (0, 1), (0, 2), (1, 0)],  # J
        ]:
            for p in all_rotations(coords):
                tots.add(p)
        assert len(tots) == 19

    def test_6_triominoes(self):
        tots = set()
        for coords in [
            [(0, 0), (1, 0), (2, 0)],  # I
            [(0, 0), (0, 1), (1, 0)],  # L
        ]:
            for p in all_rotations(coords):
                tots.add(p)
        assert len(tots) == 6

    def test_2_dominoes(self):
        tots = set()
        for p in all_rotations([(0, 0), (1, 0)]):
            tots.add(p)
        assert len(tots) == 2


# =====================================================================
#  Validacions
# =====================================================================


class TestValidacions:
    def test_peça_buida(self):
        with pytest.raises(ValueError, match="almenys una coordenada"):
            Piece()

    def test_coordenades_negatives(self):
        with pytest.raises(ValueError, match="negativa"):
            Piece((-1, 0))

    def test_coordenades_repetides(self):
        with pytest.raises(ValueError, match="repetides"):
            Piece((0, 0), (0, 0))

    def test_coordenades_desordenades(self):
        with pytest.raises(ValueError, match="no estan ordenades"):
            Piece((1, 0), (0, 0))

    def test_no_normalitzada(self):
        with pytest.raises(ValueError, match="no està normalitzada"):
            Piece((1, 0), (2, 0))

    def test_puzzle_dimensions_invalides(self):
        with pytest.raises(ValueError, match="positius"):
            Puzzle(0, 5, (), (), State(()), ())

    def test_puzzle_peces_desordenades(self):
        # DOMINO_V < DOMINO_H, posar-les al revés ha de fallar
        with pytest.raises(ValueError, match="ordre canònic"):
            Puzzle(
                4,
                4,
                (),
                (DOMINO_H, DOMINO_V),
                State(((0, 0), (2, 0))),
                (),
            )

    def test_puzzle_goals_desordenats(self):
        with pytest.raises(ValueError, match="ordre canònic"):
            Puzzle(
                4,
                4,
                (),
                (DOMINO_V,),
                State(((0, 0),)),
                ((0, (1, 0)), (0, (0, 0))),  # desordenats
            )

    def test_puzzle_index_invalid(self):
        with pytest.raises(ValueError, match="invàlid"):
            Puzzle(
                4,
                4,
                (),
                (DOMINO_H,),
                State(((0, 0),)),
                ((5, (0, 0)),),
            )

    def test_puzzle_walls_desordenades(self):
        with pytest.raises(ValueError, match="parets"):
            Puzzle(
                4,
                4,
                ((1, 0), (0, 0)),  # desordenades
                (DOMINO_H,),
                State(((0, 0),)),
                (),
            )

    def test_puzzle_wall_fora_taulell(self):
        with pytest.raises(ValueError, match="fora del taulell"):
            Puzzle(
                4,
                4,
                ((5, 0),),
                (DOMINO_H,),
                State(((0, 0),)),
                (),
            )

    def test_puzzle_posicions_incorrectes(self):
        with pytest.raises(ValueError, match="nombre de posicions"):
            Puzzle(
                4,
                4,
                (),
                (DOMINO_H,),
                State(((0, 0), (1, 0))),  # 2 posicions per 1 peça
                (),
            )


# =====================================================================
#  Ordenació canònica de peces al Puzzle
# =====================================================================


class TestOrdreCanonic:
    def test_ordena_per_forma_primer(self):
        # DOMINO_V < DOMINO_H, per tant V ha d'anar primer
        puzzle = Puzzle(
            6,
            6,
            (),
            (DOMINO_V, DOMINO_H),
            State(((0, 0), (2, 0))),
            (),
        )
        assert puzzle.pieces[0] == DOMINO_V
        assert puzzle.pieces[1] == DOMINO_H

    def test_mateixa_forma_ordena_per_posicio(self):
        puzzle = Puzzle(
            6,
            6,
            (),
            (DOMINO_H, DOMINO_H),
            State(((0, 0), (0, 1))),
            (),
        )
        assert puzzle.start.positions[0] < puzzle.start.positions[1]


# =====================================================================
#  State
# =====================================================================


class TestState:
    def test_creacio(self):
        s = State(((0, 0), (1, 1)))
        assert s.positions == ((0, 0), (1, 1))

    def test_hashable(self):
        s1 = State(((0, 0), (1, 1)))
        s2 = State(((0, 0), (1, 1)))
        assert hash(s1) == hash(s2)
        assert s1 == s2
        assert len({s1, s2}) == 1

    def test_diferent(self):
        s1 = State(((0, 0), (1, 1)))
        s2 = State(((0, 0), (2, 2)))
        assert s1 != s2

    def test_to_json(self):
        s = State(((1, 2), (3, 4)))
        assert json.loads(s.to_json()) == [[1, 2], [3, 4]]


# =====================================================================
#  to_json / from_json
# =====================================================================


class TestToJson:
    def test_piece_to_json(self):
        s = DOMINO_H.to_json()
        assert isinstance(s, str)
        assert json.loads(s) == [[0, 0], [1, 0]]

    def test_puzzle_to_json_exemple_spec(self):
        """Comprova el JSON de l'exemple de l'especificació."""
        piece_I = Piece((0, 0), (0, 1), (0, 2))
        piece_L = Piece((0, 0), (0, 1), (1, 0))

        puzzle = Puzzle(
            4,
            5,
            (),
            (piece_I, piece_L),
            State(((1, 1), (0, 0))),
            ((0, (0, 0)), (1, (2, 0))),
        )

        obj = json.loads(puzzle.to_json())
        assert obj["W"] == 4
        assert obj["H"] == 5
        assert obj["walls"] == []
        assert len(obj["pieces"]) == 2
        assert obj["pieces"][0] == [[0, 0], [0, 1], [0, 2]]
        assert obj["pieces"][1] == [[0, 0], [0, 1], [1, 0]]
        assert obj["start"] == [[1, 1], [0, 0]]
        assert obj["goals"][0] == {"i": 0, "pos": [0, 0]}
        assert obj["goals"][1] == {"i": 1, "pos": [2, 0]}

    def test_puzzle_to_json_amb_parets(self):
        puzzle = Puzzle(
            4,
            4,
            ((1, 1), (2, 2)),
            (Piece((0, 0)),),
            State(((0, 0),)),
            ((0, (3, 3)),),
        )
        obj = json.loads(puzzle.to_json())
        assert obj["walls"] == [[1, 1], [2, 2]]

    def test_puzzle_hash(self):
        puzzle = Puzzle(
            2,
            2,
            (),
            (Piece((0, 0)),),
            State(((0, 0),)),
            ((0, (1, 1)),),
        )
        h = puzzle.hash()
        assert isinstance(h, str)
        assert len(h) == 64

    def test_puzzle_hash_canvia_amb_contingut(self):
        """Dos puzzles diferents han de tenir hash diferent."""
        p1 = Puzzle(2, 2, (), (Piece((0, 0)),), State(((0, 0),)), ((0, (1, 1)),))
        p2 = Puzzle(3, 3, (), (Piece((0, 0)),), State(((0, 0),)), ((0, (1, 1)),))
        assert p1.hash() != p2.hash()

    def test_puzzle_to_json_amb_indent(self):
        puzzle = Puzzle(
            2,
            2,
            (),
            (Piece((0, 0)),),
            State(((0, 0),)),
            ((0, (1, 1)),),
        )
        s = puzzle.to_json(indent=2)
        assert isinstance(s, str)
        assert "\n" in s
        assert json.loads(s) == json.loads(puzzle.to_json())

    def test_puzzle_from_json(self):
        j = '{"W":4,"H":5,"walls":[],"pieces":[[[0,0],[0,1],[0,2]],[[0,0],[0,1],[1,0]]],"start":[[1,1],[0,0]],"goals":[{"i":0,"pos":[0,0]},{"i":1,"pos":[2,0]}]}'
        puzzle = Puzzle.from_json(j)
        assert puzzle.W == 4
        assert puzzle.H == 5
        assert puzzle.walls == ()
        assert len(puzzle.pieces) == 2
        assert puzzle.start.positions == ((1, 1), (0, 0))
        assert puzzle.goals == ((0, (0, 0)), (1, (2, 0)))

    def test_puzzle_from_json_simplicity(self):
        """Comprova el puzzle 'simplicity' (4x4, 4 peces)."""
        j = '{"W":4,"H":4,"walls":[],"pieces":[[[0,0],[0,1]],[[0,0],[0,1],[1,1]],[[0,0],[0,1],[1,1]],[[0,0],[1,0]]],"start":[[1,2],[2,0],[2,2],[0,1]],"goals":[{"i":2,"pos":[0,0]}]}'
        puzzle = Puzzle.from_json(j)
        assert puzzle.W == 4
        assert puzzle.H == 4
        assert puzzle.walls == ()
        assert len(puzzle.pieces) == 4
        assert puzzle.start.positions == ((1, 2), (2, 0), (2, 2), (0, 1))
        assert puzzle.goals == ((2, (0, 0)),)
        # Roundtrip
        assert Puzzle.from_json(puzzle.to_json()) == puzzle

    def test_puzzle_from_json_roundtrip(self):
        puzzle = Puzzle(
            4,
            5,
            ((1, 1),),
            (Piece((0, 0), (0, 1), (0, 2)), Piece((0, 0), (0, 1), (1, 0))),
            State(((1, 1), (0, 0))),
            ((0, (0, 0)), (1, (2, 0))),
        )
        reconstructed = Puzzle.from_json(puzzle.to_json())
        assert reconstructed == puzzle
