import os
from pathlib import Path

from app.path_utils import get_executable
from app.lexer import TokenType

from app.errors import BuiltinError

def handle_cd(instruction: Instruction) -> None:
    """
    Checks if given directory exists.
    Changes into directory if found, otherwise prints an error message.
    """
    args = instruction.args
    
    if len(args) > 1:
        raise BuiltinError("cd", "too many arguments")

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

def handle_pwd(instruction: Instruction) -> None:
    """
    Prints the current working directory.
    Raises an exception if there are other arguments.
    """

    if instruction.args:
        raise BuiltinError("pwd", "too many arguments")

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

    # check if output needs to be redirected
    output = " ".join(instruction.args)
    if instruction.redirects:
        for redirect in instruction.redirects:
            if redirect.type == TokenType.OVERWRITE:
                try:
                    with open(redirect.target, "w") as file:
                        file.write(output)
                except FileNotFoundError:
                    print(f"echo: {redirect.target}: No such file or directory")
                #TODO: check between access denied and target just being a directory
                except PermissionError:
                    print(f"echo: {redirect.target}: Permission denied")
    else:
        print(output)

BUILTINS = {"exit": None,
            "echo": handle_echo,
            "type": handle_type,
            "pwd": handle_pwd,
            "cd": handle_cd}
