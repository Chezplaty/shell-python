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
        """
        Return the next available background job number.
        Advance past any numbers that are currently in use.
        """
        while self.job_num in self.used_job_nums:
            self.job_num += 1
        return self.job_num

    def add_job(self, pid: int, instruction: Instruction, background: bool) -> None:
        """
        Register a process as a managed job with its instruction and state.
        Assign a job number when the process is running in the background.
        """
        job_num = None
        if background:
            job_num = self.get_next_job_num()
            self.used_job_nums.add(job_num)
        self.jobs[pid] = Job(job_num, instruction, background, status=None)

    def mark_exited(self, pid: int, status: int) -> None:
        """
        Record the exit status for a tracked process.
        Leave the job unchanged when the process is not currently tracked.
        """
        job = self.jobs.get(pid)
        if job is not None:
            self.jobs[pid] = job._replace(status=status)

    def is_finished(self, pid: int) -> bool:
        """
        Return whether the specified job has finished execution.
        A job is finished when its recorded status is no longer None.
        """
        return self.jobs[pid].status is not None

    def remove_job(self, pid: int) -> None:
        """
        Remove a tracked process and release its background job number.
        Reset the next job number if the removed number is less than the job num.
        """
        job = self.jobs.pop(pid, None)
        if job.job_num is not None:
            self.used_job_nums.discard(job.job_num)
            self.job_num = min(self.job_num, job.job_num)

    def print_job(self, pid: int):
        """
        Print the background job number and process ID for a job.
        Look up the tracked job and display its identifying information.
        """
        job = self.jobs[pid]
        print(f"[{job.job_num}] {pid}")


def make_sigchld_handler(jobs_manager: JobsManager) -> function:
    """
    Create a SIGCHLD handler that updates the supplied job manager.
    """
    def handle_sigchld(_signum, _frame) -> None:
        """
        Handle SIGCHLD signals by collecting available child statuses.
        Continue until no exited child processes remain to be collected.
        """
        while True:
            try:
                pid, status = os.waitpid(-1, os.WNOHANG) # -1: check if any child process changed
            except ChildProcessError:
                return
            
            if pid == 0:
                return
            
            jobs_manager.mark_exited(pid, status)

    return handle_sigchld

def fork_and_track(jobs_manager: JobsManager, instruction: Instruction, background: bool, run_in_child) -> None:
    """
    Fork a child process, register it, and optionally wait for completion.
    Block SIGCHLD during setup to prevent races while registering the child.
    """
    signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGCHLD})
    try:
        pid = os.fork()

        if pid == 0: #child process
            signal.pthread_sigmask(signal.SIG_UNBLOCK, {signal.SIGCHLD})
            run_in_child()
            os._exit(0)

        # parent
        jobs_manager.add_job(pid, instruction, background)

        if background:
            jobs_manager.print_job(pid)
    finally:
        signal.pthread_sigmask(signal.SIG_UNBLOCK, {signal.SIGCHLD})

    if not background:
        while not jobs_manager.is_finished(pid): #parent process waits for child to finish
            signal.pause()
        jobs_manager.remove_job(pid)
