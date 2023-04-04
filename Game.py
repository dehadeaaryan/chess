from Board import Board
from Piece import Piece

class Game:
    def __init__(self):
        self.board = Board()
        self.board.initialize()

        self.turns = ["White", "Black"]

        self.running = False

    def start(self):
        self.running = True
        turn = self.turns[0]
        while self.running:

            print()
            self.board.printBoard()
            print(turn + " plays")

            piece = None
            endPosition = None

            validPosition = False
            while not validPosition:
                startPosition = input("Enter the position of the piece you want to move: ")
                startPosition = self.parsePosition(startPosition)
                print(startPosition)
                if startPosition is not None:
                    piece = self.board.grid[startPosition[0]][startPosition[1]]
                    if piece != 0:
                        if piece.color == turn:
                            validPosition = True
                        else:
                            print("That's not your piece")
                    else:
                        print("There's no piece there")

            validPosition = False
            while not validPosition:
                endPosition = input("Enter the position you want to move the piece to: ")
                endPosition = self.parsePosition(endPosition)
                if endPosition is not None and piece.isValidMove(self.board, endPosition):
                    validPosition = True
            
            self.move(piece, endPosition)


            if turn == "white":
                turn = self.turns[1]
            else:
                turn = self.turns[0]

    def move(self, piece, end):
        if piece.isValidMove(self.board, end):
            i, j = self.board.getPosition(piece)
            self.board.grid[i][j] = 0
            self.board.grid[end[0]][end[1]] = piece
        else:
            print("Invalid move")
    
    def parsePosition(self, position):
        if len(position) == 2:
            if position[0].isalpha() and position[1].isnumeric():

                row = 7 - (int(position[1]) - 1)
                column = ord(position[0].lower()) - 97

                return (row, column)
            else:
                return None
        else:
            return None