from typing import Annotated, Literal

import chess
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from chess_game.game import Ending, Game, MAX_PLIES
from chess_game.engine import choose_move, engine_path

app = FastAPI(title='Aaryan Chess', version='1.1.0')
MoveText = Annotated[str, StringConstraints(min_length=2, max_length=16)]


class PositionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    moves: list[MoveText] = Field(default_factory=list, max_length=MAX_PLIES)
    initial_fen: str = Field(default=chess.STARTING_FEN, max_length=128)
    ending: Ending | None = None
    move: MoveText | None = None
    action: Literal['resign', 'claim_draw'] | None = None
    review_ply: int | None = Field(default=None, ge=0, le=MAX_PLIES)


class EngineRequest(PositionRequest):
    difficulty: Literal['easy', 'medium', 'hard'] = 'medium'


class ImportRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    pgn: str = Field(min_length=1, max_length=60000)


def restore(request: PositionRequest) -> Game:
    return Game(request.moves, request.initial_fen, request.ending)


@app.get('/api/health')
def health():
    return {'status': 'ok'}


@app.get('/api/engine')
def engine_status():
    return {'available': engine_path() is not None}


@app.post('/api/position')
def position(request: PositionRequest):
    try:
        game = restore(request)
        if request.review_ply is not None:
            if request.move or request.action or request.review_ply > len(game.history):
                raise ValueError('Invalid history review request.')
            return Game(game.history[:request.review_ply], game.initial_fen).snapshot()
        if request.move and request.action:
            raise ValueError('Choose a move or a game-ending action.')
        if request.move:
            game.play(request.move)
        if request.action:
            game.finish(('white resigned' if game.board.turn else 'black resigned') if request.action == 'resign' else 'draw claimed')
        return game.snapshot()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post('/api/import')
def import_pgn(request: ImportRequest):
    try:
        return Game.from_pgn(request.pgn).snapshot()
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post('/api/engine-move')
def engine_move(request: EngineRequest):
    try:
        if request.action or request.review_ply is not None or request.move:
            raise ValueError('Engine requests must contain only the current game and difficulty.')
        game = restore(request)
        if game.snapshot()['result']:
            raise ValueError('This game has ended.')
        game.play(choose_move(game.board, request.difficulty))
        return game.snapshot()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

# Analysis stays position-sized so long games do not monopolize an API worker.
@app.post('/api/analyse')
def analysis(request: PositionRequest):
    from chess_game.engine import analyse
    try:
        game = restore(request)
        if request.review_ply is not None:
            game = Game(game.history[:request.review_ply], game.initial_fen)
        return analyse(game.board)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


@app.post('/api/replays')
def create_replay(request: PositionRequest):
    from chess_game.social import create
    try:
        game = restore(request)
        return {'id': create('replay', {'moves':game.history, 'initial_fen':game.initial_fen, 'ending':game.ending})}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get('/api/replays/{identity}')
def replay(identity: str):
    from chess_game.social import connect, read
    try:
        with connect() as db:
            body=read(db, identity, 'replay')
            if 'snapshot' in body: return body['snapshot']
            return Game(**body).snapshot()
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


class MatchCreate(BaseModel):
    clock: Literal[0, 180, 300, 600] = 0


class MatchUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    token: str = Field(default='', max_length=128)
    revision: int | None = None
    move: MoveText | None = None
    action: Literal['resign', 'claim_draw'] | None = None


@app.post('/api/matches')
def create_match(request: MatchCreate):
    import secrets, time
    from chess_game.social import create, digest
    token = secrets.token_urlsafe(32)
    body = {'white':digest(token), 'black':None, 'moves':[], 'ending':None, 'revision':0,
            'clock':request.clock, 'remaining':{'white':request.clock,'black':request.clock}, 'updated':time.time()}
    try:
        return {'id':create('match',body), 'token':token}
    except ValueError as exc:
        raise HTTPException(503, str(exc)) from exc


@app.post('/api/matches/{identity}/join')
def join_match(identity: str):
    import secrets
    from chess_game.social import update
    token = secrets.token_urlsafe(32)
    try:
        return {**update(identity, token, join=True), 'token':token}
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.post('/api/matches/{identity}')
def match(identity: str, request: MatchUpdate):
    from chess_game.social import update
    try:
        if request.move and request.action:
            raise ValueError('Choose a move or an action.')
        return update(identity, request.token, request.revision, request.move, request.action)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


# Small curated collection: daily rotation, always validated by the shared rules.
PUZZLES = [
    ('6k1/5ppp/8/8/8/8/5PPP/4R1K1 w - - 0 1', ['e1e8'], 'Use the back rank.'),
    ('7k/5K2/6Q1/8/8/8/8/8 w - - 0 1', ['g6g7'], 'Bring the queen closer, protected by your king.'),
    ('7k/5K2/8/6Q1/8/8/8/8 w - - 0 1', ['g5g7'], 'Find a protected queen check.')
]


@app.get('/api/puzzle')
def daily_puzzle():
    from datetime import datetime, timezone
    day = datetime.now(timezone.utc).date()
    index = day.toordinal() % len(PUZZLES)
    fen, solution, hint = PUZZLES[index]
    return {'day':str(day), 'id':index, 'position':Game(initial_fen=fen).snapshot(), 'hint':hint}


class PuzzleAttempt(BaseModel):
    day: str = Field(max_length=10)
    move: MoveText


@app.post('/api/puzzle')
def puzzle_attempt(request: PuzzleAttempt):
    daily = daily_puzzle()
    if request.day != daily['day']:
        raise HTTPException(409, 'A new daily puzzle is ready. Reload it.')
    fen, solution, _ = PUZZLES[daily['id']]
    game = Game(initial_fen=fen)
    try:
        move = game.board.parse_san(request.move)
    except ValueError:
        raise HTTPException(422, 'Choose a legal move.')
    if move not in game.board.legal_moves:
        raise HTTPException(422, 'Choose a legal move.')
    candidate = game.board.copy()
    candidate.push(move)
    correct = candidate.is_checkmate()
    if correct: game.play(move.uci())
    return {'correct':correct, 'position':game.snapshot()}


@app.post('/api/matches/{identity}/replay')
def match_replay(identity: str):
    from chess_game.social import create, update
    try:
        current=update(identity, '')
        return {'id':create('replay', {'snapshot':current['position']})}
    except ValueError as exc:
        raise HTTPException(404,str(exc)) from exc
