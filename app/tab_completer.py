from types import MappingProxyType

from app.tab_completion import CandidateCursor, format_candidates, get_candidates, get_path_candidates, longest_common_prefix, bell
from app.completer_runner import run_completer_script
from app.edit_buffer import EditBuffer
from app.display import Display


class TabCompleter:

    def __init__(self, choices: list[str], paths: MappingProxyType, edit_buffer: EditBuffer, display: Display) -> None:
        """
        Stores the known completion choices and the collaborators needed to
        read the current word and redraw the screen during completion.
        """
        self.choices = choices
        self.paths = paths
        self.edit_buffer = edit_buffer
        self.display = display
        self.tab_cursor = None

    def cancel(self) -> None:
        """
        Cancels any in-progress completion cycle.
        """
        self.tab_cursor = None

    def handle_tab(self) -> None:
        """
        Advances the tab-completion state machine for the current buffer.
        """
        # TODO: print tab for empty buffer
        if not self.edit_buffer.buffer:
            bell()
            return

        if self.tab_cursor is None:
            if not self.start_completion(): # builds candidates for the current word; return if no candidates
                return
            if self.extend_to_lcp(self.tab_cursor): # extends to longest prefix, if True, skip list/cycle
                return
            bell()

        self.list_or_cycle(self.tab_cursor) # lists candidates once, then cycles through them

    def start_completion(self) -> bool:
        """
        Gathers candidates for the word under the cursor and starts a new
        CandidateCursor for them. Returns False if there's nothing to complete.
        """
        input = self.edit_buffer.text()
        command, sep, remainder = input.partition(" ")

        if sep: # if there is a space
            args = remainder.split()
            prefix = args[-1] if args else ""

            comp_point = len(input[:self.edit_buffer.cursor_pos].encode()) # byte index of cursor position
            candidates = run_completer_script(self.paths, command, args, input, comp_point)

            if candidates is None: # if no completer script, try and find path
                prefix, candidates = get_path_candidates(prefix)
        else:
            prefix = input
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

            if self.display.candidate_lines: # if anything from before displayed, clear it
                self.display.clear_candidates()

            self.display.display_candidates(format_candidates(cursor.candidates), len(self.edit_buffer))
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
        self.display.redraw(candidate, cursor.prefix)
        self.edit_buffer.replace_suffix(len(cursor.prefix), candidate)
        cursor.prefix = candidate
