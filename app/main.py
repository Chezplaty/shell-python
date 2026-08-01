import sys

from app.executor import handle_command
from enum import Enum

class ParseState(Enum):
    NORMAL = 1
    SINGLE = 2
    DOUBLE = 3
    BACKSLASH = 4

def finish_token(tokens: list[str], current: list[str]) -> None:
    """
    Finalizes the current token by appending it to the token list if it is non-empty.
    Clears the current token buffer so parsing can continue with the next token.
    """

    if current:
        tokens.append("".join(current))
        current.clear()

def parse_command(line: str) -> list[str]:

    tokens = []
    current = []
    state = ParseState.NORMAL
    
    for char in line:

        #separate characters by space only
        if state == ParseState.NORMAL:

            if char.isspace():
                finish_token(tokens, current)

            elif char == "'":
                state = ParseState.SINGLE

            elif char == '"':
                state = ParseState.DOUBLE

            elif char == "\\": #checks for single backslash
                state = ParseState.BACKSLASH

            else:
                current.append(char)
            
        elif state == ParseState.SINGLE:

            if char == "'":
                finish_token(tokens, current)
                state = ParseState.NORMAL

            else:
                current.append(char)

        #TODO: handle special character exceptions
        elif state == ParseState.DOUBLE:
        
            if char == '"':
                finish_token(tokens, current)
                state = ParseState.NORMAL
        
            else:
                current.append(char)

        elif state == ParseState.BACKSLASH:
            current.append(char)
            state = ParseState.NORMAL

    #check for leftover token
    finish_token(tokens, current)

    return tokens

def main():
    """
    Runs the interactive shell loop that reads and processes user commands.
    Continuously prompts the user for input until the exit command is received.
    """

    while True:
        sys.stdout.write("$ ")

        line = input()

        parts = parse_command(line)

        cmd = parts[0]
        args = parts[1:] if len(parts) > 1 else []

        if cmd == "exit":
            break

        handle_command(cmd, args)

if __name__ == "__main__":
    main()
