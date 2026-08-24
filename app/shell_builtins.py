import os
from pathlib import Path

from app.path_utils import get_executable, get_histfile
from app.errors import BuiltinError
from app.parser import Instruction

from types import MappingProxyType 

class CompleteManager:
    def __init__(self) -> None:
        self.paths = {}

    def get_paths(self) -> MappingProxyType:
        """
        Returns a read-only view of the registered completion paths.
        """
        return MappingProxyType(self.paths)
    
    def handle_complete(self, instruction: Instruction) -> None:
        """
        Handles the complete builtin by dispatching the requested completion operation.
        Supports printing, registering, and removing completion specifications.
        """

        args = instruction.args

        if not args: 
            return
        
        flag = args[0]

        if flag == "-p":
            self.print_complete(args, instruction.cmd)

        elif flag == "-C":
            self.register_completer(args, instruction.cmd)

        elif flag == "-r":
            self.remove_completer(args, instruction.cmd)

    def print_complete(self, args: list[str], cmd: str) -> None:
        """
        Prints the registered completer path for the given command.
        Raises an error if no command or completion specification is provided.
        """

        try:
            command = args[1]
            path = self.paths[command]
            print(f"complete -C '{path}' {command}")
        except IndexError:
            raise BuiltinError(cmd, "no command given")
        except KeyError:
            raise BuiltinError(cmd, f"{args[1]}: no completion specification")

    def register_completer(self, args: list[str], cmd: str) -> None:
        """
        Registers a completer path for each specified command.
        Raises an error if the completer path or command is missing.
        """

        try:
            path = args[1]
            commands = args[2:]
            for command in commands:
                self.paths[command] = path
        except IndexError:
            raise BuiltinError(cmd, "missing arguments for option: -C")

    def remove_completer(self, args: list[str], cmd: str) -> None:
        """
        Removes the registered completer for the given command.
        Does nothing if no completion specification exists for the command.
        """

        try:
            command = args[1]
            del self.paths[command]
        except IndexError:
            raise BuiltinError(cmd, "no command given")
        except KeyError: #if key doesnt exist, dont raise error
            pass

class HistoryManager:

    def __init__(self) -> None:
        """
        Initialize the history manager and its tracking state.
        Sets up history storage and command position counters.
        """

        self.history = {}
        self.num = 1
        self.pos = 1
        self.written = 1

        self.hist_start = 1

    def __enter__(self) -> HistoryManager:
        """
        Load command history when entering the context manager.
        Returns the initialized history manager instance.
        """

        self.load_hist_file()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """
        Append pending command history when leaving the context manager.
        Returns False to allow any exception to propagate.
        """

        hist_path = get_histfile()

        if hist_path is not None:
            self.append_to_file(hist_path, exit=True)

        return False #let exception propagate

    def load_hist_file(self) -> None:
        """
        Load existing command history from the configured history file.
        Updates the starting position for newly added history entries.
        """

        hist_path = get_histfile()

        if hist_path is None:
            return

        self.add_to_history(hist_path)
        self.hist_start = len(self.history) + 1

    def add_line(self, line: str) -> None:
        """
        Add a line to the command history.
        Update the history position to after the latest command.
        """

        self.history[self.num] = line
        self.num += 1
        self.pos = len(self.history) + 1 #set to one after latest command

    def handle_history(self, instruction: Instruction) -> None:
        """
        Handle the history command and its optional arguments.
        Supports reading history from a file and listing history entries.
        """

        start = 1
        if instruction.args:
            flag = instruction.args[0]

            if flag == '-r':
                self.add_to_history(instruction.args[1])
                return

            elif flag == '-w':
                self.write_to_file(instruction.args[1])
                return

            elif flag == '-a':
                self.append_to_file(instruction.args[1])
                return

            elif flag.lstrip('-').isdigit():
                start = int(flag)

            else:
                raise BuiltinError(instruction.cmd, "flag unknown")
        
        self.list_history(start)

    def add_to_history(self, path: str) -> None:
        """
        Read history entries from the specified file.
        Add each line from the file to the command history.
        """

        try:
            with open(path, "r") as file:
                for line in file:
                    self.add_line(line.rstrip('\r\n'))
        except Exception as e:
            raise BuiltinError("history", e)

    def write_to_file(self, path: str) -> None:
        """
        Write command history to the specified file.
        Overwrites the file if it already exists.
        """

        try:
            with open(path, "w") as file:
                for line in self.history.values():
                    file.write(f"{line}\n")
        except Exception as e:
            raise BuiltinError("history", e)

    def append_to_file(self, path: str, exit=False) -> None:
        """
        Append unwritten command history to the specified file.
        Updates the written position when appending during normal operation.
        """

        start = self.hist_start if exit else self.written
        try:
            with open(path, "a") as file:
                while start <= len(self.history):
                    file.write(f"{self.history[start]}\n")
                    start += 1

            if not exit:
                self.written = len(self.history) + 1

        except Exception as e:
            raise BuiltinError("history", e)

    def list_history(self, start) -> None:
        """
        Print history entries starting from the specified index.
        Supports negative indices relative to the end of history.
        """

        if start < 0:
            start = max(1, len(self.history) + start) #start cant go below 1

        for i in range(start, len(self.history)):
            print(f"{i} {self.history[i]}")

    def get_next_line(self, direction: int) -> str | None:
        new_pos = self.pos + direction
        if new_pos <= 0:
            return None

        if new_pos > len(self.history): # give empty line
            return ''

        self.pos = new_pos
        return self.history[self.pos]

def handle_cd(instruction: Instruction) -> None:
    """
    Checks if given directory exists.
    Changes into directory if found, otherwise prints an error message.
    """
    args = instruction.args

    if len(args) > 1:
        raise BuiltinError(instruction.cmd, "too many arguments")

    #path is home directory if args is nothing or ~
    path = Path.home() if not args or args[0] == '~' else args[0]

    try:
        #changes direc relative to cwd (tracked by OS kernel)
        os.chdir(path)
    except OSError as e:
        raise BuiltinError(instruction.cmd, f"{path}: {e.strerror}") from e

def handle_pwd(instruction: Instruction) -> None:
    """
    Prints the current working directory.
    Raises an exception if there are other arguments.
    """

    if instruction.args:
        raise BuiltinError(instruction.cmd, "too many arguments")

    print(Path.cwd())

def handle_type(instruction: Instruction) -> None:
    """
    Handles the shell's type builtin by identifying whether a command is built in or external.
    Prints the command's location if it exists in PATH, or a not found message otherwise.
    """

    for cmd in instruction.args:
        if cmd in BUILTIN_NAMES:
            print(f"{cmd} is a shell builtin")
            continue

        path = get_executable(cmd)

        if path:
            print(f"{cmd} is {path}")

        else:
            print(f"{cmd}: not found")

def handle_echo(instruction: Instruction) -> None:
    """
    Prints the provided arguments separated by spaces.
    """

    print(" ".join(instruction.args))

BUILTIN_NAMES = {
    "exit",
    "echo",
    "type",
    "pwd",
    "cd",
    "complete",
    "jobs",
    "history",
    "declare"
}