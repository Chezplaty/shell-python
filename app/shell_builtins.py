import os
from pathlib import Path

from app.path_utils import get_executable
from app.errors import BuiltinError

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
        if cmd in BUILTINS:
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
    Preserves the order of the arguments and appends a newline to the output.
    """

    print(" ".join(instruction.args))

BUILTINS = {"exit": None,
            "echo": handle_echo,
            "type": handle_type,
            "pwd": handle_pwd,
            "cd": handle_cd}
