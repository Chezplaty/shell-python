from app.lexer import Token, TokenType
from collections import namedtuple
from app.errors import ParseError

class Instruction:

    def __init__(self, cmd: str, args: list[str], redirects: list[(Redirect)], run_bg: bool, pipe=False):
        self.cmd = cmd
        self.args = args
        self.redirects = redirects
        self.run_bg = run_bg
        self.has_pipe = pipe

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

def parse_pipe(tokens: list[Token], i: int) -> tuple[Redirect, int]:

    if i <= 0 or i + 1 >= len(tokens): #pipe cant be the first or last
        raise ParseError(f"parse error near '{tokens[i].value}'")

    source = tokens[i - 1]
    target = tokens[i + 1]
    if source.type != TokenType.WORD or target.type != TokenType.WORD:
        raise ParseError(f"parse error near '{tokens[i].value}'")

    return i + 1

#TODO: implement returning more than one Instruction, especially for pipes and chaining    
def parse(tokens: list[Token], var_manager: VarManager) -> list[Instruction] | None:
    if not tokens:
        return

    run_bg = tokens[-1].value == '&' #check if last token is &
    end = len(tokens) - 1 if run_bg else len(tokens)

    instructions = []
    cmd = None
    args = []
    redirects = []
    i = 0

    while i < end:
        token = tokens[i]

        if token.type == TokenType.PIPE:
            i = parse_pipe(tokens, i)
            instructions.append(Instruction(cmd, args, redirects, run_bg, pipe=True))

            #reset for next instruction
            cmd = None
            args = []
            redirects = []
            continue

        if cmd is None:
            cmd = token.value
            i += 1
            continue

        if token.type == TokenType.WORD: #check if there is a '$' in front
            arg = token.value
            if arg.startswith('$'):
                arg = expand_var(arg, var_manager)
            args.append(arg)

        elif token.type in {
            TokenType.REDIRECT_STDOUT,
            TokenType.REDIRECT_STDERR,
            TokenType.APPEND_STDOUT,
            TokenType.APPEND_STDERR
        }:
            redirect, i = parse_overwrite(tokens, i)
            redirects.append(redirect)

        i += 1

    instructions.append(Instruction(cmd, args, redirects, run_bg))
    return instructions
            
def expand_var(var: str, var_manager: VarManager) -> str:
    """
    Expand a variable reference using the provided variable manager.
    Returns the variable's value if defined, otherwise returns the original string.
    """

    if len(var) > 1:
        val = var_manager.get_var_val(var[1:])

    if val is not None:
        return val
    
    return var
