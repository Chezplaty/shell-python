from enum import Enum, auto

class LexState(Enum):
    NORMAL = auto()
    SINGLE = auto()
    DOUBLE = auto()

class Token:
    def __init__(self, type, value):
        self.type = type
        self.value = value

class TokenType(Enum):
    WORD = auto()
    REDIRECT_STDOUT = auto()
    REDIRECT_STDERR = auto()
    APPEND_STDOUT = auto()
    APPEND_STDERR = auto()
    PIPE = auto()
    VARIABLE = auto()

TOKEN_TYPES = {'>': TokenType.REDIRECT_STDOUT,
             '1>': TokenType.REDIRECT_STDOUT,
             '2>': TokenType.REDIRECT_STDERR,
             '>>': TokenType.APPEND_STDOUT,
             '1>>': TokenType.APPEND_STDOUT,
             '2>>': TokenType.APPEND_STDERR,
             '|': TokenType.PIPE}

def finish_token(tokens: list[str], current: list[str]) -> None:
    """
    Finalizes the current token by appending it to the token list if it is non-empty.
    Clears the current token buffer so lexing can continue with the next token.
    """

    if not current:
        return

    word = "".join(current)
    token_type = TOKEN_TYPES.get(word, TokenType.WORD)
    
    if '$' in word:
        token_type = TokenType.VARIABLE

    tokens.append(Token(token_type, word))
    current.clear()

class Lexer:
    """
    Lexes shell input into a list of tokens while handling quoting and escaping rules.
    Maintains lexer state while processing characters from an input command string.
    """

    #characters to escape in double quotes
    DOUBLE_ESCAPES = {'"', '\\', '$', '`', '\n'}

    def __init__(self):
        """
        Initializes a lexer with empty token storage and default lexing state.
        Sets the lexer to normal mode with no active escape sequence.
        """

        self._tokens = []
        self._current = []
        self._escaping = False
        self._state = LexState.NORMAL

    def tokenize(self, line: str) -> list[str]:
        """
        Lexes a command string into a list of tokens according to shell lexing rules.
        Processes each character while tracking quote and escape states.
        """

        for char in line:
            if self._state == LexState.NORMAL:
                self.handle_normal(char)

            elif self._state == LexState.SINGLE:
                self.handle_single(char)

            elif self._state == LexState.DOUBLE:
                self.handle_double(char)

        finish_token(self._tokens, self._current)
        return self._tokens

    def disable_escape(self) -> None:
        """
        Disables the active escape sequence flag.
        Allows subsequent characters to be processed normally.
        """

        self._escaping = False

    def handle_normal(self, char: str) -> None:
        """
        Processes a character while the lexer is in normal mode.
        Handles whitespace, quote transitions, escape sequences, and regular characters.
        """

        if self._escaping:
            self._current.append(char)
            self.disable_escape()

        elif char.isspace():
            finish_token(self._tokens, self._current)

        elif char == "'":
            self._state = LexState.SINGLE

        elif char == '"':
            self._state = LexState.DOUBLE

        elif char == '\\':
            self._escaping = True

        else:
            self._current.append(char)

    def handle_single(self, char: str) -> None:
        """
        Processes a character while the lexer is inside single quotes.
        Appends characters literally until the closing single quote is encountered.
        """

        if char == "'":
            self._state = LexState.NORMAL

        else:
            self._current.append(char)

    #TODO: handle special character exceptions
    def handle_double(self, char: str) -> None:
        """
        Processes a character while the lexer is inside double quotes.
        Handles escaped characters and preserves characters until the closing double quote is encountered.
        """

        if self._escaping:
            if char not in self.DOUBLE_ESCAPES:
                self._current.append('\\')
            self._current.append(char)
            self.disable_escape()

        elif char == '"':
            self._state = LexState.NORMAL

        elif char == '\\':
            self._escaping = True

        else:
            self._current.append(char)
