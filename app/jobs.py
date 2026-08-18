import os
import signal
from collections import namedtuple

from app.parser import Instruction

Job = namedtuple("Job", ["job_num", "instruction", "background", "status"])

#TODO: make sure the job marker changes work and make it more robust

class JobsManager:

    def __init__(self):
        self.jobs: dict[int, Job] = {}
        self.job_num = 1
        self.used_job_nums = set()
        self.completed_background_jobs = set()
        self.job_order = [] # stack
        self.current_job = None
        self.previous_job = None

    def handle_jobs(self, instruction: Instruction) -> None:
        """
        Sorts all background jobs by their job number and prints each job.
        Uses the formatted job text for consistent job status display.
        """

        jobs = sorted(
            ((pid, job) for pid, job in self.jobs.items() if job.job_num is not None),
            key=lambda pair: pair[1].job_num
        )

        #TODO: replace '+' with appropiate marker when implemented
        for pid, job in jobs:
            print(self.format_print_text(pid))

    def format_print_text(self, pid: int) -> str:
        """
        Formats a job's number, status, and command into a display string.
        Returns the formatted text for printing to the terminal.
        """
        job = self.get_job(pid)
        marker = self.choose_marker(pid)
        line = job.instruction.cmd + ' ' + " ".join(job.instruction.args)
        text = f"[{job.job_num}] {marker} {job.status:<10}{line}"
        return text

    def choose_marker(self, pid: int) -> str:
        marker = ' '
        if self.current_job == pid:
            marker = '+'
        elif self.previous_job == pid:
            marker = '-'
        return marker

    def get_job(self, pid: int) -> Job:
        return self.jobs[pid]

    def get_next_job_num(self) -> int:
        """
        Return the next available background job number.
        Advance past any numbers that are currently in use.
        """
        while self.job_num in self.used_job_nums:
            self.job_num += 1
        return self.job_num

    def set_job_markers(self, pid: int):
        self.previous_job = self.current_job
        self.current_job = pid

    def add_job(self, pid: int, instruction: Instruction, background: bool) -> None:
        """
        Register a process as a managed job with its instruction and state.
        Assign a job number when the process is running in the background.
        """
        job_num = None
        if background:
            job_num = self.get_next_job_num()
            self.used_job_nums.add(job_num)
            self.set_job_markers(pid)
        self.jobs[pid] = Job(job_num, instruction, background, status='running')

    def mark_exited(self, pid: int) -> None:
        """
        Record the exit status for a tracked process.
        Leave the job unchanged when the process is not currently tracked.
        """
        job = self.jobs.get(pid)
        if job is not None:
            self.jobs[pid] = job._replace(status='done')
            if job.job_num is not None: # if it is a background job, mark it as completed
                self.completed_background_jobs.add(pid)

    def is_finished(self, pid: int) -> bool:
        """
        Return whether the specified job has finished execution.
        A job is finished when its recorded status is no longer None.
        """
        return self.jobs[pid].status == 'done'

    def remove_job(self, pid: int) -> None:
        """
        Remove a tracked process and release its background job number.
        Reset the next job number if the removed number is less than the job num.
        """
        job = self.jobs.pop(pid, None)
        if pid in self.completed_background_jobs:
            self.used_job_nums.discard(job.job_num)
            self.job_num = min(self.job_num, job.job_num)
            self.completed_background_jobs.remove(pid)

            # set the next priority jobs
            self.remove_markers(pid)

    def remove_markers(self, pid: int) -> None:

        if self.current_job == pid:
            self.current_job = self.previous_job
            self.previous_job = next(reversed(self.jobs))
        elif self.previous_job == pid:
            self.previous_job = next(reversed(self.jobs))

    def print_job(self, pid: int):
        """
        Print the background job number and process ID for a job.
        Look up the tracked job and display its identifying information.
        """
        job = self.jobs[pid]
        print(f"[{job.job_num}] {pid}")

    def get_completed_jobs(self) -> set[int]:
        """
        Return a copy so that changes while looping do not affect the loop.
        """
        return list(self.completed_background_jobs)

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
            
            jobs_manager.mark_exited(pid)

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
