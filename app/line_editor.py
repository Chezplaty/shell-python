import sys
import tty
import termios

from app.shell_builtins import BUILTINS

BUILTINS = sorted(BUILTINS)


class CandidateCursor:

    def __init__(self, candidates: list[str]):
        self.candidates = candidates
        self.index = 0

    def next(self) -> str:
        candidate = self.candidates[self.index]
        self.index = (self.index + 1) % len(self.candidates) #wrap around
        return candidate

#TODO: replace with bisect later
def find_insertion_point(prefix: str) -> int:
    """
    Finds the index where a prefix should be inserted in a sorted list.
    Returns the first index containing a value greater than or equal to the prefix.
    """

    l, r = 0, len(BUILTINS)

    while l < r:
        mid = (l + r) // 2

        if BUILTINS[mid] < prefix:
            l = mid + 1
        else:
            r = mid

    return l

def get_candidates(prefix: str) -> list[str]:
    """
    Finds all sorted entries that begin with the given prefix.
    Returns a list of possible autocomplete matches.
    """

    start = find_insertion_point(prefix)
    candidates = []

    while start < len(BUILTINS) and BUILTINS[start].startswith(prefix):
        candidates.append(BUILTINS[start])
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
    sys.stdout.write('\x07') #bell sound
    sys.stdout.flush()


class LineEditor:

    def __init__(self):
        self.buffer = []
        self.tab_cursor = None

    def run(self) -> str:
        while True:
            key = sys.stdin.read(1) #read one char at a time

            if key not in {'\t', '\x7f'}:
                self.add_key(key)

            if key == '\n':
                return "".join(self.buffer)

            if key == '\t':
                self.handle_tab()
                continue

            self.tab_cursor = None
            if key == '\x7f':
                self.handle_backspace()

    def add_key(self, key: str):
        sys.stdout.write(key)
        sys.stdout.flush()
        self.buffer.append(key)

    def handle_tab(self):
        prefix = "".join(self.buffer)
        if not prefix:
            bell()
            return
        
        if self.tab_cursor is None:
            candidates = get_candidates(prefix)
            if candidates:
                self.tab_cursor = CandidateCursor(candidates)
            else: #no candidates found
                bell()
                return

        candidate = self.tab_cursor.next()
        redraw(candidate)
        self.buffer.clear()
        self.buffer.extend(candidate)

    def handle_backspace(self):
        if self.buffer:
            self.buffer.pop()
            sys.stdout.write("\b \b")
            sys.stdout.flush()