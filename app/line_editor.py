import sys
import subprocess

import os


from app.tab_completion import CandidateCursor, format_candidates, get_candidates, get_path_candidates, longest_common_prefix, bell

def redraw(output: str, prefix: str) -> None:
    """
    Erases the last len(prefix) characters before the cursor and writes output in their place.
    """

    if prefix: #a 0-length move is still interpreted as 1 by terminals, so skip it
        sys.stdout.write(f"\033[{len(prefix)}D") #move cursor to before prefix
    sys.stdout.write("\033[0K") #erase from cursor to end of line
    sys.stdout.write(f"{output}")
    sys.stdout.flush()


class LineEditor:

    def __init__(self, choices: list[str], paths: MappingProxyType) -> None:
        """
        Sets up an empty input buffer and stores the known completion choices.
        """
        self.buffer = []
        self.tab_cursor = None
        self.choices = choices
        self.candidate_lines = 0
        self.paths = paths

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
        """
        #TODO: print tab for empty buffer
        if not self.buffer:
            bell()
            return

        if self.tab_cursor is None:
            if not self.start_completion(): # builds candidates for the current word; return if no candidates
                return
            if self.extend_to_lcp(self.tab_cursor): # extends to longest prefix if True, skip list/cycle
                return
            bell()

        self.list_or_cycle(self.tab_cursor) # lists candidates once, then cycles through them

    def run_completer_script(self, command: str) -> list[str]:
        """
        Runs the registered completer script for a command and returns its output lines.
        Returns an empty list if no completer is registered for the command.
        """
        if command not in self.paths:
            return None
        
        path = self.paths[command]
        os.chmod(path, os.stat(path).st_mode | 0o111) # make path executable for testing purposes
        output = subprocess.run([path], capture_output=True, text=True)
        return output.stdout.splitlines()

    def start_completion(self) -> bool:
        """
        Gathers candidates for the word under the cursor and starts a new
        CandidateCursor for them. Returns False if there's nothing to complete.
        """
        prefix = "".join(self.buffer)
        command, sep, prefix = prefix.rpartition(" ")
        if sep: #if there is a space
            candidates = self.run_completer_script(command)
            if candidates is None: #if no completer script, try and find path
                prefix, candidates = get_path_candidates(prefix)
        else:
            candidates = get_candidates(self.choices, prefix)

        if not candidates:
            bell()
            return False

        self.tab_cursor = CandidateCursor(candidates, prefix)
        return True

    def extend_to_lcp(self, cursor: CandidateCursor) -> bool:
        """
        Fills in the longest text shared by every candidate, if it's more
        than what's already typed. Rings the bell if candidates are still
        ambiguous after extending.
        """
        lcp = longest_common_prefix(cursor.candidates)
        if len(lcp) <= len(cursor.prefix):
            return False

        self.replace_current(cursor, lcp)
        if len(cursor.candidates) > 1:
            bell()
        return True

    def list_or_cycle(self, cursor: CandidateCursor) -> None:
        """
        Lists all candidates the first time they're still ambiguous,
        then cycles through them one at a time on every press after that.
        """
        if not cursor.listed and len(cursor.candidates) > 1:

            if self.candidate_lines: #if anything from before displayed, clear it
                self.clear_candidates()

            self.display_candidates(format_candidates(cursor.candidates))
            cursor.listed = True
        else:
            self.complete(cursor)

    def complete(self, cursor: CandidateCursor) -> None:
        """
        Swaps the cursor's currently displayed word for its next candidate,
        on screen and in the buffer.
        """
        self.replace_current(cursor, cursor.next())

    def replace_current(self, cursor: CandidateCursor, candidate: str) -> None:
        """
        Replaces the current completion prefix with the given candidate.
        Updates both the terminal display and the input buffer accordingly.
        """
        redraw(candidate, cursor.prefix)

        if cursor.prefix:
            del self.buffer[-len(cursor.prefix):] #delete prefix from buffer

        self.buffer.extend(candidate)
        cursor.prefix = candidate

    def handle_backspace(self) -> None:
        """
        Removes the last character from the buffer and erases it on screen.
        Does nothing if the buffer is already empty.
        """
        if self.buffer:
            self.buffer.pop()
            sys.stdout.write("\b \b")
            sys.stdout.flush()
