"""Durable invitations and immutable replays, with atomic game updates."""
import json
import os
from pathlib import Path
import secrets
import sqlite3
import time
import chess.pgn
import hashlib

from chess_game.game import Game


def connect():
    path = Path(os.environ.get('CHESS_DB', 'data/chess.sqlite3'))
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute('CREATE TABLE IF NOT EXISTS records (id TEXT PRIMARY KEY, kind TEXT, body TEXT, created REAL)')
    return db


def create(kind, body):
    identity = secrets.token_urlsafe(18)
    with connect() as db:
        # Keep anonymous local hosting bounded; links expire after 30 days.
        db.execute('DELETE FROM records WHERE created < ?', (time.time() - 30*86400,))
        if db.execute('SELECT count(*) FROM records').fetchone()[0] >= 10000:
            raise ValueError('Storage is full. Try again later.')
        db.execute('INSERT INTO records VALUES (?, ?, ?, ?)', (identity, kind, json.dumps(body), time.time()))
    return identity


def read(db, identity, kind):
    row = db.execute('SELECT body FROM records WHERE id=? AND kind=? AND created>?', (identity, kind, time.time()-30*86400)).fetchone()
    if not row:
        raise ValueError('This link is invalid or has expired.')
    return json.loads(row['body'])


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def tick(body):
    game = Game(body['moves'], ending=body.get('ending'))
    if body['clock'] and body.get('black') and not game.snapshot()['result']:
        color = game.snapshot()['turn']
        body['remaining'][color] = max(0, body['remaining'][color] - (time.time() - body['updated']))
        if body['remaining'][color] == 0:
            # A side unable to mate receives a draw on a flag fall.
            import chess
            winner = not game.board.turn
            body['flag_result'] = '1/2-1/2' if game.board.has_insufficient_material(winner) else ('1-0' if winner else '0-1')
    body['updated'] = time.time()
    return game


def snapshot(body, token=''):
    game = tick(body)
    result = game.snapshot()
    if body.get('flag_result'):
        result.update(result=body['flag_result'], termination='time forfeit', legal_moves=[],can_claim_draw=False)
        pgn = chess.pgn.Game.from_board(game.board)
        pgn.headers['Result'] = body['flag_result']
        pgn.headers['Termination'] = 'time forfeit'
        result['pgn'] = str(pgn)
    role = next((c for c in ['white', 'black'] if body.get(c) == digest(token)), None) if token else None
    return {'position': result, 'revision': body['revision'], 'role': role, 'joined': bool(body.get('black')), 'remaining': body['remaining'], 'clock': body['clock']}


def update(identity, token, revision=None, move=None, action=None, join=False):
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        body = read(db, identity, 'match')
        if join:
            if body.get('black'):
                raise ValueError('This match already has two players.')
            body['black'] = digest(token)
            body['updated'] = time.time()
            body['revision'] += 1
        game = tick(body)
        role = next((c for c in ['white','black'] if body.get(c) == digest(token)), None) if token else None
        if move or action:
            if not role:
                raise PermissionError('A player key is required.')
            if revision != body['revision']:
                raise ValueError('The board changed. Refresh and try again.')
            if not body.get('black'):
                raise ValueError('Wait for your friend to join.')
            if game.snapshot()['result'] or body.get('flag_result'):
                raise ValueError('This match has ended.')
            if action == 'resign':
                game.finish(f'{role} resigned')
            else:
                if game.snapshot()['turn'] != role:
                    raise ValueError('It is not your turn.')
                if action == 'claim_draw': game.finish('draw claimed')
                elif move: game.play(move)
            body['moves'] = game.history
            body['ending'] = game.ending
            body['revision'] += 1
        db.execute('UPDATE records SET body=? WHERE id=?', (json.dumps(body), identity))
        return snapshot(body, token)
