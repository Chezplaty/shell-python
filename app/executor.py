import subprocess

from app.path_utils import get_executable
from app.shell_builtins import BUILTINS
from app.redirects import open_redirects, redirected_fds

def handle_external_programs(cmd: str, args: list[str], files: dict[int, 'file']) -> None:
    """
    Executes an external command by locating its executable path through PATH.
    Runs the command with the provided arguments or prints an error if the command cannot be found.
    """

    #TODO: implement error handling if subprocess does not work

    program = get_executable(cmd)
    if program:
        subprocess.run([cmd, *args], stdin=files.get(0), stdout=files.get(1), stderr=files.get(2))
    else:
        print(f"{cmd}: command not found")

def handle_command(instruction: Instruction) -> None:
    """
    Executes the appropriate handler for a parsed shell command and its argument.
    Prints an error message when the command is not supported by the shell.
    """

    with open_redirects(instruction) as files:
        handler = BUILTINS.get(instruction.cmd, "")
        if handler:
            #change fds (rewire std outputs) if needed
            with redirected_fds(files):
                handler(instruction)
        else:
            handle_external_programs(instruction.cmd, instruction.args, files)
