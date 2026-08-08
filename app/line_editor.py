import sys

from app.tab_completion import CandidateCursor, format_candidates, get_candidates, bell

def redraw(output: str) -> None:
    """
    Clears the current terminal line and redraws the shell prompt.
    Displays the provided output after the prompt symbol.
    """

    sys.stdout.write("\r\033[2K") #clear line
    sys.stdout.write(f"$ {output}")
    sys.stdout.flush()


class LineEditor:

    def __init__(self, choices: list[str]) -> None:
        """
        Sets up an empty input buffer and stores the known completion choices.
        """
        self.buffer = []
        self.tab_cursor = None
        self.choices = choices
        self.candidate_lines = 0

    def run(self) -> str:
        """
        Reads keystrokes one at a time, handling editing and tab completion.
        Returns the finished line once the user presses enter.
        """
        while True:
            key = sys.stdin.read(1) #read one char at a time

            if key == '\n':
                self.clear_candidates()
                sys.stdout.write(key)
                sys.stdout.flush()
                return "".join(self.buffer)

            if key == '\t':
                self.handle_tab()
                continue

            #any non-tab key cancels in-progress completion cycle
            self.tab_cursor = None

            if key == '\x7f':
                self.handle_backspace()
                continue

            self.add_key(key) # any other character typed normally

    def add_key(self, key: str) -> None:
        """
        Echoes a typed character to the terminal and appends it to the buffer.
        """
        sys.stdout.write(key)
        sys.stdout.flush()
        self.buffer.append(key)

    def display_candidates(self, lines: list[str]) -> None:
        """
        Prints candidate lines below the prompt without disturbing the cursor.
        Restores the cursor to its original position after drawing them.
        """
        column = len(self.buffer) + 3 # "$ " (2 cols) + buffer, 1-indexed, just past the last typed char

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
        if not self.candidate_lines: #lines == 0
            return

        for _ in range(self.candidate_lines):
            sys.stdout.write("\033[B") #move down
            sys.stdout.write("\033[2K") #erase

        sys.stdout.write(f"\033[{self.candidate_lines}A\r")
        sys.stdout.flush()

        self.candidate_lines = 0

    def handle_tab(self) -> None:
        """
        Advances the tab-completion state machine for the current buffer.
        Lists candidates on first ambiguous tab, then cycles through them.
        """
        prefix = "".join(self.buffer)
        #TODO: print tab for empty buffer
        if not prefix:
            bell()
            return

        if self.tab_cursor is None:
            candidates = get_candidates(self.choices, prefix)
            if not candidates:
                bell()
                return
            self.tab_cursor = CandidateCursor(candidates)
            bell()

        cursor = self.tab_cursor
        if not cursor.listed and len(cursor.candidates) > 1:
            self.display_candidates(format_candidates(cursor.candidates))
            cursor.listed = True
        else:
            self.complete(cursor.next())

    def complete(self, candidate: str) -> None:
        """
        Replaces the current buffer with the chosen completion candidate.
        Redraws the prompt line to reflect the new buffer contents.
        """
        redraw(candidate)
        self.buffer.clear()
        self.buffer.extend(candidate)

    def handle_backspace(self) -> None:
        """
        Removes the last character from the buffer and erases it on screen.
        Does nothing if the buffer is already empty.
        """
        if self.buffer:
            self.buffer.pop()
            sys.stdout.write("\b \b")
            sys.stdout.flush()
