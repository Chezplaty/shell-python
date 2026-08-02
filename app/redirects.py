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
    Figures out which file a command's output, errors, and input should each go to or come from.
    If a command redirects the same stream more than once, only the last one takes effect.
    """

    targets = {}

    for redirect in instruction.redirects:
        fd, mode = REDIRECT_FD_MODES[redirect.type]
        targets[fd] = (redirect.target, mode)

    return targets

@contextmanager
def open_redirects(instruction: Instruction) -> dict[int, 'file']:
    """
    Opens the files a command's redirects point to, so its output/errors can be written there.
    Closes every file it opened once the command is done, even if something goes wrong.
    """

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
    """
    Makes a builtin command's printed output actually land in its redirected file, not the screen.
    Only lasts for the duration of the command; everything goes back to normal right after.
    """

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
