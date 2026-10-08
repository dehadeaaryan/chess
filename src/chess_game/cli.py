import argparse
from pathlib import Path

import chess

from chess_game.engine import choose_move
from chess_game.game import Game


def main():
    parser = argparse.ArgumentParser(description='Aaryan Chess terminal game')
    parser.add_argument('--computer', action='store_true', help='Play Stockfish')
    parser.add_argument('--color', choices=['white', 'black'], default='white')
    parser.add_argument('--difficulty', choices=['easy', 'medium', 'hard'], default='medium')
    options = parser.parse_args()
    computer = options.computer
    human = options.color == 'white'
    game = Game()
    print('Aaryan Chess · SAN/UCI moves, undo, review N, live, resign, draw, pgn, import PATH, save PATH, new, quit')
    while True:
        if computer and not game.snapshot()['result'] and game.board.turn != human:
            try:
                game.play(choose_move(game.board, options.difficulty))
            except RuntimeError as exc:
                print(f'{exc} Enter retry, undo, new, or quit.')
        state = game.snapshot()
        print(f"\n{game.board}\n\n{state['result'] or ''} {state['termination'] or state['turn'] + ' to move'}")
        if state['last_move']:
            print('Last move:', ' → '.join(state['last_move']))
        if state['check']:
            print('Check:', state['checked_king'])
        print('Captures:', state['captured'], '| White material balance:', state['material_balance'])
        try:
            command = input('> ').strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if command in {'quit', 'exit'}:
            break
        try:
            if command in {'retry', 'live'}:
                continue
            if command == 'new':
                game = Game()
            elif command == 'undo':
                if computer and not human and len(game.history) == 1:
                    print('No player move to undo yet.')
                else:
                    count = 2 if computer and game.board.turn == human else 1
                    for _ in range(count):
                        game.undo()
            elif command == 'pgn':
                print(state['pgn'])
            elif command.startswith('review '):
                ply = int(command[7:])
                if not 0 <= ply <= len(game.history):
                    raise ValueError('Review ply must be between 0 and the current move count.')
                past = Game(game.history[:ply], game.initial_fen)
                print(f'\nReview {ply}/{len(game.history)}\n{past.board}\nLive game preserved.')
            elif command.startswith('import '):
                path = Path(command[7:]).expanduser()
                if path.stat().st_size > 60000:
                    raise ValueError('PGN files must be under 60 KB.')
                game = Game.from_pgn(path.read_text())
                computer = False
            elif command.startswith('save '):
                Path(command[5:]).expanduser().write_text(state['pgn'])
            elif computer and game.board.turn != human and not state['result']:
                print('Waiting for Stockfish. Use retry, undo, new, or quit.')
            elif command == 'resign':
                game.finish('white resigned' if game.board.turn else 'black resigned')
            elif command == 'draw':
                game.finish('draw claimed')
            else:
                game.play(command)
        except (ValueError, OSError) as exc:
            print(exc)


if __name__ == '__main__':
    main()
