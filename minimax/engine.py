from __future__ import annotations

from dataclasses import dataclass, field

import chess


BOARD_SIZE = 8
CHECKMATE_SCORE = 100_000
INFINITY = 1_000_000

PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}


@dataclass(slots=True)
class SearchStats:
    nodes: int = 0
    cutoffs: int = 0


@dataclass(frozen=True, slots=True)
class SearchResult:
    best_move: chess.Move | None
    score: int
    depth: int
    nodes: int
    cutoffs: int


@dataclass(slots=True)
class SimpleEvaluator:
    material_weight: int = 1
    mobility_weight: int = 2
    center_weight: int = 6
    bishop_pair_bonus: int = 35
    check_penalty: int = 40

    def evaluate(self, board: chess.Board) -> int:
        """Return a white-centric score in centipawns."""
        score = self._material_and_position_score(board)
        score += self._bishop_pair_score(board)
        score += self._mobility_score(board)
        score += self._check_score(board)
        return score

    def _material_and_position_score(self, board: chess.Board) -> int:
        score = 0

        for piece_type, value in PIECE_VALUES.items():
            for square in board.pieces(piece_type, chess.WHITE):
                score += value * self.material_weight
                score += self._piece_activity(piece_type, square, chess.WHITE)

            for square in board.pieces(piece_type, chess.BLACK):
                score -= value * self.material_weight
                score -= self._piece_activity(piece_type, square, chess.BLACK)

        return score

    def _piece_activity(
        self,
        piece_type: chess.PieceType,
        square: chess.Square,
        color: chess.Color,
    ) -> int:
        rank = chess.square_rank(square)
        file_index = chess.square_file(square)

        if color == chess.BLACK:
            rank = 7 - rank

        center_distance = abs(file_index - 3.5) + abs(rank - 3.5)
        center_bonus = int((7 - center_distance) * self.center_weight)

        if piece_type == chess.PAWN:
            return rank * 8 + center_bonus // 2
        if piece_type in (chess.KNIGHT, chess.BISHOP):
            return center_bonus + rank * 2
        if piece_type == chess.ROOK:
            return rank * 3
        if piece_type == chess.QUEEN:
            return center_bonus // 2
        if piece_type == chess.KING:
            return self._king_safety(file_index, rank)

        return 0

    def _king_safety(self, file_index: int, rank: int) -> int:
        if rank == 0 and file_index in (1, 2, 6):
            return 30
        if rank == 0 and file_index in (0, 7):
            return 15
        return 0

    def _bishop_pair_score(self, board: chess.Board) -> int:
        score = 0

        if len(board.pieces(chess.BISHOP, chess.WHITE)) >= 2:
            score += self.bishop_pair_bonus
        if len(board.pieces(chess.BISHOP, chess.BLACK)) >= 2:
            score -= self.bishop_pair_bonus

        return score

    def _mobility_score(self, board: chess.Board) -> int:
        mobility = board.legal_moves.count() * self.mobility_weight
        return mobility if board.turn == chess.WHITE else -mobility

    def _check_score(self, board: chess.Board) -> int:
        if not board.is_check():
            return 0

        return -self.check_penalty if board.turn == chess.WHITE else self.check_penalty


@dataclass(slots=True)
class ChessEngine:
    depth: int = 3
    evaluator: SimpleEvaluator = field(default_factory=SimpleEvaluator)

    def find_best_move(
        self,
        board: chess.Board,
        depth: int | None = None,
    ) -> SearchResult:
        search_depth = depth if depth is not None else self.depth
        if search_depth < 1:
            raise ValueError("Search depth must be at least 1.")

        stats = SearchStats()
        best_move: chess.Move | None = None
        best_score = -INFINITY
        alpha = -INFINITY
        beta = INFINITY

        for move in self._ordered_moves(board):
            board.push(move)
            score = -self._negamax(board, search_depth - 1, -beta, -alpha, 1, stats)
            board.pop()

            if score > best_score:
                best_score = score
                best_move = move

            alpha = max(alpha, best_score)

        if best_move is None:
            best_score = self._terminal_or_static_score(board, 0)

        return SearchResult(
            best_move=best_move,
            score=best_score,
            depth=search_depth,
            nodes=stats.nodes,
            cutoffs=stats.cutoffs,
        )

    def choose_move(self, board: chess.Board, depth: int | None = None) -> chess.Move | None:
        return self.find_best_move(board, depth).best_move

    def _negamax(
        self,
        board: chess.Board,
        depth: int,
        alpha: int,
        beta: int,
        ply: int,
        stats: SearchStats,
    ) -> int:
        stats.nodes += 1

        terminal_score = self._terminal_score(board, ply)
        if terminal_score is not None:
            return terminal_score

        if depth == 0:
            return self._static_score(board)

        best_score = -INFINITY

        for move in self._ordered_moves(board):
            board.push(move)
            score = -self._negamax(board, depth - 1, -beta, -alpha, ply + 1, stats)
            board.pop()

            best_score = max(best_score, score)
            alpha = max(alpha, score)

            if alpha >= beta:
                stats.cutoffs += 1
                break

        return best_score

    def _terminal_or_static_score(self, board: chess.Board, ply: int) -> int:
        terminal_score = self._terminal_score(board, ply)
        if terminal_score is not None:
            return terminal_score
        return self._static_score(board)

    def _terminal_score(self, board: chess.Board, ply: int) -> int | None:
        outcome = board.outcome(claim_draw=True)
        if outcome is None:
            return None

        if outcome.winner is None:
            return 0

        if outcome.winner == board.turn:
            return CHECKMATE_SCORE - ply

        return -CHECKMATE_SCORE + ply

    def _static_score(self, board: chess.Board) -> int:
        score = self.evaluator.evaluate(board)
        return score if board.turn == chess.WHITE else -score

    def _ordered_moves(self, board: chess.Board) -> list[chess.Move]:
        return sorted(
            board.legal_moves,
            key=lambda move: self._move_score(board, move),
            reverse=True,
        )

    def _move_score(self, board: chess.Board, move: chess.Move) -> int:
        score = 0

        if board.is_capture(move):
            victim = board.piece_at(move.to_square)

            if victim is None and board.is_en_passant(move):
                victim = chess.Piece(chess.PAWN, not board.turn)

            attacker = board.piece_at(move.from_square)
            victim_value = PIECE_VALUES.get(victim.piece_type, 0) if victim else 0
            attacker_value = PIECE_VALUES.get(attacker.piece_type, 0) if attacker else 0
            score += 10_000 + victim_value * 10 - attacker_value

        if move.promotion:
            score += 8_000 + PIECE_VALUES[move.promotion]

        if board.gives_check(move):
            score += 2_000

        if board.is_castling(move):
            score += 500

        score += self._destination_activity(move.to_square)
        return score

    def _destination_activity(self, square: chess.Square) -> int:
        rank = chess.square_rank(square)
        file_index = chess.square_file(square)
        center_distance = abs(file_index - 3.5) + abs(rank - 3.5)
        return int((7 - center_distance) * 10)
