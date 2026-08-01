from app.lexer import Token, TokenType
from collections import namedtuple

"""
TODO: implement raising errors that are caught by main and printed out
class ParseError(Exception):
    def __init__(self, message: str):
        self.message = message

    def __str__(self):
        return f"shell: {self.message}"
"""

class Instruction:

    def __init__(self, cmd: str, args: list[str], redirects: list[(Redirect)]):
        self.cmd = cmd
        self.args = args
        self.redirects = redirects

Redirect = namedtuple('Redirect', ['type', 'target'])

def parse(tokens: list[Token]) -> Instruction:

    cmd = ""
    args = []
    redirects = []
    i = 0 

    while i < len(tokens):
        token = tokens[i]

        if i == 0:
            cmd = token.value

        elif token.type == TokenType.WORD:
            args.append(token.value)

        # > operator
        elif token.type == TokenType.OVERWRITE:
            if i + 1 >= len(tokens):
                print("shell: parse error near '\\n'")
                return

            if tokens[i + 1].type != TokenType.WORD:
                print(f"shell: parse error near '{tokens[i+1]}'")
                return

            redirects.append(Redirect(token.type, tokens[i+1].value))

            #skip over next token, already used
            i += 1

        i += 1
        
    return Instruction(cmd, args, redirects)
            

