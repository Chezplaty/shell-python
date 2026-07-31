import sys
import os
from pathlib import Path

BUILTINS = {"echo", "exit", "type"}

def find_command(cmd: str) -> Path | None:
    system_path = os.getenv("PATH", "")

    for directory in system_path.split(os.pathsep):
        full_path = Path(directory)/cmd
        if full_path.exists() and os.access(full_path, os.X_OK): #X_OK tests permissions
            return full_path

    return None

def handle_type(cmd: str):
    if cmd in BUILTINS:
        print(f"{cmd} is a shell builtin")
        return

    path = find_command(cmd)

    if path:
        print(f"{cmd} is {path}")

    else:
        print(f"{cmd}: not found")

def handle_command(cmd, arg): 

    if cmd.startswith("echo"):
        print(arg)

    elif cmd.startswith("type"):
        handle_type(arg)

    else:
        print(f"{cmd}: command not found")

def main():
    while True:
        sys.stdout.write("$ ") #no new line, can use print("$ ", end="")

        # Wait for user input
        line = input()

        parts = line.split(maxsplit=1)
        cmd = parts[0]
        arg = parts[1] if len(parts) > 1 else ""

        # Exit
        if cmd == "exit":
            break

        handle_command(cmd, arg)



if __name__ == "__main__":
    main()
