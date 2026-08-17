import sys
import subprocess
import select
import os


from app.tab_completion import CandidateCursor, format_candidates, get_candidates, get_path_candidates, longest_common_prefix, bell

#TODO: split some methods into separate modules
#TODO: since cursor can move left and right, it can delete inside words, add support for that
class LineEditor:

    # -------------------------------------------------------------------------
    # Lifecycle / main loop
    # -------------------------------------------------------------------------

    def __init__(self, choices: list[str], paths: MappingProxyType, read_fd: 'fd', job_man: JobsManager) -> None:
        """
        Sets up an empty input buffer and stores the known completion choices.
        """
        self.buffer = []
        self.choices = choices
        self.candidate_lines = 0
        self.cursor_pos = 0
        self.tab_cursor = None
        self.paths = paths
        self.read_fd = read_fd
        self.job_man = job_man

    def run(self) -> str:
        """
        Reads keystrokes one at a time, handling editing and tab completion.
        Returns the finished line once the user presses enter.
        """
        while True:

            #wait for input in stdin or read_fd
            ready, _, _ = select.select([sys.stdin, self.read_fd], [], [])

            if self.read_fd in ready:
                os.read(self.read_fd, 1024) #consume at most 1024 bytes in buffer
                self.process_background_job()
                continue


            if sys.stdin in ready:
                key = sys.stdin.read(1) # read one char at a time

            if key == '\n':
                self.clear_candidates()
                sys.stdout.write(key)
                sys.stdout.flush()
                return "".join(self.buffer)

            if key == '\t':
                self.handle_tab()
                continue

            # any non-tab key cancels in-progress completion cycle
            self.tab_cursor = None

            if key == '\x7f':
                self.handle_backspace()
                continue

            if key == '\x1b': #esc character, start of many terminal esc sequences
                self.handle_escape()
                continue

            self.add_key(key) # any other character typed normally

    # -------------------------------------------------------------------------
    # Background jobs
    # -------------------------------------------------------------------------

    def process_background_job(self) -> None:
        """
        Processes completed background jobs and displays their status.
        Removes each completed job after redisplaying the current input line.
        """
        for pid in self.job_man.get_completed_jobs():
            job = self.job_man.get_job(pid)
            self.job_man.remove_job(pid)
            self.print_job_and_redisplay(job)

    # -------------------------------------------------------------------------
    # Input handling
    # -------------------------------------------------------------------------

    def add_key(self, key: str) -> None:
        """
        Echoes a typed character to the terminal and appends it to the buffer.
        """
        self.cursor_pos += 1
        sys.stdout.write(key)
        sys.stdout.flush()
        self.buffer.append(key)

    def handle_backspace(self) -> None:
        """
        Removes the last character from the buffer and erases it on screen.
        Does nothing if the buffer is already empty.
        """
        if self.buffer:
            self.cursor_pos -= 1
            self.buffer.pop()
            sys.stdout.write("\b \b")
            sys.stdout.flush()

    def handle_escape(self) -> None:
        """
        Reads and handles escape sequences for special keys.
        """
        sequence = sys.stdin.read(2) #read in 2 bytes, arrow keys are 3 bytes including esc

        if sequence in {'[D', '[C'}:
            self.handle_arrow_keys(sequence)

    def handle_arrow_keys(self, sequence: str) -> None:
        """
        Moves the cursor left or right based on the given arrow-key sequence.
        Ignores movement that would place the cursor outside the input buffer.
        """

        if sequence == '[D': #left
            if self.cursor_pos > 0:
                self.cursor_pos -= 1
                sys.stdout.write("\033[D")
                sys.stdout.flush()

        elif sequence == '[C': #right
            if self.cursor_pos < len(self.buffer):
                self.cursor_pos += 1
                sys.stdout.write("\033[C")
                sys.stdout.flush()

    # -------------------------------------------------------------------------
    # Tab completion
    # -------------------------------------------------------------------------

    def handle_tab(self) -> None:
        """
        Advances the tab-completion state machine for the current buffer.
        """
        # TODO: print tab for empty buffer
        if not self.buffer:
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
        input = "".join(self.buffer)
        command, sep, remainder = input.partition(" ")

        if sep: # if there is a space
            args = remainder.split()
            prefix = args[-1] if args else ""

            # TODO: implement comp_line and comp_pos. create cursor tracker
            candidates = self.run_completer_script(command, args, input)

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

            if self.candidate_lines: # if anything from before displayed, clear it
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

    # -------------------------------------------------------------------------
    # Buffer / completion replacement
    # -------------------------------------------------------------------------

    def replace_current(self, cursor: CandidateCursor, candidate: str) -> None:
        """
        Replaces the current completion prefix with the given candidate.
        Updates both the terminal display and the input buffer accordingly.
        """
        self.redraw(candidate, cursor.prefix)

        if cursor.prefix:
            del self.buffer[-len(cursor.prefix):] # delete prefix from buffer

        self.buffer.extend(candidate)
        cursor.prefix = candidate

    # -------------------------------------------------------------------------
    # Terminal display
    # -------------------------------------------------------------------------

    def print_job_and_redisplay(self, job: Job) -> None:
        """
        Prints a completed job notification and redraws the current command line.
        Restores the cursor to its previous position after displaying the notification.
        """
        sys.stdout.write('\r\n')

        line = job.instruction.cmd + " ".join(job.instruction.args)
        sys.stdout.write(f"[{job.job_num}] + {job.status:<10}{line}\n")

        sys.stdout.write("$ ")
        sys.stdout.write(''.join(self.buffer))
        sys.stdout.write(f"\033[{self.cursor_pos + 3}G")
        sys.stdout.flush()

    def redraw(self, output: str, prefix: str) -> None:
        """
        Erases the last len(prefix) characters before the cursor and writes output in their place.
        """

        if prefix: # a 0-length move is still interpreted as 1 by terminals, so skip it
            sys.stdout.write(f"\033[{len(prefix)}D") # move cursor to before prefix
            self.cursor_pos -= len(prefix)

        sys.stdout.write("\033[0K") # erase from cursor to end of line
        sys.stdout.write(f"{output}")
        self.cursor_pos += len(output)
        sys.stdout.flush()

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
        if not self.candidate_lines: # lines == 0
            return

        for _ in range(self.candidate_lines):
            sys.stdout.write("\033[B") # move down
            sys.stdout.write("\033[2K") # erase

        sys.stdout.write(f"\033[{self.candidate_lines}A\r")
        sys.stdout.flush()

        self.candidate_lines = 0

    # -------------------------------------------------------------------------
    # Completer process
    # -------------------------------------------------------------------------

    def run_completer_script(self, command: str, args: list[str], comp_line: str) -> list[str] | None:
        """
        Runs the registered completer script with command arguments and completion environment.
        Returns a list of the script's output lines, or None if no completer is registered.
        """

        if command not in self.paths:
            return None

        env_copy = os.environ.copy()
        env_copy["COMP_LINE"] = comp_line
        env_copy["COMP_POINT"] = str(len(comp_line[:self.cursor_pos].encode())) # byte index of cursor position

        path = self.paths[command]
        os.chmod(path, os.stat(path).st_mode | 0o111) # make path executable for testing purposes
        #TODO: implement error handling when path cannot be run
        output = subprocess.run([path, *args], env=env_copy, capture_output=True, text=True)
        return output.stdout.splitlines()
