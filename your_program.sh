#!/bin/sh
#
# Runs the shell locally using the project's venv.

set -e # Exit early if any commands fail

SCRIPT_DIR="$(dirname "$0")"
PYTHONSAFEPATH=1 PYTHONPATH="$SCRIPT_DIR" exec "$SCRIPT_DIR/venv/bin/python" -m app.main "$@"
