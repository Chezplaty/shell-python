import sys

from app.executor import handle_command
from app.lexer import Lexer
from app.parser import parse, ParseError



def main():
    """
    Runs the interactive shell loop that reads and processes user commands.
    Continuously prompts the user for input until the exit command is received.
    """

    while True:
        sys.stdout.write("$ ")

        line = input()

        tokens = Lexer().tokenize(line)

        try:
            instruction = parse(tokens)
        except ParseError as e:
            print(f"shell: {e}")
            continue
        
        if instruction.cmd == "exit":
            break

        handle_command(instruction)

if __name__ == "__main__":
    main()
