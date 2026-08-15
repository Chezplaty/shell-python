from app.lexer import Token, TokenType
from collections import namedtuple
from app.errors import ParseError

class Instruction:

    def __init__(self, cmd: str, args: list[str], redirects: list[(Redirect)], run_bg: bool):
        self.cmd = cmd
        self.args = args
        self.redirects = redirects
        self.run_bg = run_bg

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
    if not tokens:
        return Instruction("", [], [], False)

    run_bg = tokens[-1].value == '&' #check if last token is &
    end = len(tokens) - 1 if run_bg else len(tokens)

    cmd = tokens[0].value
    args = []
    redirects = []
    i = 1 

    while i < end:
        token = tokens[i]

        if token.type == TokenType.WORD:
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

    return Instruction(cmd, args, redirects, run_bg)
            

