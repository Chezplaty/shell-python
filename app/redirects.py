from contextlib import contextmanager

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

@contextmanager
def open_redirects(instruction: Instruction):
    targets = resolve_redirect_targets(instruction)
    files = {}
    
    try:
        # open all the files and yield them
        for fd, (path, mode) in targets.items():
            try:
                files[fd] = open(path, mode)
            except OSError as e:
                raise BuiltinError(instruction.cmd, f"{path}: {e.strerror}") from e
            
        yield files

    finally:
        for file in files.values():
            file.close()

