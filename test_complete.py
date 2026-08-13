#!/usr/bin/env python3

import sys

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