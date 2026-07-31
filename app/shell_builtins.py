import os
from pathlib import Path

from app.path_utils import get_executable

def handle_cd(args: list[str]) -> None:
    """
    Checks if given directory exists.
    Changes into directory if found, otherwise prints an error message.
    """

    if len(args) > 1:
        print(f"cd: too many arguments")
        return

    #path is home directory if args is nothing or ~
    path = Path.home() if not args or args[0] == '~' else args[0]

    try:
        #changes direc relative to cwd (tracked by OS kernel)
        os.chdir(path)
    except FileNotFoundError:
        print(f"cd: {path}: No such file or directory")
    except NotADirectoryError:
        print(f"cd {path}: Not a directory")
    except PermissionError:
        print(f"cd: {path}: Permission denied")

def handle_pwd(args: list[str]) -> None:
    """
    Prints the current working directory.
    Prints an error message if there are other arguments.
    """

    if args:
        print("pwd: too many arguments")
        return

    print(Path.cwd())

def handle_type(args: list[str]) -> None:
    """
    Handles the shell's type builtin by identifying whether a command is built in or external.
    Prints the command's location if it exists in PATH, or a not found message otherwise.
    """

    for cmd in args:
        if cmd in BUILTINS:
            print(f"{cmd} is a shell builtin")
            continue

        path = get_executable(cmd)

        if path:
            print(f"{cmd} is {path}")

        else:
            print(f"{cmd}: not found")

def handle_echo(args: list[str]) -> None:
    """
    Prints the provided arguments separated by spaces.
    Preserves the order of the arguments and appends a newline to the output.
    """

    print(" ".join(args))

BUILTINS = {"exit": None,
            "echo": handle_echo,
            "type": handle_type,
            "pwd": handle_pwd,
            "cd": handle_cd}
