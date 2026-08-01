# shell-python

A POSIX-style shell implemented in Python. It supports command parsing (including
quoting), builtin commands (`cd`, `pwd`, `echo`, and more), and running external
programs on `PATH`.

## Setup

```sh
python3 -m venv venv
./venv/bin/pip install -e ".[dev]"
```

## Running

```sh
./your_program.sh
```

## Testing

```sh
./venv/bin/pytest
```
