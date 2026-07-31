import sys

BUILTINS = {"echo", "exit", "type"}

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
            if (arg) in BUILTINS:
                print(f"{arg} is a shell builtin")
            else:
                print(f"{arg}: not found")

        else:
            print(f"{arg}: command not found") #print for newline


if __name__ == "__main__":
    main()
