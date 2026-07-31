import sys

BUILTINS = {"echo", "exit", "type"}

def main():
    while True:
        sys.stdout.write("$ ") #no new line, can use print("$ ", end="")

        # Wait for user input
        command = input()

        # Exit
        if command == "exit":
            break

        # Echo (print)
        if command.startswith("echo"):
            print(command[5:])

        # Type - description of command type
        elif command.startswith("type"):
            if (command[5:]) in BUILTINS:
                print(f"{command[5:]} is a shell builtin")
            else:
                print(f"{command[5:]}: not found")

        else:
            print(f"{command}: command not found") #print for newline


if __name__ == "__main__":
    main()
