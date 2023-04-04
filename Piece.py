class Piece:
    def __init__(self, number, color):
        self.number = number
        self.color = color

        self.pieces = {
            1: "King",
            2: "Queen",
            3: "Bishop",
            4: "Rook",
            5: "Knight",
            6: "Pawn"
        }

        self.type = self.pieces[self.number]
        self.symbol = self.type[0].upper() if self.color == "White" else self.type[0].lower()
        if self.type == "King":
            self.symbol = "N" if self.color == "White" else "n"

    
    def isValidMove(self, board, end):
        start = board.getPosition(self)
        if self.type == "King":
            return self.isValidKingMove(board, start, end)
        elif self.type == "Queen":
            return self.isValidQueenMove(board, start, end)
        elif self.type == "Bishop":
            return self.isValidBishopMove(board, start, end)
        elif self.type == "Rook":
            return self.isValidRookMove(board, start, end)
        elif self.type == "Knight":
            return self.isValidKnightMove(board, start, end)
        elif self.type == "Pawn":
            return self.isValidPawnMove(board, start, end)
    
    def isValidKingMove(self, board, start, end):
        if abs(start[0] - end[0]) <= 1 and abs(start[1] - end[1]) <= 1:
            return True
        return False
    
    def isValidQueenMove(self, board, start, end):
        if self.isValidBishopMove(board, start, end) or self.isValidRookMove(board, start, end):
            return True
        return False
    
    def isValidBishopMove(self, board, start, end):
        if abs(start[0] - end[0]) == abs(start[1] - end[1]):
            if start[0] < end[0]:
                if start[1] < end[1]:
                    for i in range(start[0] + 1, end[0]):
                        if board.grid[i][i] != 0:
                            return False
                else:
                    for i in range(start[0] + 1, end[0]):
                        if board.grid[i][start[1] - i] != 0:
                            return False
            else:
                if start[1] < end[1]:
                    for i in range(end[0] + 1, start[0]):
                        if board.grid[i][i] != 0:
                            return False
                else:
                    for i in range(end[0] + 1, start[0]):
                        if board.grid[i][start[1] - i] != 0:
                            return False
            return True
        return False
    
    def isValidRookMove(self, board, start, end):
        if start[0] == end[0]:
            if start[1] < end[1]:
                for i in range(start[1] + 1, end[1]):
                    if board.grid[start[0]][i] != 0:
                        return False
            else:
                for i in range(end[1] + 1, start[1]):
                    if board.grid[start[0]][i] != 0:
                        return False
            return True
        elif start[1] == end[1]:
            if start[0] < end[0]:
                for i in range(start[0] + 1, end[0]):
                    if board.grid[i][start[1]] != 0:
                        return False
            else:
                for i in range(end[0] + 1, start[0]):
                    if board.grid[i][start[1]] != 0:
                        return False
            return True
        return False
    
    def isValidKnightMove(self, board, start, end):
        if abs(start[0] - end[0]) == 2 and abs(start[1] - end[1]) == 1:
            return True
        elif abs(start[0] - end[0]) == 1 and abs(start[1] - end[1]) == 2:
            return True
        return False

    def isValidPawnMove(self, board, start, end):
        if self.color == "White":
            if start[0] == 1:
                if start[0] + 2 == end[0] and start[1] == end[1]:
                    if board.grid[start[0] + 1][start[1]] == 0 and board.grid[end[0]][end[1]] == 0:
                        return True
            if start[0] + 1 == end[0] and start[1] == end[1]:
                if board.grid[end[0]][end[1]] == 0:
                    return True
            if start[0] + 1 == end[0] and abs(start[1] - end[1]) == 1:
                if board.grid[end[0]][end[1]] != 0:
                    return True
        else:
            if start[0] == 6:
                if start[0] - 2 == end[0] and start[1] == end[1]:
                    if board.grid[start[0] - 1][start[1]] == 0 and board.grid[end[0]][end[1]] == 0:
                        return True
            if start[0] - 1 == end[0] and start[1] == end[1]:
                if board.grid[end[0]][end[1]] == 0:
                    return True
            if start[0] - 1 == end[0] and abs(start[1] - end[1]) == 1:
                if board.grid[end[0]][end[1]] != 0:
                    return True
        return False

