import sys

from app.errors import BuiltinError, ParseError
from app.executor import handle_command
from app.lexer import Lexer
from app.line_editor import line_editor
from app.parser import parse

def main():
    """
    Runs the interactive shell loop that reads and processes user commands.
    Continuously prompts the user for input until the exit command is received.
    """
         

    while True:
        sys.stdout.write("$ ")
        sys.stdout.flush()

        line = line_editor()

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
