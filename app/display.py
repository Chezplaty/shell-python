import sys


class Display:

    def __init__(self) -> None:
        """
        Tracks how many candidate lines are currently shown below the prompt.
        """
        self.candidate_lines = 0

    def display_prompt(self) -> None:
        sys.stdout.write("$ ")
        sys.stdout.flush()

    def echo(self, key: str) -> None:
        """
        Writes a single typed character to the terminal.
        """
        sys.stdout.write(key)
        sys.stdout.flush()

    def erase_last(self) -> None:
        """
        Erases the character immediately before the cursor on screen.
        """
        sys.stdout.write("\b \b")
        sys.stdout.flush()

    def move_cursor(self, sequence: str) -> None:
        """
        Writes the escape sequence to move the terminal cursor left or right.
        """
        if sequence == '[D': #left
            sys.stdout.write("\033[D")
        elif sequence == '[C': #right
            sys.stdout.write("\033[C")
        sys.stdout.flush()

    def redraw(self, new_word: str, old_word: str) -> None:
        """
        Erases the given characters before the cursor and writes output in their place.
        """

        if old_word: # a 0-length move is still interpreted as 1 by terminals, so skip it
            sys.stdout.write(f"\033[{len(old_word)}D") # move cursor to before prev word

        sys.stdout.write("\033[0K") # erase from cursor to end of line
        sys.stdout.write(f"{new_word}")
        sys.stdout.flush()

    def display_candidates(self, lines: list[str], buffer_len: int) -> None:
        """
        Prints candidate lines below the prompt without disturbing the cursor.
        Restores the cursor to its original position after drawing them.
        """
        column = buffer_len + 3 # "$ " (2 cols) + buffer, 1-indexed, just past the last typed char

        for line in lines:
            sys.stdout.write("\n\r")
            sys.stdout.write(line)

        sys.stdout.write(f"\033[{len(lines)}A") # back up to the prompt line
        sys.stdout.write(f"\033[{column}G") # restore the column cursor was at
        sys.stdout.flush()

        self.candidate_lines = len(lines)

    def clear_candidates(self) -> None:
        """
        Erases any previously displayed candidate lines from the terminal.
        Does nothing if no candidates are currently shown.
        """
        if not self.candidate_lines: # lines == 0
            return

        for _ in range(self.candidate_lines):
            sys.stdout.write("\033[B") # move down
            sys.stdout.write("\033[2K") # erase

        sys.stdout.write(f"\033[{self.candidate_lines}A\r")
        sys.stdout.flush()

        self.candidate_lines = 0

    def show_job_notice(self, text: str, buffer_text: str, cursor_pos: int) -> None:
        """
        Prints a completed job notification and redraws the current command line.
        Restores the cursor to its previous position after displaying the notification.
        """
        sys.stdout.write('\r\n')
        sys.stdout.write(f"{text}\n")

        sys.stdout.write("$ ")
        sys.stdout.write(buffer_text)
        sys.stdout.write(f"\033[{cursor_pos + 3}G")
        sys.stdout.flush()
