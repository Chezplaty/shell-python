from app.lexer import Token, TokenType
from collections import namedtuple
from app.errors import ParseError

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

        elif token.type in {
            TokenType.REDIRECT_STDOUT,
            TokenType.REDIRECT_STDERR,
            TokenType.APPEND_STDOUT,
            TokenType.APPEND_STDERR
        }:
            redirect, i = parse_overwrite(tokens, i)
            redirects.append(redirect)

        i += 1
        
    return Instruction(cmd, args, redirects)
            

