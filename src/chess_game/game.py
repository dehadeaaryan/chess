"""Pure game model shared by terminal and web clients."""
import io
import re
from typing import Literal

import chess
import chess.pgn

MAX_PLIES = 1200
Ending = Literal['white resigned', 'black resigned', 'draw claimed', 'draw by agreement']
VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}


class Game:
    def __init__(self, moves: list[str] | None = None, initial_fen: str = chess.STARTING_FEN, ending: Ending | None = None):
        self.board = chess.Board(initial_fen)
        if not self.board.is_valid():
            raise ValueError('Invalid starting position.')
        self.initial_fen = self.board.fen()
        self.history: list[str] = []
        self.captures: list[tuple[bool, str] | None] = []
        self.ending: Ending | None = None
        for move in moves or []:
            self.play(move)
        if ending:
            self.finish(ending)

    def play(self, notation: str) -> None:
        if len(self.history) >= MAX_PLIES:
            raise ValueError('Move limit reached.')
        if self.ending or self.board.is_game_over():
            raise ValueError('This game has ended. Start a new game.')
        try:
            move = self.board.parse_san(notation)
        except ValueError:
            try:
                move = self.board.parse_uci(notation)
            except ValueError as exc:
                raise ValueError('Illegal move. Use notation such as e4 or e2e4.') from exc
        if move not in self.board.legal_moves:
            raise ValueError('Illegal move. Passing a turn is not allowed.')
        captured = self.board.piece_at(move.to_square)
        if self.board.is_en_passant(move):
            captured = chess.Piece(chess.PAWN, not self.board.turn)
        self.captures.append((self.board.turn, captured.symbol()) if captured else None)
        self.history.append(self.board.san(move))
        self.board.push(move)

    def finish(self, ending: Ending) -> None:
        if self.ending or self.board.is_game_over():
            raise ValueError('This game has already ended.')
        if ending == 'draw claimed' and not self.board.can_claim_draw():
            raise ValueError('No draw is available by repetition or the fifty-move rule.')
        self.ending = ending

    def undo(self) -> None:
        self.ending = None
        if self.history:
            self.board.pop()
            self.history.pop()
            self.captures.pop()

    @classmethod
    def from_pgn(cls, text: str) -> 'Game':
        stream = io.StringIO(text)
        pgn = chess.pgn.read_game(stream)
        if pgn is None or pgn.errors:
            raise ValueError('Invalid PGN. Import one valid game.')
        if chess.pgn.read_game(stream) is not None:
            raise ValueError('Import one game at a time.')
        if pgn.headers.get('Variant', 'Standard') not in {'Standard', 'Chess'}:
            raise ValueError('Only standard chess PGNs are supported.')
        game = cls(initial_fen=pgn.board().fen())
        for move in pgn.mainline_moves():
            game.play(move.uci())
        if not game.history and not re.search(r'^\s*\[[A-Za-z]+\s+"', text, re.MULTILINE) and text.strip() != '*':
            raise ValueError('Invalid PGN. Include PGN headers or legal move notation.')
        result = pgn.headers.get('Result', '*')
        if result not in {'*', '1-0', '0-1', '1/2-1/2'}:
            raise ValueError('Invalid PGN result.')
        outcome = game.board.outcome()
        if outcome and result not in {'*', outcome.result()}:
            raise ValueError('PGN result contradicts the board position.')
        if not outcome and result != '*':
            ending = {'1-0': 'black resigned', '0-1': 'white resigned', '1/2-1/2': 'draw by agreement'}[result]
            if result == '1/2-1/2' and pgn.headers.get('Termination') == 'draw claimed':
                ending = 'draw claimed'
            game.finish(ending)
        return game

    def snapshot(self) -> dict:
        outcome = self.board.outcome()
        result = outcome.result() if outcome else None
        termination = outcome.termination.name.lower().replace('_', ' ') if outcome else None
        if self.ending:
            result = '0-1' if self.ending == 'white resigned' else '1-0' if self.ending == 'black resigned' else '1/2-1/2'
            termination = 'resignation' if 'resigned' in self.ending else self.ending
        pgn = chess.pgn.Game.from_board(self.board)
        pgn.headers['Result'] = result or '*'
        if self.ending:
            pgn.headers['Termination'] = self.ending
        captures = {color: [c[1] for c in self.captures if c and c[0] == (color == 'white')] for color in ['white', 'black']}
        material = sum(VALUES[p.piece_type] * (1 if p.color else -1) for p in self.board.piece_map().values())
        last = self.board.peek().uci() if self.board.move_stack else None
        checked = self.board.king(self.board.turn) if self.board.is_check() else None
        return {
            'initial_fen': self.initial_fen,
            'ending': self.ending,
            'fen': self.board.fen(),
            'turn': 'white' if self.board.turn else 'black',
            'pieces': {chess.square_name(s): p.symbol() for s, p in self.board.piece_map().items()},
            'legal_moves': [m.uci() for m in self.board.legal_moves] if not result else [],
            'moves': list(self.history),
            'check': self.board.is_check(),
            'checked_king': chess.square_name(checked) if checked is not None else None,
            'last_move': [last[:2], last[2:4]] if last else [],
            'captured': captures,
            'material_balance': material,
            'result': result,
            'termination': termination,
            'can_claim_draw': self.board.can_claim_draw() if not result else False,
            'pgn': str(pgn),
        }
