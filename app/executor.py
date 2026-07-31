import subprocess

from app.path_utils import get_executable
from app.shell_builtins import BUILTINS

def handle_external_programs(cmd: str, args: list[str]) -> None:
    """
    Executes an external command by locating its executable path through PATH.
    Runs the command with the provided arguments or prints an error if the command cannot be found.
    """

    #TODO: implement error handling if subprocess does not work

    program = get_executable(cmd)
    if program:
        subprocess.run([cmd, *args]) #expand list
    else:
        print(f"{cmd}: command not found")

def handle_command(cmd: str, args: list[str]) -> None:
    """
    Executes the appropriate handler for a parsed shell command and its argument.
    Prints an error message when the command is not supported by the shell.
    """

    handler = BUILTINS.get(cmd, "")

    if handler:
        handler(args)

    else:
        handle_external_programs(cmd, args)
