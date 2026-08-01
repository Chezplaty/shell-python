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

class Parser:

    #characters to escape in double quotes
    DOUBLE_ESCAPES = {'"', '\\', '$', '`', '\n'}

    def __init__(self):
        self._tokens = []
        self._current = []
        self._escaping = False
        self._state = ParseState.NORMAL

    def parse(self, line: str) -> list[str]:

        for char in line:
            if self._state == ParseState.NORMAL:
                self.handle_normal_parse(char)

            elif self._state == ParseState.SINGLE:
                self.handle_single_parse(char)

            elif self._state == ParseState.DOUBLE:
                self.handle_double_parse(char)

        finish_token(self._tokens, self._current)
        return self._tokens

    def turn_escape_off(self) -> None:
        self._escaping = False

    def handle_normal_parse(self, char: str) -> None:

        if self._escaping:
            self._current.append(char)
            self.turn_escape_off()

        elif char.isspace():
            finish_token(self._tokens, self._current)

        elif char == "'":
            self._state = ParseState.SINGLE

        elif char == '"':
            self._state = ParseState.DOUBLE

        elif char == '\\':
            self._escaping = True

        else:
            self._current.append(char)

    def handle_single_parse(self, char: str) -> None:

        if char == "'":
            self._state = ParseState.NORMAL
        
        else:
            self._current.append(char)

    #TODO: handle special character exceptions
    def handle_double_parse(self, char: str) -> None:

        if self._escaping:
            if char not in self.DOUBLE_ESCAPES:
                self._current.append('\\')
            self._current.append(char)
            self.turn_escape_off()

        elif char == '"':
            self._state = ParseState.NORMAL
        
        elif char == '\\':
            self._escaping = True
        
        else:
            self._current.append(char)

# def parse_command(line: str) -> list[str]:

#     tokens = []
#     current = []
#     escaping = False
#     sp_chars = {'"', '\\', '$', '`', '\n'}
#     state = ParseState.NORMAL

#     for char in line:

#         #separate characters by space only
#         if state == ParseState.NORMAL:

#             if escaping:
#                 current.append(char)
#                 escaping = False

#             elif char.isspace():
#                 finish_token(tokens, current)

#             elif char == "'":
#                 state = ParseState.SINGLE

#             elif char == '"':
#                 state = ParseState.DOUBLE

#             elif char == "\\":
#                 escaping = True

#             else:
#                 current.append(char)

#         elif state == ParseState.SINGLE:

#             if char == "'":
#                 state = ParseState.NORMAL

#             else:
#                 current.append(char)

#         #TODO: handle special character exceptions
#         elif state == ParseState.DOUBLE:

#             if escaping:
#                 if char not in sp_chars:
#                     current.append('\\')
#                 current.append(char)
#                 escaping = False

#             elif char == '"':
#                 state = ParseState.NORMAL

#             elif char == '\\':
#                 escaping = True

#             else:
#                 current.append(char)

#     #TODO: check if state is in NORMAL, keep prompting user if in quote mode
#     finish_token(tokens, current)

#     return tokens
