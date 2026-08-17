import os
import signal
from collections import namedtuple

from app.parser import Instruction

Job = namedtuple("Job", ["job_num", "instruction", "background", "status"])

class JobsManager:

    def __init__(self):
        self.jobs: dict[int, Job] = {}
        self.job_num = 1
        self.used_job_nums = set()

    def get_next_job_num(self) -> int:
        while self.job_num in self.used_job_nums:
            self.job_num += 1
        return self.job_num

    def add_job(self, pid: int, instruction: Instruction, background: bool):
        job_num = None
        if background:
            job_num = self.get_next_job_num()
            self.used_job_nums.add(job_num)
        self.jobs[pid] = Job(job_num, instruction, background, status=None)

    def mark_exited(self, pid: int, status: int) -> None:
        job = self.jobs.get(pid)
        if job is not None:
            self.jobs[pid] = job._replace(status=status)

    def is_finished(self, pid: int) -> bool:
        return self.jobs[pid].status is not None

    def remove_job(self, pid: int):
        job = self.jobs.pop(pid, None)
        if job.job_num is not None:
            self.used_job_nums.discard(job.job_num)
            self.job_num = min(self.job_num, job.job_num)

    def print_job(self, pid: int):
        job = self.jobs[pid]
        print(f"[{job.job_num}] {pid}")


def make_sigchld_handler(jobs_manager: JobsManager):
    def handle_sigchld(_signum, _frame):
        while True:
            try:
                pid, status = os.waitpid(-1, os.WNOHANG) # -1: check if any child process changed
            except ChildProcessError:
                return
            
            if pid == 0:
                return
            
            jobs_manager.mark_exited(pid, status)
            
    return handle_sigchld

def fork_and_track(jobs_manager: JobsManager, instruction: Instruction, background: bool, run_in_child) -> int:
    """
    Forks a child to run `run_in_child`, registers it with jobs_manager,
    and (for foreground jobs) blocks until it exits.
    """
    signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGCHLD})
    try:
        pid = os.fork()

        if pid == 0:
            signal.pthread_sigmask(signal.SIG_UNBLOCK, {signal.SIGCHLD})
            run_in_child()
            os._exit(0)

        jobs_manager.add_job(pid, instruction, background)

        if background:
            jobs_manager.print_job(pid)
    finally:
        signal.pthread_sigmask(signal.SIG_UNBLOCK, {signal.SIGCHLD})

    if not background:
        while not jobs_manager.is_finished(pid): #parent process waits for child to finish
            signal.pause()
        jobs_manager.remove_job(pid)

    return pid
