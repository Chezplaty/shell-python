import sys
import select
import os


from app.edit_buffer import EditBuffer
from app.display import Display
from app.tab_completer import TabCompleter

#TODO: since cursor can move left and right, it can delete inside words, add support for that
class LineEditor:

    def __init__(self, choices: list[str], paths: MappingProxyType, read_fd: 'fd', job_man: JobsManager) -> None:
        """
        Sets up the buffer, terminal display, and tab completer, and stores the read fd and job manager.
        """
        self.edit_buffer = EditBuffer()
        self.display = Display()
        self.tab_completer = TabCompleter(choices, paths, self.edit_buffer, self.display)
        self.read_fd = read_fd
        self.job_man = job_man

    def run(self) -> str:
        """
        Reads keystrokes one at a time, handling editing and tab completion.
        Returns the finished line once the user presses enter.
        """
        self.display.display_prompt()

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
                self.display.clear_candidates()
                sys.stdout.write(key)
                sys.stdout.flush()
                return self.edit_buffer.text()

            if key == '\t':
                self.tab_completer.handle_tab()
                continue

            # any non-tab key cancels in-progress completion cycle
            self.tab_completer.cancel()

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
            self.print_job_and_redisplay(pid)
            self.job_man.remove_job(pid)

    def print_job_and_redisplay(self, pid: int) -> None:
        """
        Prints a completed job notification and redraws the current command line.
        """
        text = self.job_man.format_print_text(pid)
        self.display.show_job_notice(text, self.edit_buffer.text(), self.edit_buffer.cursor_pos)

    # -------------------------------------------------------------------------
    # Input handling
    # -------------------------------------------------------------------------

    def add_key(self, key: str) -> None:
        """
        Echoes a typed character to the terminal and appends it to the buffer.
        """
        self.edit_buffer.insert(key)
        self.display.echo(key)

    def handle_backspace(self) -> None:
        """
        Removes the last character from the buffer and erases it on screen.
        Does nothing if the buffer is already empty.
        """
        if self.edit_buffer.backspace():
            self.display.erase_last()

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
            moved = self.edit_buffer.move_left()
        else: #right
            moved = self.edit_buffer.move_right()

        if moved:
            self.display.move_cursor(sequence)
