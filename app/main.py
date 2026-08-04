import sys
import tty
import termios

from app.errors import BuiltinError, ParseError
from app.executor import handle_command
from app.lexer import Lexer
from app.parser import parse

from app.shell_builtins import BUILTINS

BUILTINS = sorted(BUILTINS)

#TODO: replace with bisect later
def find_insertion_point(prefix: str):
    l, r = 0, len(BUILTINS)

    while l < r:
        mid = (l + r) // 2

        if BUILTINS[mid] < prefix:
            l = mid + 1
        else:
            r = mid 

    return l

def get_candidates(prefix: str) -> list[str]:

    start = find_insertion_point(prefix)
    candidates = []

    while start < len(BUILTINS) and BUILTINS[start].startswith(prefix):
        candidates.append(BUILTINS[start])
        start += 1

    return candidates

def redraw(output: str) -> None:

    sys.stdout.write("\r\033[2K") #clear line
    sys.stdout.write(f"$ {output}")
    sys.stdout.flush()

def autocomplete(buffer: list[str]) -> list[str]:

    candidates = get_candidates("".join(buffer))

    if candidates:
        buffer.clear()
        buffer.append(candidates[0])
        redraw(candidates[0])
    else:
        sys.stdout.write('\x07') #bell sound
        sys.stdout.flush()

    return buffer

def line_editor():
    #TODO: turn into context manager
    fd = sys.stdin.fileno()
    old_settings = tty.setcbreak(fd)
    buffer = []
    try:
        
        while True:

            char = sys.stdin.read(1) #read one character at a time

            sys.stdout.write(char)
            sys.stdout.flush()

            if char == '\n':
                return "".join(buffer)

            #tab character
            if char == '\t':
                buffer = autocomplete(buffer)
                continue

            buffer.append(char)
                    
    finally:
        termios.tcsetattr(fd, termios.TCSAFLUSH, old_settings)

def main():
    """
    Runs the interactive shell loop that reads and processes user commands.
    Continuously prompts the user for input until the exit command is received.
    """
         

    while True:
        sys.stdout.write("$ ")
        sys.stdout.flush()

        #line = input()

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
