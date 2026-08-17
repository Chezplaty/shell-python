import os
from typing import IO

from app.path_utils import get_executable
from app.redirects import open_redirects, redirected_fds
from app.parser import Instruction
from app.jobs import JobsManager, fork_and_track

def handle_external_programs(instruction: Instruction, files: dict[int, IO], jobs_manager: JobsManager):
    """
    Run an external program with the provided file descriptors.
    Fork the process, redirect its files, and execute the requested command.
    """
    if get_executable(instruction.cmd) is None:
        print(f"{instruction.cmd}: command not found")
        return

    def run_in_child():
        for fd, file in files.items():
            os.dup2(file.fileno(), fd)

        os.execvp(instruction.cmd, [instruction.cmd, *instruction.args])
        #dont need to restore fd, child process exits
    
    fork_and_track(jobs_manager, instruction, False, run_in_child)

def handle_command(instruction: Instruction, builtins: dict[str, function], jobs_manager: JobsManager) -> None:
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
            handle_external_programs(instruction, files, jobs_manager)
