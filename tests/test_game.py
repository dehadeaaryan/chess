import chess
import pytest
from fastapi.testclient import TestClient

from chess_game.api import app
from chess_game.game import Game


def test_replay_and_undo():
    game = Game(["e4", "e5", "Nf3"])
    assert game.snapshot()["turn"] == "black"
    assert Game(game.history).board.fen() == game.board.fen()
    game.undo()
    assert game.snapshot()["turn"] == "white"
    assert "1. e4 e5" in game.snapshot()["pgn"]


@pytest.mark.parametrize("move", ["e2e5", "a9a8", "e7e5", "e1e2", "0000"])
def test_reject_illegal_moves(move):
    game = Game()
    with pytest.raises(ValueError):
        game.play(move)
    assert game.board.fen() == chess.STARTING_FEN


def test_checkmate_and_terminal_guard():
    game = Game(["f3", "e5", "g4", "Qh4#"])
    assert game.snapshot()["result"] == "0-1"
    assert game.snapshot()["legal_moves"] == []
    with pytest.raises(ValueError):
        game.play("e4")


def test_castling():
    game = Game(["e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6", "O-O"])
    assert game.board.piece_at(chess.G1).piece_type == chess.KING
    assert game.board.piece_at(chess.F1).piece_type == chess.ROOK


def test_en_passant():
    game = Game(["e4", "a6", "e5", "d5", "exd6"])
    assert game.board.piece_at(chess.D5) is None
    assert game.board.piece_at(chess.D6).piece_type == chess.PAWN


def test_promotion():
    game = Game(["a4", "h5", "a5", "h4", "a6", "h3", "axb7", "hxg2", "bxa8=N"])
    assert game.board.piece_at(chess.A8).piece_type == chess.KNIGHT


def test_repetition_history_survives_replay():
    game = Game(["Nf3", "Nf6", "Ng1", "Ng8"] * 2)
    assert game.snapshot()["can_claim_draw"]
    assert not game.snapshot()["result"]


def test_stalemate_and_insufficient_material():
    game = Game()
    game.board = chess.Board("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
    assert game.snapshot()["termination"] == "stalemate"
    game.board = chess.Board("7k/8/6K1/8/8/8/8/8 w - - 0 1")
    assert game.snapshot()["termination"] == "insufficient material"


def test_http_contract_and_validation():
    client = TestClient(app)
    assert client.get("/api/health").json() == {"status": "ok"}
    response = client.post("/api/position", json={"moves": ["e4"], "move": "e7e5"})
    assert response.status_code == 200
    assert response.json()["moves"] == ["e4", "e5"]
    assert client.post("/api/position", json={"moves": ["e5"]}).status_code == 422
    assert client.post("/api/position", json={"moves": [], "unexpected": True}).status_code == 422
    assert client.post("/api/position", json={"moves": ["e4"] * 1201}).status_code == 422


def test_highlights_and_capture_undo():
    game = Game(['e4', 'd5', 'exd5'])
    state = game.snapshot()
    assert state['last_move'] == ['e4', 'd5']
    assert state['captured'] == {'white': ['p'], 'black': []}
    assert state['material_balance'] == 1
    game.undo()
    assert game.snapshot()['captured']['white'] == []
    mate = Game(['f3', 'e5', 'g4', 'Qh4#']).snapshot()
    assert mate['checked_king'] == 'e1'


def test_en_passant_capture_accounting_and_promoted_material():
    game = Game(['e4', 'a6', 'e5', 'd5', 'exd6'])
    assert game.snapshot()['captured']['white'] == ['p']
    promoted = Game(['a4', 'h5', 'a5', 'h4', 'a6', 'h3', 'axb7', 'hxg2', 'bxa8=N'])
    assert promoted.snapshot()['captured']['white'] == ['p', 'r']
    assert promoted.snapshot()['material_balance'] == 7


def test_resign_and_restore_result():
    game = Game(['e4'])
    game.finish('black resigned')
    assert game.snapshot()['result'] == '1-0'
    assert game.snapshot()['legal_moves'] == []
    with pytest.raises(ValueError):
        game.play('e5')
    restored = Game(game.history, game.initial_fen, game.ending)
    assert restored.snapshot()['result'] == '1-0'
    assert Game.from_pgn(game.snapshot()['pgn']).snapshot()['result'] == '1-0'


def test_claim_draw_validation_and_pgn_roundtrip():
    with pytest.raises(ValueError):
        Game().finish('draw claimed')
    game = Game(['Nf3', 'Nf6', 'Ng1', 'Ng8'] * 2)
    game.finish('draw claimed')
    assert game.snapshot()['result'] == '1/2-1/2'
    assert Game.from_pgn(game.snapshot()['pgn']).ending == 'draw claimed'
    fifty = Game(initial_fen='7k/8/8/8/8/8/8/R5K1 w - - 100 51')
    fifty.finish('draw claimed')
    assert fifty.snapshot()['result'] == '1/2-1/2'


@pytest.mark.parametrize('pgn', ['not a PGN', '1. e5 *', '1. e4 *\n\n[Event "second"]\n\n1. d4 *', '[Result "1-0"]\n\n1. f3 e5 2. g4 Qh4# 1-0'])
def test_reject_invalid_pgn(pgn):
    with pytest.raises(ValueError):
        Game.from_pgn(pgn)


def test_pgn_custom_position_and_replay():
    text = '[SetUp "1"]\n[FEN "7k/8/8/8/8/8/8/R5K1 b - - 0 12"]\n[Result "*"]\n\n12... Kh7 *'
    imported = Game.from_pgn(text)
    assert imported.history == ['Kh7']
    assert Game(imported.history, imported.initial_fen).board.fen() == imported.board.fen()
    assert '[FEN ' in imported.snapshot()['pgn']


def test_review_does_not_change_live_game_and_action_endpoints():
    client = TestClient(app)
    live = {'moves': ['e4', 'e5', 'Nf3']}
    reviewed = client.post('/api/position', json={**live, 'review_ply': 1}).json()
    assert reviewed['moves'] == ['e4']
    assert client.post('/api/position', json=live).json()['moves'] == live['moves']
    assert client.post('/api/position', json={**live, 'review_ply': 4}).status_code == 422
    assert client.post('/api/position', json={**live, 'review_ply': 1, 'move': 'Nc6'}).status_code == 422
    assert client.post('/api/position', json={'action': 'claim_draw'}).status_code == 422
    ended = client.post('/api/position', json={**live, 'action': 'resign'}).json()
    assert ended['result'] == '1-0'
    assert client.post('/api/import', json={'pgn': ended['pgn']}).json()['result'] == '1-0'


def test_engine_missing_and_bad_requests(monkeypatch):
    from chess_game import engine
    monkeypatch.setenv('STOCKFISH_PATH', '/does/not/exist')
    client = TestClient(app)
    assert not client.get('/api/engine').json()['available']
    assert client.post('/api/engine-move', json={}).status_code == 503
    assert client.post('/api/engine-move', json={'difficulty': 'invalid'}).status_code == 422
    assert client.post('/api/engine-move', json={'moves': ['f3', 'e5', 'g4', 'Qh4#']}).status_code == 422


def test_real_stockfish_returns_legal_move():
    from chess_game.engine import engine_path
    if not engine_path():
        pytest.skip('Stockfish is not installed')
    client = TestClient(app)
    response = client.post('/api/engine-move', json={'moves': ['e4'], 'difficulty': 'easy'})
    assert response.status_code == 200
    state = response.json()
    assert len(state['moves']) == 2
    assert state['turn'] == 'white'
    assert Game(state['moves']).board.is_valid()


@pytest.mark.parametrize('fen', [
    '4k3/8/8/8/2b5/8/8/4K2R w K - 0 1',  # f1 is attacked
    'k3r3/8/8/8/8/8/8/4K2R w K - 0 1',  # king is in check
])
def test_no_castling_through_or_out_of_check(fen):
    game = Game(initial_fen=fen)
    with pytest.raises(ValueError):
        game.play('O-O')


def test_moved_rook_cannot_castle_even_after_returning():
    game = Game(['Rh2','Rh7','Rh1','Rh8'], initial_fen='r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1')
    with pytest.raises(ValueError):
        game.play('O-O')
    assert 'e1c1' in game.snapshot()['legal_moves']
