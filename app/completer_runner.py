import os
import subprocess
import signal
from types import MappingProxyType


def run_completer_script(
    paths: MappingProxyType, command: str, args: list[str], comp_line: str, comp_point: int
) -> list[str] | None:
    """
    Runs the registered completer script with command arguments and completion environment.
    Returns a list of the script's output lines, or None if no completer is registered.
    """

    if command not in paths:
        return None

    env_copy = os.environ.copy()
    env_copy["COMP_LINE"] = comp_line
    env_copy["COMP_POINT"] = str(comp_point)

    path = paths[command]
    os.chmod(path, os.stat(path).st_mode | 0o111) # make path executable for testing purposes
    #TODO: implement error handling when path cannot be run

    signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGCHLD})
    try:
        output = subprocess.run([path, *args], env=env_copy, capture_output=True, text=True)
    finally:
        signal.pthread_sigmask(signal.SIG_UNBLOCK, {signal.SIGCHLD})
        
    return output.stdout.splitlines()
