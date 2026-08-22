import os

from app.path_utils import get_executable
from app.redirects import open_redirects, redirected_fds
from app.parser import Instruction
from app.jobs import JobsManager, fork_stage, wait_stage


#TODO: split function into helper methods
def run_instructions(instructions: list[Instruction], jobs_manager: JobsManager, builtins: dict[str, function]) -> None:

    run_bg = instructions[0].run_bg
    pids = []
    prev_read_fd = None

    for instruction in instructions:

        if instruction.has_pipe: #if there is a pipe
            read_fd, write_fd = os.pipe()
        else:
            read_fd, write_fd = None, None

        handler = builtins.get(instruction.cmd, "")
        #forking occurs for external programs, background programs, and pipelines
        needs_fork = not handler or run_bg or instruction.has_pipe

        #if no forking, run the command regularly, continue
        if not needs_fork:
            run_command(instruction, builtins, jobs_manager)
            continue

        #the child only keeps open and redirects the fds that it will use, it closes the ones that it doesnt use
        def run_in_child(instruction=instruction, prev_read_fd=prev_read_fd, write_fd=write_fd, read_fd=read_fd):
            if prev_read_fd:
                os.dup2(prev_read_fd, 0) #set read_fd to read from output of last command
                os.close(prev_read_fd)
            if write_fd:
                os.dup2(write_fd, 1) #set stdout to write_fd of pipe
                os.close(write_fd)
            if read_fd:
                os.close(read_fd) #child never reads from the read_fd opened on their turn
            run_command(instruction, builtins, jobs_manager)

        pid = fork_stage(jobs_manager, instruction, run_bg, run_in_child)
        pids.append(pid)

        #parent process closes pipes
        if prev_read_fd:
            os.close(prev_read_fd)
        if write_fd:
            os.close(write_fd)
        prev_read_fd = read_fd #pass on read_fd to next command if any

    if not run_bg:
        for pid in pids: #if not run in the background, wait for child processes to finish
            wait_stage(jobs_manager, pid)

def run_command(instruction: Instruction, builtins: dict[str, function], jobs_manager: JobsManager) -> None:
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
            if get_executable(instruction.cmd) is None:
                print(f"{instruction.cmd}: command not found")
                return

            for fd, file in files.items():
                os.dup2(file.fileno(), fd)
            
            os.execvp(instruction.cmd, [instruction.cmd, *instruction.args])
