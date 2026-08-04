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

# def autocomplete(buffer: list[str]) -> list[str]:
#     """
#     Replaces the current buffer with the first matching completion.
#     Emits a terminal bell when no completion candidates are found.
#     """

#     candidates = get_candidates("".join(buffer))

#     #choose candidate
#     cursor = CandidateCursor(candidates)

#     if candidates:
#         buffer.clear()
#         buffer.extend(candidates[0])
#         redraw(candidates[0])
#     else:
#         sys.stdout.write('\x07') #bell sound
#         sys.stdout.flush()

#     return buffer

def line_editor():
    #TODO: turn into context manager
    fd = sys.stdin.fileno()
    old_settings = tty.setcbreak(fd)
    buffer = []
    tab_cursor = None
    try:

        while True:

            key = sys.stdin.read(1) #read one character at a time

            if key == '\n':
                return "".join(buffer)

            #tab character
            if key == '\t':

                #has not pressed tab yet, get new candidates
                if tab_cursor is None:
                    candidates = get_candidates("".join(buffer))
                    if candidates:
                        tab_cursor = CandidateCursor(candidates)
                    else: #no candidates found
                        sys.stdout.write('\x07') #bell sound
                        sys.stdout.flush()
                        continue

                candidate = tab_cursor.next()
                redraw(candidate)
                buffer.clear()
                buffer.extend(candidate)
                continue

            tab_cursor = None

            if key == '\x7f':
                if buffer:
                    buffer.pop()
                    sys.stdout.write("\b \b")
                    sys.stdout.flush()
                continue

            sys.stdout.write(key)
            sys.stdout.flush()
            buffer.append(key)

    finally:
        termios.tcsetattr(fd, termios.TCSAFLUSH, old_settings)
