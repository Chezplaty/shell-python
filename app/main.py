import sys

from app.errors import BuiltinError, ParseError
from app.executor import handle_command
from app.lexer import Lexer
from app.line_editor import LineEditor
from app.parser import parse

import tty
import termios

def main():
    """
    Runs the interactive shell loop that reads and processes user commands.
    Continuously prompts the user for input until the exit command is received.
    """

    #TODO: only returning an empty line gives an error
    try:

        while True:
            #set cbreak
            fd = sys.stdin.fileno()
            old_settings = tty.setcbreak(fd)

            sys.stdout.write("$ ")
            sys.stdout.flush()

            line = LineEditor().run()

            if not line.strip(): #empty input
                continue
            
            #restore after getting line
            termios.tcsetattr(fd, termios.TCSAFLUSH, old_settings)

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

    finally:
        termios.tcsetattr(fd, termios.TCSAFLUSH, old_settings)

if __name__ == "__main__":
    main()
