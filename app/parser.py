from enum import Enum, auto

class ParseState(Enum):
    NORMAL = auto()
    SINGLE = auto()
    DOUBLE = auto()

class TokenType(Enum):
    WORD = auto()
    OUTPUT = auto()

def finish_token(tokens: list[str], current: list[str]) -> None:
    """
    Finalizes the current token by appending it to the token list if it is non-empty.
    Clears the current token buffer so parsing can continue with the next token.
    """

    token_type = TokenType.WORD

    if current:

        token = "".join(current)
        if token == '>' or token == '1>':
            token_type = TokenType.OUTPUT

        tokens.append(token)
        current.clear()

class Parser:
    """
    Parses shell input into a list of tokens while handling quoting and escaping rules.
    Maintains parser state while processing characters from an input command string.
    """

    #characters to escape in double quotes
    DOUBLE_ESCAPES = {'"', '\\', '$', '`', '\n'}

    def __init__(self):
        """
        Initializes a parser with empty token storage and default parsing state.
        Sets the parser to normal mode with no active escape sequence.
        """

        self._tokens = []
        self._current = []
        self._escaping = False
        self._state = ParseState.NORMAL

    def parse(self, line: str) -> list[str]:
        """
        Parses a command string into a list of tokens according to shell parsing rules.
        Processes each character while tracking quote and escape states.
        """

        for char in line:
            if self._state == ParseState.NORMAL:
                self.handle_normal_parse(char)

            elif self._state == ParseState.SINGLE:
                self.handle_single_parse(char)

            elif self._state == ParseState.DOUBLE:
                self.handle_double_parse(char)

        finish_token(self._tokens, self._current)
        return self._tokens

    def disable_escape(self) -> None:
        """
        Disables the active escape sequence flag.
        Allows subsequent characters to be processed normally.
        """

        self._escaping = False

    def handle_normal_parse(self, char: str) -> None:
        """
        Processes a character while the parser is in normal mode.
        Handles whitespace, quote transitions, escape sequences, and regular characters.
        """

        if self._escaping:
            self._current.append(char)
            self.disable_escape()

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
        """
        Processes a character while the parser is inside single quotes.
        Appends characters literally until the closing single quote is encountered.
        """

        if char == "'":
            self._state = ParseState.NORMAL
        
        else:
            self._current.append(char)

    #TODO: handle special character exceptions
    def handle_double_parse(self, char: str) -> None:
        """
        Processes a character while the parser is inside double quotes.
        Handles escaped characters and preserves characters until the closing double quote is encountered.
        """

        if self._escaping:
            if char not in self.DOUBLE_ESCAPES:
                self._current.append('\\')
            self._current.append(char)
            self.disable_escape()

        elif char == '"':
            self._state = ParseState.NORMAL
        
        elif char == '\\':
            self._escaping = True
        
        else:
            self._current.append(char)