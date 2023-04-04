from Piece import Piece

class Board:
    def __init__(self):
        self.grid = [[0 for i in range(8)] for j in range(8)]
    
    def initialize(self):
        # White Pieces
        self.grid[0][0] = Piece(4, "White")
        self.grid[0][1] = Piece(5, "White")
        self.grid[0][2] = Piece(3, "White")
        self.grid[0][3] = Piece(2, "White")
        self.grid[0][4] = Piece(1, "White")
        self.grid[0][5] = Piece(3, "White")
        self.grid[0][6] = Piece(5, "White")
        self.grid[0][7] = Piece(4, "White")
        for i in range(8):
            self.grid[1][i] = Piece(6, "White")
        
        # Black Pieces
        self.grid[7][0] = Piece(4, "Black")
        self.grid[7][1] = Piece(5, "Black")
        self.grid[7][2] = Piece(3, "Black")
        self.grid[7][3] = Piece(2, "Black")
        self.grid[7][4] = Piece(1, "Black")
        self.grid[7][5] = Piece(3, "Black")
        self.grid[7][6] = Piece(5, "Black")
        self.grid[7][7] = Piece(4, "Black")
        for i in range(8):
            self.grid[6][i] = Piece(6, "Black")
        
    def printBoard(self):
        output = ""

        for i in range(8):
            for j in range(8):
                if self.grid[i][j] == 0:
                    output += "- "
                else:
                    output += self.grid[i][j].symbol + " "
            output += "\n"
        
        print(output)

    def getPosition(self, piece: Piece):
        for i in range(8):
            for j in range(8):
                if self.grid[i][j] == piece:
                    return (i, j)
        return None
