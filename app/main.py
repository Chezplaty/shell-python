import sys


def main():
    while True:
        sys.stdout.write("$ ") #no new line, can use print("$ ", end="")

        # Wait for user input
        command = input()

        # Exit
        if command == "exit":
            break

        print(f"{command}: command not found") #print for newline


if __name__ == "__main__":
    main()
