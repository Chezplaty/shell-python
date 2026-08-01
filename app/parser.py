from app.lexer import Token, TokenType
from collections import namedtuple


#TODO: implement raising errors that are caught by main and printed out
class ParseError(Exception):
    def __init__(self, message: str):
        self.message = message

    def __str__(self):
        return self.message


class Instruction:

    def __init__(self, cmd: str, args: list[str], redirects: list[(Redirect)]):
        self.cmd = cmd
        self.args = args
        self.redirects = redirects

Redirect = namedtuple('Redirect', ['type', 'target'])


def parse_overwrite(tokens: list[Token], i: int) -> tuple[Redirect, int]:
    """
    Parses an output overwrite redirection and validates its target filename token.
    Returns the created redirect object and the index of the consumed target token.
    Raises a ParseError if the redirection is missing a valid filename target.
    """

    if i + 1 >= len(tokens):
        raise ParseError("parse error near '\\n'")

    target = tokens[i+1]
    
    if target.type != TokenType.WORD:
        raise ParseError(f"parse error near '{target.value}'")

    return Redirect(tokens[i].type, target.value), i + 1

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
            redirect, i = parse_overwrite(tokens, i)
            redirects.append(redirect)

        i += 1
        
    return Instruction(cmd, args, redirects)
            

