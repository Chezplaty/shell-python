import sys

from app.errors import BuiltinError, ParseError
from app.executor import handle_command
from app.lexer import Lexer
from app.line_editor import LineEditor
from app.tab_completion import compile_choices
from app.parser import parse
from app.shell_builtins import (
    CompleteManager,
    JobsManager,
    handle_cd,
    handle_echo,
    handle_pwd,
    handle_type
)

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

    builtins = {"exit": None,
                "echo": handle_echo,
                "type": handle_type,
                "pwd": handle_pwd,
                "cd": handle_cd,
                "complete": complete_manager.handle_complete,
                "jobs": jobs_manager.handle_jobs}

    while True:
        with set_cbreak_mode():

            sys.stdout.write("$ ")
            sys.stdout.flush()

            line = LineEditor(choices, complete_manager.get_paths()).run()
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
            handle_command(instruction, builtins)
        except BuiltinError as e:
            print(e)

if __name__ == "__main__":
    main()
