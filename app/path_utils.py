import os
from pathlib import Path
from app.errors import BuiltinError

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
