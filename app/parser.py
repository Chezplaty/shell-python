from enum import Enum

class ParseState(Enum):
    NORMAL = 1
    SINGLE = 2
    DOUBLE = 3

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
    escaping = False
    sp_chars = {'"', '\\', '$', '`', '\n'}
    state = ParseState.NORMAL

    for char in line:

        #separate characters by space only
        if state == ParseState.NORMAL:

            if escaping:
                current.append(char)
                escaping = False

            elif char.isspace():
                finish_token(tokens, current)

            elif char == "'":
                state = ParseState.SINGLE

            elif char == '"':
                state = ParseState.DOUBLE

            elif char == "\\":
                escaping = True

            else:
                current.append(char)

        elif state == ParseState.SINGLE:

            if char == "'":
                state = ParseState.NORMAL

            else:
                current.append(char)

        #TODO: handle special character exceptions
        elif state == ParseState.DOUBLE:

            if escaping:
                if char not in sp_chars:
                    current.append('\\')
                current.append(char)
                escaping = False

            elif char == '"':
                state = ParseState.NORMAL

            elif char == '\\':
                escaping = True

            else:
                current.append(char)

    #TODO: check if state is in NORMAL, keep prompting user if in quote mode
    finish_token(tokens, current)

    return tokens
