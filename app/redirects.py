from app.lexer import TokenType
from app.errors import BuiltinError

REDIRECT_FD_MODES = {
    TokenType.OVERWRITE: (1, "w"),
    TokenType.REDIRECT_STDERR: (2, "w")
}

def resolve_redirect_targets(instruction: Instruction) -> dict[int, tuple[str, str]]:
    """
    Resolves command redirections into a mapping of file descriptors to targets and modes.
    """

    targets = {}

    for redirect in instruction.redirects:
        fd, mode = REDIRECT_FD_MODES[redirect.type]
        targets[fd] = (redirect.target, mode)

    return targets