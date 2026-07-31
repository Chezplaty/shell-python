import sys
import os
from pathlib import Path

BUILTINS = {"echo", "exit", "type"}

def find_command(command: str) -> Path | None:
    system_path = os.getenv("PATH", "")

    for directory in system_path.split(os.pathsep):
        full_path = Path(directory)/command
        if full_path.exists() and os.access(full_path, os.X_OK): #X_OK tests permissions
            return full_path

    return None


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

        # Echo (print)
        if cmd.startswith("echo"):
            print(arg)

        # Type - description of command type
        elif cmd.startswith("type"):
            if arg in BUILTINS:
                print(f"{arg} is a shell builtin")
            else:
                path = find_command(arg)
                if path:
                    print(f"{arg} is {path}")
                else:
                    print(f"{arg}: not found")

        else:
            print(f"{arg}: command not found") #print for newline


if __name__ == "__main__":
    main()
