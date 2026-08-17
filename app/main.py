import sys
import os
import signal

from app.errors import BuiltinError, ParseError
from app.executor import handle_command
from app.lexer import Lexer
from app.line_editor import LineEditor
from app.tab_completion import compile_choices
from app.parser import parse
from app.shell_builtins import (
    CompleteManager,
    handle_cd,
    handle_echo,
    handle_pwd,
    handle_type
)

from contextlib import contextmanager
import tty
import termios

@contextmanager
def set_cbreak_mode():
    """
    Temporarily switches stdin into cbreak mode for character-by-character input.
    Restores the original terminal settings when the context exits.
    """
    fd = sys.stdin.fileno()
    old_settings = tty.setcbreak(fd)

    try:
        yield 
    finally:
        termios.tcsetattr(fd, termios.TCSAFLUSH, old_settings)

#TODO: create a class to hold all background jobs

class JobsManager:

    def __init__(self):
        self.jobs = {} # map pid: job
        self.job_num = 1 # start at 1
        self.used_job_nums = set()

    def has_job(self, pid: int) -> bool:
        return pid in self.jobs
    
    def get_next_job_num(self):
        while self.job_num in self.used_job_nums:
            self.job_num += 1

    def add_job(self, pid: int, instruction: Instruction):
        self.get_next_job_num()
        self.jobs[pid] = (self.job_num, instruction)
        self.reserve_job_num()

    def reserve_job_num(self):
        self.used_job_nums.add(self.job_num)
        self.job_num += 1

    def remove_job(self, pid: int):
        job_num = self.jobs[pid][0]
        del self.used_job_nums[job_num]
        self.job_num = min(self.job_num, job_num) #job number reusable, use lower num

    def print_job(self, pid: int):
        job_num, instruction = self.jobs[pid]
        print(f"[{job_num}] {pid}")

def make_sigchld_handler(jobs_manager: JobsManager):

    def handle_sigchld(_signum, _frame):
        while True:
            try:
                pid, status = os.waitpid(-1, os.WNOHANG) # -1: status requested for any child process

                if pid == 0:
                    return

                if jobs_manager.has_job(pid):
                    jobs_manager.remove_job(pid)

            except ChildProcessError as e:
                print(e)
                return

    return handle_sigchld

def run_in_background(jb_man: JobsManager, instruction: Instruction, builtins: dict[str: function]) -> None:

    #temporarily block signals
    signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGCHLD})

    try:
        pid = os.fork()
        if pid == 0: #child process

            signal.pthread_sigmask(signal.SIG_UNBLOCK, {signal.SIGCHLD})
            handle_command(instruction, builtins)
            exit(0)
        else: #parent process
            jb_man.add_job(pid, instruction)
            jb_man.print_job(pid)
    finally:
        #unblock
        signal.pthread_sigmask(signal.SIG_UNBLOCK, {signal.SIGCHLD})
        
def main():
    """
    Runs the interactive shell loop that reads and processes user commands.
    Continuously prompts the user for input until the exit command is received.
    """
    choices = compile_choices()
    complete_manager = CompleteManager()
    jobs_manager = JobsManager()
    
    handler = make_sigchld_handler(jobs_manager)
    signal.signal(signal.SIGCHLD, handler)

    builtins = {"exit": None,
                "echo": handle_echo,
                "type": handle_type,
                "pwd": handle_pwd,
                "cd": handle_cd,
                "complete": complete_manager.handle_complete,
                "jobs": None}

    while True:
        with set_cbreak_mode():

            sys.stdout.write("$ ")
            sys.stdout.flush()

            line = LineEditor(choices, complete_manager.get_paths()).run()
        #restore on exit

        if not line.strip(): 
            continue

        tokens = Lexer().tokenize(line)

        try:
            instruction = parse(tokens)
        except ParseError as e:
            print(f"shell: {e}")
            continue

        if instruction.cmd == "exit":
            break

        try:
            if instruction.run_bg:
                run_in_background(jobs_manager, instruction, builtins)
            else:
                handle_command(instruction, builtins)
        except BuiltinError as e:
            print(e)

if __name__ == "__main__":
    main()
