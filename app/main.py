import sys

from app.executor import handle_command
from app.lexer import Lexer

def main():
    """
    Runs the interactive shell loop that reads and processes user commands.
    Continuously prompts the user for input until the exit command is received.
    """

    while True:
        sys.stdout.write("$ ")

        line = input()

        parts = Lexer().tokenize(line)

        cmd = parts[0]
        args = parts[1:] if len(parts) > 1 else []

        if cmd == "exit":
            break

        handle_command(cmd, args)

if __name__ == "__main__":
    main()
