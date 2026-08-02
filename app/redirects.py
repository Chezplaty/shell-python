import os
import sys
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
def open_redirects(instruction: Instruction) -> dict[int, 'file']:
    targets = resolve_redirect_targets(instruction)
    files = {}

    try:
        # open all the files and yield them
        for fd, (path, mode) in targets.items():
            try:
                #fd points wherever file object's fd points
                files[fd] = open(path, mode)
            except OSError as e:
                raise BuiltinError(instruction.cmd, f"{path}: {e.strerror}") from e
            
        yield files

    finally:
        for file in files.values():
            file.close()

@contextmanager
def redirected_fds(files: dict[int, 'file']):

    if not files:
        yield
        return

    #empty everything
    sys.stdout.flush()
    sys.stderr.flush()

    #get new un-used fd number that points to samce place original fd does
    saved = {fd: os.dup(fd) for fd in files}

    try:
        for fd, file in files.items():
            #make fd point to same place file's fd points to
            os.dup2(file.fileno(), fd)
        yield
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        for fd, saved_fd in saved.items():
            os.dup2(saved_fd, fd) #repoint it back
            os.close(saved_fd) #dont need bookmark anymore
