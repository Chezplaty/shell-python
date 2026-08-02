import subprocess

from app.path_utils import get_executable
from app.shell_builtins import BUILTINS
from app.redirects import open_redirects, redirected_fds

def handle_external_programs(cmd: str, args: list[str], files: dict[int, 'file']) -> None:
    """
    Runs an external command as its own program, found by searching PATH.
    Its output, errors, and input go wherever the command's own redirects say they should.
    """

    #TODO: implement error handling if subprocess does not work

    program = get_executable(cmd)
    if program:
        subprocess.run([cmd, *args], stdin=files.get(0), stdout=files.get(1), stderr=files.get(2))
    else:
        print(f"{cmd}: command not found")

def handle_command(instruction: Instruction) -> None:
    """
    Runs a single parsed command.
    Any redirects on the command are set up first so output goes to the right place.
    """

    with open_redirects(instruction) as files:
        handler = BUILTINS.get(instruction.cmd, "")
        if handler:
            #change fds (rewire std outputs) if needed
            with redirected_fds(files):
                handler(instruction)
        else:
            handle_external_programs(instruction.cmd, instruction.args, files)
