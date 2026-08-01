import sys

from app.executor import handle_command
from enum import Enum

class ParseState(Enum):
    NORMAL = 1
    SINGLE = 2
    DOUBLE = 3

def parse_command(line: str) -> list[str]:

    parts = []
    current = []
    state = ParseState.NORMAL
    
    for char in line:

        #separate characters by space only
        if state == ParseState.NORMAL:

            if char.isspace():
                if current:
                    parts.append("".join(current))
                    current = []

            elif char == "'":
                state = ParseState.SINGLE

            #TODO: implement Double state

            else:
                current.append(char)
            
        elif state == ParseState.SINGLE:

            if char == "'":
                if current:
                    parts.append("".join(current))
                    current = []
                state = ParseState.NORMAL

            else:
                current.append(char)

    if current:
        parts.append("".join(current))

    return parts

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
