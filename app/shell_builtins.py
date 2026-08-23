import os
from pathlib import Path

from app.path_utils import get_executable
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

    def __init__(self):
        self.history = {}
        self.num = 1
        self.pos = 1

    def add_line(self, line: str):
        self.history[self.num] = line
        self.num += 1
        self.pos = len(self.history) + 1 #set to one after latest command

    def handle_history(self, instruction: Instruction) -> None:
        #TODO: error handling if the argument is not an integer
        start = int(instruction.args[0]) if instruction.args else 1

        if start < 0:
            start = len(self.history) + start

        for i in range(start, len(self.history)):
            print(f"{i} {self.history[i]}")

    def get_next_line(self, direction: int) -> str | None:
        new_pos = self.pos + direction
        if new_pos <= 0 or new_pos > len(self.history):
            return

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
    "history"
}