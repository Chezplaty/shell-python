import sys
import os
import subprocess 
from pathlib import Path

BUILTINS = {"echo", "exit", "type", "pwd", "cd"}


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

def handle_cd(*args: str) -> None:
    """
    Checks if given directory exists.
    Changes into directory if found, otherwise prints an error message.
    """

    if len(*args) > 1:
        print(f"cd: too many arguments")

    direc = args[0][0]
    path_obj = Path(direc)
    if path_obj.exists():
        os.chdir(path_obj)
    else:
        print(f"cd: {direc}: No such file or directory")
    

def handle_pwd() -> None:
    """
    Prints the current working directory.
    """

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

def handle_type(cmd: str) -> None:
    """
    Handles the shell's type builtin by identifying whether a command is built in or external.
    Prints the command's location if it exists in PATH, or a not found message otherwise.
    """

    if cmd in BUILTINS:
        print(f"{cmd} is a shell builtin")
        return

    path = executable_path(cmd)

    if path:
        print(f"{cmd} is {path}")

    else:
        print(f"{cmd}: not found")

def handle_command(cmd: str, args: list[str]) -> None:
    """
    Executes the appropriate handler for a parsed shell command and its argument.
    Prints an error message when the command is not supported by the shell.
    """ 

    if cmd.startswith("echo"):
        print(" ".join(args))

    elif cmd.startswith("type"):
        handle_type(args[0])

    elif cmd.startswith("pwd"):
        handle_pwd()

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
