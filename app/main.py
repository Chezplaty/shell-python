import sys
from app.errors import BuiltinError, ParseError
from app.executor import handle_command
from app.lexer import Lexer
from app.parser import parse

import tty
import termios

def main():
    """
    Runs the interactive shell loop that reads and processes user commands.
    Continuously prompts the user for input until the exit command is received.
    """
    fd = sys.stdin.fileno()
    old_settings = tty.setcbreak(fd)

    
    try:
        while True:
            sys.stdout.write("$ ")
            sys.stdout.flush() 

            char = sys.stdin.read(1)#read one character at a time
            print(char)

            if char == 'q':
                break
    finally:
        termios.tcsetattr(fd, termios.TCSAFLUSH, old_settings)
         

    # while True:
    #     sys.stdout.write("$ ")

    #     #TODO: implement tab autocompletion

        
    #     #fd = sys.stdin.fileno()
    #     #old_settings = tty.setcbreak(fd) #set stdin into cbreak mode



    #     line = input()

    #     tokens = Lexer().tokenize(line)

    #     try:
    #         instruction = parse(tokens)
    #     except ParseError as e:
    #         print(f"shell: {e}")
    #         continue

    #     if instruction.cmd == "exit":
    #         break

    #     try:
    #         handle_command(instruction)
    #     except BuiltinError as e:
    #         print(e)

if __name__ == "__main__":
    main()
