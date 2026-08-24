import os
from pathlib import Path

SUPPORTED_SHELLS = {
    "~/.zsh_history",
    "~/.bash_history"
}

def get_executable(cmd: str) -> Path | None:
    """
    Searches the system PATH for an executable matching the given command name.
    Returns the command's full path if found, otherwise returns None.
    """
    system_path = os.getenv("PATH", "")

    for directory in system_path.split(os.pathsep):
        full_path = Path(directory)/cmd
        if full_path.exists() and os.access(full_path, os.X_OK): #X_OK tests executable
            return full_path

    return None

def get_histfile() -> str | None:
    """
    Return the shell history file path, if one can be found.
    Check HISTFILE first, then fall back to supported shell paths.
    """

    hist_file = os.getenv("HISTFILE")

    if hist_file is None: #histfile not exported, shell var only
        for path in SUPPORTED_SHELLS:
            hist_path = os.path.expanduser(path)
            if os.path.exists(hist_path):
                hist_file = hist_path
                break

    return hist_file
