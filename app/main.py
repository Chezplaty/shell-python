import sys
import os
import subprocess 
from pathlib import Path

def executable_path(cmd: str) -> Path | None:
    """
    Searches the system PATH for an executable matching the given command name.
    Returns the command's full path if found, otherwise returns None.
    """
    system_path = os.getenv("PATH", "")

    for directory in system_path.split(os.pathsep):
        full_path = Path(directory)/cmd
        if full_path.exists() and os.access(full_path, os.X_OK): #X_OK tests executable 
            return full_path

    return None

def handle_cd(args: list[str]) -> None:
    """
    Checks if given directory exists.
    Changes into directory if found, otherwise prints an error message.
    """

    if len(args) > 1:
        print(f"cd: too many arguments")

    path = args[0]

    try:
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

def handle_external_programs(cmd, args: list[str]) -> None:
    """
    Executes an external command by locating its executable path through PATH.
    Runs the command with the provided arguments or prints an error if the command cannot be found.
    """

    #TODO: implement error handling if subprocess does not work

    program = executable_path(cmd)
    if program:
        subprocess.run([cmd, *args]) #expand list
    else:
        print(f"{cmd}: command not found")

def handle_type(args: list[str]) -> None:
    """
    Handles the shell's type builtin by identifying whether a command is built in or external.
    Prints the command's location if it exists in PATH, or a not found message otherwise.
    """

    for cmd in args:
        if cmd in BUILTINS:
            print(f"{cmd} is a shell builtin")
            continue

        path = executable_path(cmd)

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

def handle_command(cmd: str, args: list[str]) -> None:
    """
    Executes the appropriate handler for a parsed shell command and its argument.
    Prints an error message when the command is not supported by the shell.
    """ 

    #handler = BUILTINS.get(cmd, "")

    if cmd.startswith("echo"):
        handle_echo(args)

    elif cmd.startswith("type"):
        handle_type(args)

    elif cmd.startswith("pwd"):
        handle_pwd(args)

    elif cmd.startswith("cd"):
        handle_cd(args)

    else:
        handle_external_programs(cmd, args)

def main():
    """
    Runs the interactive shell loop that reads and processes user commands.
    Continuously prompts the user for input until the exit command is received.
    """

    while True:
        sys.stdout.write("$ ") 

        line = input()

        parts = line.split()
        cmd = parts[0]
        args = parts[1:] if len(parts) > 1 else []
        
        if cmd == "exit":
            break

        handle_command(cmd, args)

if __name__ == "__main__":
    main()
