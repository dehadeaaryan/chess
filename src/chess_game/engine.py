"""Bounded Stockfish requests; no persistent mutable engine sessions."""
import os
from pathlib import Path
import shutil
import threading

import chess
import chess.engine

SLOTS = threading.BoundedSemaphore(1)


def engine_path() -> str | None:
    configured = os.environ.get('STOCKFISH_PATH')
    if configured:
        return configured if Path(configured).is_file() else None
    installed = shutil.which('stockfish')
    if installed:
        return installed
    for candidate in [Path(__file__).resolve().parents[2] / '.tools/stockfish/stockfish-macos-m1-apple-silicon', Path('/usr/games/stockfish')]:
        if candidate.is_file():
            return str(candidate)
    return None


def choose_move(board: chess.Board, difficulty: str) -> str:
    path = engine_path()
    if not path:
        raise RuntimeError('Stockfish is unavailable. Install it or set STOCKFISH_PATH, then retry.')
    if not SLOTS.acquire(timeout=2):
        raise RuntimeError('Stockfish is busy. Try again in a moment.')
    try:
        with chess.engine.SimpleEngine.popen_uci(path, timeout=5) as engine:
            skill, seconds = {'easy': (0, .1), 'medium': (8, .25), 'hard': (20, .5)}[difficulty]
            engine.configure({'Threads': 1, 'Hash': 16, 'Skill Level': skill})
            result = engine.play(board, chess.engine.Limit(time=seconds))
            if result.move is None or result.move not in board.legal_moves:
                raise RuntimeError('Stockfish did not return a legal move. Try again.')
            return result.move.uci()
    except (chess.engine.EngineError, OSError, TimeoutError) as exc:
        raise RuntimeError('Stockfish could not complete this move. Try again.') from exc
    finally:
        SLOTS.release()


def analyse(board: chess.Board) -> dict:
    path = engine_path()
    if not path:
        raise RuntimeError('Stockfish is unavailable. Install it or set STOCKFISH_PATH.')
    if not SLOTS.acquire(timeout=2):
        raise RuntimeError('Stockfish is busy. Try again in a moment.')
    try:
        with chess.engine.SimpleEngine.popen_uci(path, timeout=5) as engine:
            engine.configure({'Threads': 1, 'Hash': 16})
            infos = engine.analyse(board, chess.engine.Limit(time=.2), multipv=3)
            lines = []
            for info in infos:
                pv = info.get('pv', [])[:8]
                score = info['score'].white()
                explanation = 'No legal moves remain.'
                if pv:
                    move = pv[0]
                    piece = board.piece_at(move.from_square)
                    explanation = f'Moves the {chess.piece_name(piece.piece_type)} to {chess.square_name(move.to_square)}.'
                    if board.is_castling(move): explanation = 'Castles to bring the rook into play and shelter the king.'
                    elif board.is_capture(move):
                        target = board.piece_at(move.to_square)
                        explanation += f' Captures a {chess.piece_name(target.piece_type) if target else "pawn en passant"}.'
                    if move.promotion: explanation += f' Promotes to a {chess.piece_name(move.promotion)}.'
                    if board.gives_check(move): explanation += ' Gives check, forcing the opponent to respond.'
                lines.append({'explanation':explanation, 'cp': score.score(mate_score=10000), 'mate': score.mate(),
                              'uci': [m.uci() for m in pv], 'san': board.variation_san(pv)})
            threats = []
            for square, piece in board.piece_map().items():
                if piece.color == board.turn and piece.piece_type != chess.KING and board.is_attacked_by(not piece.color, square) and not board.is_attacked_by(piece.color, square):
                    threats.append({'square':chess.square_name(square), 'piece':chess.piece_name(piece.piece_type)})
            return {'threats':threats, 'lines': lines, 'cp': lines[0]['cp'] if lines else 0,
                    'mate': lines[0]['mate'] if lines else None}
    except (chess.engine.EngineError, OSError, TimeoutError) as exc:
        raise RuntimeError('Stockfish could not analyse this position. Retry.') from exc
    finally:
        SLOTS.release()
