import sys
import os
import signal

from app.errors import BuiltinError, ParseError
from app.executor import run_instructions
from app.lexer import Lexer
from app.line_editor import LineEditor
from app.tab_completion import compile_choices
from app.parser import parse
from app.path_utils import get_histfile
from app.shell_builtins import (
    CompleteManager,
    HistoryManager,
    handle_cd,
    handle_echo,
    handle_pwd,
    handle_type
)
from app.jobs import JobsManager, make_sigchld_handler

from contextlib import contextmanager
import tty
import termios

@contextmanager
def set_cbreak_mode():
    """
    Temporarily switches stdin into cbreak mode for character-by-character input.
    Restores the original terminal settings when the context exits.
    """
    fd = sys.stdin.fileno()
    old_settings = tty.setcbreak(fd)

    try:
        yield 
    finally:
        termios.tcsetattr(fd, termios.TCSAFLUSH, old_settings)

def run_shell(history_manager: HistoryManager):
    """
    Runs the interactive shell loop that reads and processes user commands.
    Continuously prompts the user for input until the exit command is received.
    """

    choices = compile_choices()
    complete_manager = CompleteManager()
    jobs_manager = JobsManager()

    handler = make_sigchld_handler(jobs_manager)
    signal.signal(signal.SIGCHLD, handler)

    read_fd, write_fd = os.pipe() # create pipe to wake up line editor for signals
    os.set_blocking(write_fd, False) #make fd nonblocking
    signal.set_wakeup_fd(write_fd) # if SIGCHLD comes, write byte into this fd

    builtins = {"exit": None,
                "echo": handle_echo,
                "type": handle_type,
                "pwd": handle_pwd,
                "cd": handle_cd,
                "complete": complete_manager.handle_complete,
                "jobs": jobs_manager.handle_jobs,
                "history": history_manager.handle_history}

    while True:
        with set_cbreak_mode():

            line = LineEditor(choices, complete_manager.get_paths(), read_fd, jobs_manager, history_manager).run()
        #restore on exit

        if not line.strip(): 
            continue

        history_manager.add_line(line)

        tokens = Lexer().tokenize(line)

        try:
            instructions = parse(tokens)
        except ParseError as e:
            print(f"shell: {e}")
            continue

        if not instructions:
            continue

        if instructions[0].cmd == "exit":
            break

        try:
            run_instructions(instructions, jobs_manager, builtins)
        except BuiltinError as e:
            print(e)
            
if __name__ == "__main__":
    with HistoryManager() as hm:
        run_shell(hm)
