import sys
import os
from pathlib import Path
import math
import shutil

from app.shell_builtins import BUILTINS

class CandidateCursor:
    """Cycles through tab-completion candidates for a single prefix."""

    def __init__(self, candidates: list[str]):
        """
        Stores the candidate list and starts cycling from the first entry.
        """
        self.candidates = candidates
        self.index = 0
        self.listed = False #whether the full candidate list has already been shown

    def next(self) -> str:
        """
        Returns the current candidate and advances to the next one, wrapping around.
        """
        candidate = self.candidates[self.index]
        self.index = (self.index + 1) % len(self.candidates) #wrap around
        return candidate

def get_terminal_width() -> int:
    """
    Returns the current terminal width in columns, falling back to 80 if unknown.
    """
    return shutil.get_terminal_size(fallback=(80, 24)).columns

def format_candidates(candidates: list[str]):
    """
    Lays out candidates into column-major rows sized to fit the terminal width.
    Returns a list of formatted lines ready to print beneath the prompt.
    """

    column_width = max(map(len, candidates)) + 2
    columns = max(1, get_terminal_width()//column_width) # 1 in case terminal width smaller than column
    rows = math.ceil(len(candidates) / columns)

    lines = []
    for row in range(rows):
        line = []

        for col in range(columns):
            index = col * rows + row #column-major: fill down each column before moving right
            if index < len(candidates):
                line.append(candidates[index].ljust(column_width))

        lines.append("".join(line).rstrip())

    return lines

def compile_choices() -> list[str]:
    """
    Builds a sorted list of command names available for autocompletion.
    Combines executables from PATH with the shell's builtin commands.
    """
    choices = set()
    for directory in map(Path, os.get_exec_path()): #splits directories in PATH var
        try:
            for entry in directory.iterdir():
                if entry.is_file() and os.access(entry, os.X_OK):
                    choices.add(entry.name)
        except OSError: #skip unreadable directories/files
            pass

    choices.update(BUILTINS) #add builtins
    return sorted(choices)

#TODO: replace with bisect later
def find_insertion_point(choices: list[str], prefix: str) -> int:
    """
    Finds the index where a prefix should be inserted in a sorted list.
    Returns the first index containing a value greater than or equal to the prefix.
    """

    l, r = 0, len(choices)

    while l < r:
        mid = (l + r) // 2

        if choices[mid] < prefix:
            l = mid + 1
        else:
            r = mid

    return l

def get_candidates(choices: list[str], prefix: str) -> list[str]:
    """
    Finds all sorted entries that begin with the given prefix.
    Returns a list of possible autocomplete matches.
    """

    start = find_insertion_point(choices, prefix)
    candidates = []

    while start < len(choices) and choices[start].startswith(prefix):
        candidates.append(choices[start])
        start += 1

    return candidates

def redraw(output: str) -> None:
    """
    Clears the current terminal line and redraws the shell prompt.
    Displays the provided output after the prompt symbol.
    """

    sys.stdout.write("\r\033[2K") #clear line
    sys.stdout.write(f"$ {output}")
    sys.stdout.flush()

def bell() -> None:
    """
    Rings the terminal bell to signal an invalid or ambiguous completion.
    """
    sys.stdout.write('\x07') #bell sound
    sys.stdout.flush()


class LineEditor:

    def __init__(self, choices: list[str]):
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
            
    def add_key(self, key: str):
        """
        Echoes a typed character to the terminal and appends it to the buffer.
        """
        sys.stdout.write(key)
        sys.stdout.flush()
        self.buffer.append(key)

    def display_candidates(self, lines: list[str]):
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

    def clear_candidates(self):
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

    def handle_tab(self):
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

    def complete(self, candidate: str):
        """
        Replaces the current buffer with the chosen completion candidate.
        Redraws the prompt line to reflect the new buffer contents.
        """
        redraw(candidate)
        self.buffer.clear()
        self.buffer.extend(candidate)

    def handle_backspace(self):
        """
        Removes the last character from the buffer and erases it on screen.
        Does nothing if the buffer is already empty.
        """
        if self.buffer:
            self.buffer.pop()
            sys.stdout.write("\b \b")
            sys.stdout.flush()