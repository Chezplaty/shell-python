# shell-python

A POSIX-style command-line shell implemented from scratch in Python — no
`readline`, no `subprocess.shell=True`, no shortcuts. It implements its own
lexer, parser, line editor, job control, and process execution using raw
terminal I/O and `os.fork`/`os.execvp`.

## Features

**Parsing & execution**
- Command parsing with single/double-quote handling and backslash escapes
- Output/error redirection: `>`, `1>`, `2>`, `>>`, `1>>`, `2>>`
- Pipelines (`cmd1 | cmd2 | cmd3`)
- Background execution with `&`
- Shell variables: `declare NAME=value`, `$NAME` / `${NAME}` expansion
- Runs builtins in-process and external programs via `PATH` lookup + `execvp`

**Job control**
- Background job tracking with job numbers (`[1] 1234`)
- `jobs` builtin with running/done status and `+`/`-` current/previous markers
- `SIGCHLD`-driven reaping so finished background jobs are detected asynchronously
- Job-completion notices printed without corrupting the in-progress input line

**Interactive line editor**
- Custom raw-mode (cbreak) input loop — not GNU Readline
- Cursor movement (left/right arrows), backspace, in-place redraw
- Command history: up/down arrow navigation, persisted to a history file
- `history` builtin: list, `-r` read, `-w` write, `-a` append
- Tab completion: builtin/PATH command completion, longest-common-prefix
  expansion, candidate listing and cycling, and support for external
  completion scripts registered via `complete -C`

**Builtins**
`cd`, `pwd`, `echo`, `type`, `exit`, `jobs`, `history`, `declare`, `complete`

## Requirements

- Python 3.14+
- A POSIX terminal (uses `os.fork`, `termios`, `tty`, signals — Linux/macOS only, not Windows)

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

## Project layout

```
app/
├── main.py             # shell loop, builtin registry, signal setup
├── lexer.py            # tokenizes input, handles quoting/escaping
├── parser.py           # tokens -> Instruction objects, variable expansion
├── executor.py          # forking, piping, and dispatching instructions
├── redirects.py        # file-descriptor redirection for builtins/externals
├── jobs.py             # job table, SIGCHLD handling, fork/wait helpers
├── shell_builtins.py   # cd, pwd, echo, type, declare, history, complete
├── line_editor.py       # raw-mode keystroke loop
├── edit_buffer.py       # cursor-aware text buffer for the line editor
├── display.py           # terminal rendering (prompt, redraws, candidates)
├── tab_completer.py     # tab-completion state machine
├── tab_completion.py    # candidate generation, formatting, prefix logic
├── completer_runner.py # runs external `complete -C` completion scripts
└── path_utils.py        # PATH lookup, history file location

tests/
├── pytests.py
└── test_integration.py
```

## Design notes

- Process execution is built directly on `os.fork()` / `os.execvp()` rather
  than the `subprocess` module, so the project handles its own pipe
  file-descriptor plumbing, redirection, and zombie reaping.
- Job completion is signal-driven: a `SIGCHLD` handler updates job state, and
  a self-pipe wakes the blocking line editor so completed background jobs are
  reported without polling.
- The line editor operates in `cbreak` mode and manages cursor position,
  redraws, and tab-completion cycling itself, without relying on `readline`.
