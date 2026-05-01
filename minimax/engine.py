from random import randrange


class TicTacToe:
    def __init__(self):
        while True:
            self.first_move_row = randrange(0, 3, 2)
            self.first_move_col = randrange(0, 3, 2)
            self.board = [[0, 0, 0] for _ in range(3)]
            self.bot_team = int(input('Input computer team (1 -> X, 2 -> O): '))
            self.player_team = 3 - self.bot_team
            self.moves = 0
            if self.bot_team == 1 or self.bot_team == 2:
                break

    def check_win(self, board, team):
        for i in range(3):
            if board[i][0] == board[i][1] == board[i][2] == team:
                return True
            if board[0][i] == board[1][i] == board[2][i] == team:
                return True

        if (board[0][0] == board[1][1] == board[2][2] == team or
                board[0][2] == board[1][1] == board[2][0] == team):
            return True

        if all(cell != 0 for row in board for cell in row):
            return None

        return False

    def minimax(self, minimax_board, is_maximizing):
        if self.check_win(minimax_board, self.bot_team) is True:
            return float('inf')
        if self.check_win(minimax_board, self.player_team) is True:
            return float('-inf')
        if all(cell != 0 for row in minimax_board for cell in row):
            return 0

        if is_maximizing:
            best_score = -float('inf')
            for row in range(3):
                for col in range(3):
                    if minimax_board[row][col] == 0:
                        minimax_board[row][col] = self.bot_team
                        score = self.minimax(minimax_board, False)
                        minimax_board[row][col] = 0
                        best_score = max(score, best_score)
            return best_score
        else:
            best_score = float('inf')
            for row in range(3):
                for col in range(3):
                    if minimax_board[row][col] == 0:
                        minimax_board[row][col] = self.player_team
                        score = self.minimax(minimax_board, True)
                        minimax_board[row][col] = 0
                        best_score = min(score, best_score)
            return best_score

    def bot_move(self):
        best_score = float('-inf')
        best_move = (-1, -1)

        for row in range(3):
            for col in range(3):
                if self.board[row][col] == 0:
                    self.board[row][col] = self.bot_team
                    score = self.minimax(self.board, False)
                    self.board[row][col] = 0
                    if score > best_score:
                        best_score = score
                        best_move = (row, col)

        if best_move != (-1, -1):
            self.board[best_move[0]][best_move[1]] = self.bot_team
            self.moves += 1

    def game(self):
        while True:
            if not (self.bot_team == 1 and self.moves == 0):
                print('\nCurrent board:')
                for row in self.board:
                    print(' '.join(['X' if cell == 1 else 'O' if cell == 2 else '.' for cell in row]))

            if self.check_win(self.board, self.bot_team):
                print("Computer wins!")
                break
            if self.check_win(self.board, self.player_team):
                print("Player wins!")
                break
            if self.check_win(self.board, None) is None:
                print("It's a draw!")
                break

            if (self.bot_team == 1 and self.moves % 2 == 0) or (self.bot_team == 2 and self.moves % 2 == 1):
                self.bot_move()
            else:
                print('\nPossible moves:')
                print('00 01 02\n10 11 12\n20 21 22')
                while True:
                    move = input('Your move (e.g. "02" for row 0, column 2): ').strip()
                    if len(move) == 2 and move.isdigit():
                        row, col = int(move[0]), int(move[1])
                        if 0 <= row <= 2 and 0 <= col <= 2 and self.board[row][col] == 0:
                            self.board[row][col] = self.player_team
                            self.moves += 1
                            break
                    print('Invalid move. Please enter two digits like "02" for row 0, column 2')


if __name__ == "__main__":
    TicTacToe().game()
