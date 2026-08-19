import sys
import os
import signal

from app.errors import BuiltinError, ParseError
from app.executor import handle_command
from app.lexer import Lexer
from app.line_editor import LineEditor
from app.tab_completion import compile_choices
from app.parser import parse
from app.shell_builtins import (
    CompleteManager,
    handle_cd,
    handle_echo,
    handle_pwd,
    handle_type
)
from app.jobs import JobsManager, make_sigchld_handler, fork_and_track

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

def main():
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
                "jobs": jobs_manager.handle_jobs}

    while True:
        with set_cbreak_mode():

            line = LineEditor(choices, complete_manager.get_paths(), read_fd, jobs_manager).run()
        #restore on exit

        if not line.strip(): 
            continue

        tokens = Lexer().tokenize(line)

        try:
            instruction = parse(tokens)
        except ParseError as e:
            print(f"shell: {e}")
            continue

        if instruction.cmd == "exit":
            break

        try:
            if instruction.run_bg:
                fork_and_track(jobs_manager, instruction, True, lambda: handle_command(instruction, builtins, jobs_manager))
            else:
                handle_command(instruction, builtins, jobs_manager)
        except BuiltinError as e:
            print(e)

if __name__ == "__main__":
    main()
