from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from io import StringIO
from typing import Any

import chess
import chess.pgn


EMPTY_CELLS = {None, "", ".", "0", 0}


class ChessConversionError(ValueError):
    """Raised when input data cannot be converted to a chess object."""


class ArrayPGNAdapter(ABC):
    """Base class for future array formats.

    The exact array format is still unknown, so a new format should only
    implement these two methods. ChessConverter will keep the same public API.
    """

    @abstractmethod
    def array_to_game(self, array: Any) -> chess.pgn.Game:
        """Convert user array data to a python-chess PGN game."""

    @abstractmethod
    def game_to_array(self, game: chess.pgn.Game) -> Any:
        """Convert a python-chess PGN game to user array data."""


@dataclass(slots=True)
class MoveListAdapter(ArrayPGNAdapter):
    """Adapter for arrays with moves.

    Input examples:
        ["e2e4", "e7e5", "g1f3"]
        ["e4", "e5", "Nf3"]
        [["e2e4", "e7e5"], ["g1f3", "b8c6"]]

    Output from PGN is a flat list of UCI moves, for example:
        ["e2e4", "e7e5", "g1f3"]
    """

    headers: Mapping[str, str] = field(
        default_factory=lambda: {
            "Event": "Converted game",
            "Site": "?",
            "Date": "????.??.??",
            "Round": "?",
            "White": "White",
            "Black": "Black",
            "Result": "*",
        }
    )

    def array_to_game(self, array: Any) -> chess.pgn.Game:
        board = chess.Board()
        game = chess.pgn.Game()

        for key, value in self.headers.items():
            game.headers[key] = value

        node = game
        for move_text in self._flatten_moves(array):
            move = self._parse_move(board, move_text)
            node = node.add_variation(move)
            board.push(move)

        game.headers["Result"] = board.result(claim_draw=True)
        return game

    def game_to_array(self, game: chess.pgn.Game) -> list[str]:
        return [move.uci() for move in game.mainline_moves()]

    def _flatten_moves(self, array: Any) -> Iterable[str]:
        if isinstance(array, str):
            yield array
            return

        if not isinstance(array, Iterable):
            raise ChessConversionError("Move array must be an iterable of moves.")

        for item in array:
            if isinstance(item, str):
                yield item
            elif isinstance(item, Iterable):
                yield from self._flatten_moves(item)
            else:
                raise ChessConversionError(f"Unsupported move item: {item!r}")

    def _parse_move(self, board: chess.Board, move_text: str) -> chess.Move:
        move_text = move_text.strip()

        try:
            return board.parse_san(move_text)
        except ValueError:
            pass

        try:
            move = chess.Move.from_uci(move_text)
        except ValueError as exc:
            raise ChessConversionError(f"Invalid move: {move_text!r}") from exc

        if move not in board.legal_moves:
            raise ChessConversionError(f"Illegal move for current position: {move_text!r}")

        return move


@dataclass(slots=True)
class PositionMatrixAdapter(ArrayPGNAdapter):
    """Adapter for an 8x8 board matrix.

    Matrix orientation:
        row 0 is rank 8, row 7 is rank 1;
        column 0 is file a, column 7 is file h.

    Piece values may be FEN symbols ("P", "n", "k"), chess.Piece objects,
    or empty values: None, "", ".", "0", 0.

    A single position has no move history, so array_to_game stores the position
    in PGN through SetUp/FEN headers.
    """

    turn: chess.Color = chess.WHITE
    output_symbols: str = "fen"
    headers: Mapping[str, str] = field(
        default_factory=lambda: {
            "Event": "Converted position",
            "Site": "?",
            "Date": "????.??.??",
            "Round": "?",
            "White": "White",
            "Black": "Black",
            "Result": "*",
        }
    )

    def array_to_game(self, array: Any) -> chess.pgn.Game:
        board = self.array_to_board(array)
        game = chess.pgn.Game()

        for key, value in self.headers.items():
            game.headers[key] = value

        game.setup(board)
        return game

    def game_to_array(self, game: chess.pgn.Game) -> list[list[str | None]]:
        return self.board_to_array(final_board_from_game(game))

    def array_to_board(self, array: Any) -> chess.Board:
        self._validate_matrix(array)

        board = chess.Board(None)
        board.turn = self.turn
        board.castling_rights = 0
        board.ep_square = None
        board.halfmove_clock = 0
        board.fullmove_number = 1

        for row_index, row in enumerate(array):
            rank = 7 - row_index
            for file_index, cell in enumerate(row):
                piece = self._cell_to_piece(cell)
                if piece is not None:
                    board.set_piece_at(chess.square(file_index, rank), piece)

        board.clear_stack()
        return board

    def board_to_array(self, board: chess.Board) -> list[list[str | None]]:
        matrix: list[list[str | None]] = []

        for rank in range(7, -1, -1):
            row: list[str | None] = []
            for file_index in range(8):
                piece = board.piece_at(chess.square(file_index, rank))
                row.append(self._piece_to_cell(piece))
            matrix.append(row)

        return matrix

    def _validate_matrix(self, array: Any) -> None:
        if not isinstance(array, Sequence) or len(array) != 8:
            raise ChessConversionError("Position matrix must contain exactly 8 rows.")

        for row in array:
            if not isinstance(row, Sequence) or isinstance(row, str) or len(row) != 8:
                raise ChessConversionError("Each position matrix row must contain 8 cells.")

    def _cell_to_piece(self, cell: Any) -> chess.Piece | None:
        if cell in EMPTY_CELLS:
            return None

        if isinstance(cell, chess.Piece):
            return cell

        text = str(cell).strip()
        try:
            return chess.Piece.from_symbol(text)
        except ValueError as exc:
            raise ChessConversionError(f"Unknown piece cell: {cell!r}") from exc

    def _piece_to_cell(self, piece: chess.Piece | None) -> str | None:
        if piece is None:
            return None

        if self.output_symbols == "fen":
            return piece.symbol()

        if self.output_symbols == "unicode":
            return piece.unicode_symbol()

        raise ChessConversionError("output_symbols must be 'fen' or 'unicode'.")


@dataclass(slots=True)
class UTF8BoardRenderer:
    """Renders a board the same way as python-chess board.unicode()."""

    borders: bool = False
    empty_square: str = "."
    orientation: chess.Color = chess.WHITE

    def render(self, board: chess.Board) -> str:
        return board.unicode(
            borders=self.borders,
            empty_square=self.empty_square,
            orientation=self.orientation,
        )


@dataclass(slots=True)
class ChessConverter:
    """Facade for conversions between arrays, PGN, and UTF-8 board text."""

    adapter: ArrayPGNAdapter = field(default_factory=MoveListAdapter)
    renderer: UTF8BoardRenderer = field(default_factory=UTF8BoardRenderer)

    def array_to_pgn(self, array: Any) -> str:
        game = self.adapter.array_to_game(array)
        return str(game)

    def pgn_to_array(self, pgn_text: str) -> Any:
        game = read_pgn_game(pgn_text)
        return self.adapter.game_to_array(game)

    def pgn_to_board(self, pgn_text: str) -> chess.Board:
        return final_board_from_game(read_pgn_game(pgn_text))

    def pgn_to_utf8_board(self, pgn_text: str) -> str:
        return self.renderer.render(self.pgn_to_board(pgn_text))


def read_pgn_game(pgn_text: str) -> chess.pgn.Game:
    game = chess.pgn.read_game(StringIO(pgn_text))
    if game is None:
        raise ChessConversionError("PGN text does not contain a game.")
    return game


def final_board_from_game(game: chess.pgn.Game) -> chess.Board:
    board = game.board()
    for move in game.mainline_moves():
        board.push(move)
    return board

