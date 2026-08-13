#!/usr/bin/env python3

import sys

if len(sys.argv) < 3:
    print("Usage: test_complete.py <command> <prefix> [previous_args...]", file=sys.stderr)
    sys.exit(1)

command = sys.argv[1]
prefix = sys.argv[2]
previous_args = sys.argv[3:]

candidates = [
    "set-url",
    "set-branches",
    "set-head",
    "get-url",
    "add",
    "remove",
]

for candidate in candidates:
    if candidate.startswith(prefix):
        print(candidate)