from __future__ import annotations

import argparse
from pathlib import Path

import chess

try:
    from .board import UTF8BoardRenderer, final_board_from_game, read_pgn_game
    from .engine import ChessEngine
except ImportError:
    from board import UTF8BoardRenderer, final_board_from_game, read_pgn_game
    from engine import ChessEngine


COLOR_BY_NAME = {
    "white": chess.WHITE,
    "w": chess.WHITE,
    "1": chess.WHITE,
    "black": chess.BLACK,
    "b": chess.BLACK,
    "2": chess.BLACK,
}


def load_board(fen: str | None, pgn: str | None) -> chess.Board:
    if fen and pgn:
        raise ValueError("Use either --fen or --pgn, not both.")

    if fen:
        return chess.Board(fen)

    if pgn:
        pgn_text = _read_text_or_value(pgn)
        return final_board_from_game(read_pgn_game(pgn_text))

    return chess.Board()


def run_game(board: chess.Board, depth: int, engine_color: chess.Color | None) -> None:
    if engine_color is None:
        engine_color = ask_engine_color()

    player_color = not engine_color
    renderer = UTF8BoardRenderer(
        borders=False,
        orientation=player_color,
        coordinates=True,
    )
    engine = ChessEngine(depth=depth)

    while not board.is_game_over(claim_draw=True):
        print_position(board, renderer)

        if board.turn == engine_color:
            result = engine.find_best_move(board)
            if result.best_move is None:
                break

            san = board.san(result.best_move)
            board.push(result.best_move)
            print(f"\nComputer move: {san} ({result.best_move.uci()})")
            print(
                f"Score: {result.score}, depth: {result.depth}, "
                f"nodes: {result.nodes}, cutoffs: {result.cutoffs}"
            )
        else:
            move = ask_player_move(board)
            if move is None:
                print("Game stopped.")
                return

            board.push(move)

    print_position(board, renderer)
    print_game_result(board)


def print_position(board: chess.Board, renderer: UTF8BoardRenderer) -> None:
    print()
    print(renderer.render(board))
    print()
    print(f"Side to move: {'White' if board.turn == chess.WHITE else 'Black'}")


def ask_engine_color() -> chess.Color:
    while True:
        try:
            color_text = input("Input computer color (white/black): ").strip()
        except EOFError as exc:
            raise SystemExit("No computer color provided.") from exc

        try:
            return parse_color(color_text)
        except ValueError:
            print("Invalid color. Enter white or black.")


def ask_player_move(board: chess.Board) -> chess.Move | None:
    print("\nLegal moves:")
    print(" ".join(board.san(move) for move in board.legal_moves))

    while True:
        try:
            move_text = input('Your move (SAN or UCI, "quit" to stop): ').strip()
        except EOFError:
            return None

        if move_text.lower() in {"quit", "exit"}:
            return None

        try:
            return parse_move(board, move_text)
        except ValueError:
            print("Invalid move. Try SAN like Nf3 or UCI like g1f3.")


def parse_move(board: chess.Board, move_text: str) -> chess.Move:
    if not move_text:
        raise ValueError("Move cannot be empty.")

    try:
        return board.parse_san(move_text)
    except ValueError:
        pass

    try:
        move = chess.Move.from_uci(move_text.lower())
    except ValueError as exc:
        raise ValueError(f"Invalid move: {move_text!r}") from exc

    if move not in board.legal_moves:
        raise ValueError(f"Illegal move: {move_text!r}")

    return move


def print_game_result(board: chess.Board) -> None:
    outcome = board.outcome(claim_draw=True)
    if outcome is None:
        print("Game ended without a result.")
        return

    termination = outcome.termination.name.lower().replace("_", " ")

    if outcome.winner is None:
        print(f"Result: {board.result(claim_draw=True)}. Draw by {termination}.")
        return

    winner = "White" if outcome.winner == chess.WHITE else "Black"
    print(f"Result: {board.result(claim_draw=True)}. {winner} wins by {termination}.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the chess engine.")
    parser.add_argument("--depth", type=_positive_int, default=3, help="Search depth in plies.")
    parser.add_argument("--fen", help="Analyze a position from FEN.")
    parser.add_argument("--pgn", help="Start from the final position of PGN text or a PGN file.")
    parser.add_argument(
        "--engine-color",
        type=parse_color,
        help="Computer color: white/black. If omitted, the program asks.",
    )
    return parser.parse_args()


def parse_color(color_text: str) -> chess.Color:
    try:
        return COLOR_BY_NAME[color_text.lower()]
    except KeyError as exc:
        raise ValueError("Color must be white or black.") from exc


def _read_text_or_value(value: str) -> str:
    path = Path(value)
    try:
        if path.exists():
            return path.read_text(encoding="utf-8")
    except OSError:
        pass

    return value


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("depth must be at least 1")
    return parsed


def main() -> None:
    args = parse_args()
    board = load_board(args.fen, args.pgn)
    run_game(board, args.depth, args.engine_color)


if __name__ == "__main__":
    main()
