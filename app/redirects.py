import os
import sys
from contextlib import contextmanager
from typing import IO, Generator

from app.lexer import TokenType
from app.errors import BuiltinError
from app.parser import Instruction


REDIRECT_FD_MODES = {
    TokenType.REDIRECT_STDOUT: (1, "w"),
    TokenType.REDIRECT_STDERR: (2, "w"),
    TokenType.APPEND_STDOUT: (1, "a"),
    TokenType.APPEND_STDERR: (2, "a"),
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
def open_redirects(instruction: Instruction) -> Generator[dict[int, IO]]:
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
                files[fd] = open(path, mode)
            except OSError as e:
                raise BuiltinError(instruction.cmd, f"{path}: {e.strerror}") from e

        #yield files  
        yield {fd: file.fileno() for fd, file in files.items()} #just yield the numbers instead of objects

    finally:
        for file in files.values():
            file.close()

@contextmanager
def redirected_fds(target_fds: dict[int, IO]) -> Generator[None]:
    """
    Makes a builtin command's printed output actually land in its redirected file, not the screen.
    Only lasts for the duration of the command; everything goes back to normal right after.
    """

    if not target_fds:
        yield
        return

    #empty everything
    sys.stdout.flush()
    sys.stderr.flush()

    #get new un-used fd number that points to same place original fd does
    saved = {fd: os.dup(fd) for fd in target_fds}

    try:
        for fd, target in target_fds.items():
            #make fd for stdout or stderr point to same place target's fd points to
            os.dup2(target.fileno(), fd)
        yield
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        for fd, saved_fd in saved.items():
            os.dup2(saved_fd, fd) #repoint it back
            os.close(saved_fd) #dont need bookmark anymore
