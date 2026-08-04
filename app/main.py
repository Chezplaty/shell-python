import sys

from app.errors import BuiltinError, ParseError
from app.executor import handle_command
from app.lexer import Lexer
from app.line_editor import LineEditor
from app.parser import parse

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

    while True:
        with set_cbreak_mode():

            sys.stdout.write("$ ")
            sys.stdout.flush()

            line = LineEditor().run()
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
            handle_command(instruction)
        except BuiltinError as e:
            print(e)

if __name__ == "__main__":
    main()
