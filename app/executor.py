import os
import subprocess
from typing import IO

from app.path_utils import get_executable
from app.redirects import open_redirects, redirected_fds
from app.parser import Instruction

def handle_external_programs(cmd: str, args: list[str], files: dict[int, IO]) -> None:
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

def handle_command(instruction: Instruction, builtins: dict[str, function]) -> None:
    """
    Runs a single parsed command.
    Any redirects on the command are set up first so output goes to the right place.
    """
    
    with open_redirects(instruction) as files:
        handler = builtins.get(instruction.cmd, "")

        if handler:
            #change fds (rewire std outputs) if needed
            with redirected_fds(files):
                handler(instruction)
        else:
            handle_external_programs(instruction.cmd, instruction.args, files)
