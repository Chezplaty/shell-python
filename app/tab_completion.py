import sys
import os
from pathlib import Path
import math
import shutil
import shlex

from app.shell_builtins import BUILTINS

class CandidateCursor:
    """Cycles through tab-completion candidates for a single prefix."""

    def __init__(self, candidates: list[str], prefix: str):
        """
        Stores the candidates and the text currently shown on screen for this word,
        and starts cycling from the first entry.
        """
        self.candidates = candidates
        self.prefix = prefix
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

def format_candidates(candidates: list[str]) -> list[str]:
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

def get_path_candidates(prefix: str) -> tuple[str, list[str]]:
    """
    Returns files and directories starting with the given prefix's final path segment.
    Also returns the (possibly narrowed) prefix, since completion only ever replaces that final segment.
    """

    #TODO: if prefix is empty, list all the directories in the cwd
    if not prefix:
        return prefix, []


    path = Path(prefix)
    loc, prefix = path.parent, path.name

    paths = []

    try:
        for entry in loc.iterdir():
            if entry.exists() and entry.name.startswith(prefix):
                name = shlex.quote(entry.name)
                if entry.is_dir():
                    name += '/'
                paths.append(name)
    except OSError: # loc is not a direc or cant be accessed
        pass
    return prefix, paths #prefix might change, return it


def bell() -> None:
    """
    Rings the terminal bell to signal an invalid or ambiguous completion.
    """
    sys.stdout.write('\x07') #bell sound
    sys.stdout.flush()
