import sys
import tty
import termios

from app.errors import BuiltinError, ParseError
from app.executor import handle_command
from app.lexer import Lexer
from app.parser import parse

from app.shell_builtins import BUILTINS

def line_editor():
    fd = sys.stdin.fileno()
    old_settings = tty.setcbreak(fd)
    buffer = []
    try:
        
        while True:

            char = sys.stdin.read(1)#read one character at a time

            sys.stdout.write(char)
            sys.stdout.flush()


            if char == '\n':
                return "".join(buffer)

            #tab character
            if char == '\t':
                #autocomplete function
                word = "".join(buffer)
                #search for prefix
                candidates = []
                for candidate in BUILTINS.keys():
                    if candidate.startswith(word):
                        candidates.append(candidate)

                if candidates:
                    sys.stdout.write("\r\033[2K")
                    sys.stdout.write(f"$ {candidates[0]}")
                    sys.stdout.flush()
                    buffer.clear()
                    buffer.append(candidates[0])
            else:
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

        #TODO: implement tab autocompletion

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
