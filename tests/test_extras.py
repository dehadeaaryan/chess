import concurrent.futures
import time
import chess
from fastapi.testclient import TestClient
from chess_game.api import app, PUZZLES
from chess_game.social import connect, read

client = TestClient(app)


def test_puzzles_are_valid_and_accept_mate():
    for fen, moves, _ in PUZZLES:
        board = chess.Board(fen)
        assert board.is_valid()
        for move in moves:
            board.push_uci(move)
        assert board.is_checkmate()
    daily = client.get('/api/puzzle').json()
    board = chess.Board(daily['position']['fen'])
    mate = next(m for m in board.legal_moves if (lambda b: (b.push(m), b.is_checkmate())[1])(board.copy()))
    response = client.post('/api/puzzle', json={'day':daily['day'],'move':mate.uci()})
    assert response.json()['correct']
    assert response.json()['position']['result']
    assert client.post('/api/puzzle', json={'day':'2000-01-01','move':mate.uci()}).status_code == 409


def test_replay_is_durable_and_immutable(tmp_path, monkeypatch):
    monkeypatch.setenv('CHESS_DB',str(tmp_path/'games.sqlite3'))
    identity = client.post('/api/replays',json={'moves':['e4','e5']}).json()['id']
    assert client.get(f'/api/replays/{identity}').json()['moves']==['e4','e5']
    assert client.get('/api/replays/missing').status_code == 404
    assert client.post('/api/replays',json={'moves':['e5']}).status_code==422


def test_friend_auth_turns_revision_and_resignation(tmp_path,monkeypatch):
    monkeypatch.setenv('CHESS_DB',str(tmp_path/'games.sqlite3'))
    created=client.post('/api/matches',json={'clock':0}).json()
    path=f"/api/matches/{created['id']}"
    white=created['token']
    assert client.post(path,json={'token':white,'revision':0,'move':'e4'}).status_code==409
    joined=client.post(path+'/join',json={}).json()
    black=joined['token']
    assert joined['role']=='black'
    assert client.post(path+'/join',json={}).status_code==409
    assert client.post(path,json={'revision':1,'move':'e4'}).status_code==403
    assert client.post(path,json={'token':black,'revision':1,'move':'e4'}).status_code==409
    next=client.post(path,json={'token':white,'revision':1,'move':'e4'}).json()
    assert next['revision']==2
    assert client.post(path,json={'token':white,'revision':1,'move':'e5'}).status_code==409
    assert client.post(path,json={'token':black,'revision':2,'move':'e5'}).json()['position']['moves']==['e4','e5']
    assert client.post(path,json={'token':black,'revision':3,'action':'resign'}).json()['position']['result']=='1-0'


def test_friend_concurrent_move_only_one_wins(tmp_path,monkeypatch):
    monkeypatch.setenv('CHESS_DB',str(tmp_path/'games.sqlite3'))
    created=client.post('/api/matches',json={}).json()
    path=f"/api/matches/{created['id']}"
    client.post(path+'/join',json={})
    def play(move):
        return client.post(path,json={'token':created['token'],'revision':1,'move':move}).status_code
    with concurrent.futures.ThreadPoolExecutor() as pool:
        assert sorted(pool.map(play,['e4','d4']))==[200,409]


def test_clock_runs_only_after_join_and_flags(tmp_path,monkeypatch):
    monkeypatch.setenv('CHESS_DB',str(tmp_path/'games.sqlite3'))
    created=client.post('/api/matches',json={'clock':180}).json()
    path=f"/api/matches/{created['id']}"
    with connect() as db:
        body=read(db,created['id'],'match')
        body['updated']=time.time()-1000
        import json
        db.execute('UPDATE records SET body=? WHERE id=?',(json.dumps(body),created['id']))
    assert client.post(path,json={}).json()['remaining']['white']==180
    client.post(path+'/join',json={})
    with connect() as db:
        body=read(db,created['id'],'match');body['updated']=time.time()-181
        db.execute('UPDATE records SET body=? WHERE id=?',(json.dumps(body),created['id']))
    result=client.post(path,json={}).json()
    assert result['position']['result']=='0-1'
    assert result['position']['legal_moves']==[]
    assert client.post(path,json={'token':created['token'],'revision':1,'move':'e4'}).status_code==409


def test_analysis_returns_legal_candidates():
    from chess_game.engine import engine_path
    if not engine_path():
        import pytest
        pytest.skip('Stockfish not installed')
    data=client.post('/api/analyse',json={'moves':['e4']}).json()
    board=chess.Board();board.push_san('e4')
    assert isinstance(data['cp'],int)
    for line in data['lines']:
        b=board.copy()
        for move in line['uci']:
            assert chess.Move.from_uci(move) in b.legal_moves
            b.push_uci(move)
