import os
import stat
from pathlib import Path

import pytest

from app import main


def make_executable(path: Path) -> None:
    path.write_text("#!/bin/sh\necho hi\n")
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


# ---------------------------------------------------------------------------
# find_command
# ---------------------------------------------------------------------------

class TestFindCommand:
    def test_returns_path_when_executable_found(self, tmp_path, monkeypatch):
        exe = tmp_path / "mycmd"
        make_executable(exe)
        monkeypatch.setenv("PATH", str(tmp_path))

        result = main.find_command("mycmd")

        assert result == exe

    def test_returns_none_when_not_found(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PATH", str(tmp_path))

        assert main.find_command("does_not_exist") is None

    def test_empty_path_returns_none(self, monkeypatch):
        monkeypatch.setenv("PATH", "")

        assert main.find_command("ls") is None

    def test_returns_first_match_in_path_order(self, tmp_path, monkeypatch):
        first_dir = tmp_path / "first"
        second_dir = tmp_path / "second"
        first_dir.mkdir()
        second_dir.mkdir()
        make_executable(first_dir / "mycmd")
        make_executable(second_dir / "mycmd")
        monkeypatch.setenv("PATH", os.pathsep.join([str(first_dir), str(second_dir)]))

        result = main.find_command("mycmd")

        assert result == first_dir / "mycmd"

    def test_file_exists_but_not_executable_is_skipped(self, tmp_path, monkeypatch):
        non_exec = tmp_path / "mycmd"
        non_exec.write_text("not executable")
        non_exec.chmod(stat.S_IREAD)
        monkeypatch.setenv("PATH", str(tmp_path))

        assert main.find_command("mycmd") is None


# ---------------------------------------------------------------------------
# handle_external_programs
# ---------------------------------------------------------------------------

class TestHandleExternalPrograms:
    def test_runs_command_when_found(self, monkeypatch):
        monkeypatch.setattr(main, "find_command", lambda cmd: Path("/usr/bin/ls"))
        calls = []
        monkeypatch.setattr(main.subprocess, "run", lambda args: calls.append(args))

        main.handle_external_programs("ls", ["-la"])

        assert calls == [["/usr/bin/ls", "-la"]]

    def test_prints_not_found_when_missing(self, monkeypatch, capsys):
        monkeypatch.setattr(main, "find_command", lambda cmd: None)

        main.handle_external_programs("nope", [])

        captured = capsys.readouterr()
        assert captured.out == "nope: command not found\n"

    def test_runs_with_no_args(self, monkeypatch):
        monkeypatch.setattr(main, "find_command", lambda cmd: Path("/usr/bin/ls"))
        calls = []
        monkeypatch.setattr(main.subprocess, "run", lambda args: calls.append(args))

        main.handle_external_programs("ls", [])

        assert calls == [["/usr/bin/ls"]]

    def test_runs_with_multiple_args(self, monkeypatch):
        monkeypatch.setattr(main, "find_command", lambda cmd: Path("/usr/bin/cp"))
        calls = []
        monkeypatch.setattr(main.subprocess, "run", lambda args: calls.append(args))

        main.handle_external_programs("cp", ["a.txt", "b.txt", "-v"])

        assert calls == [["/usr/bin/cp", "a.txt", "b.txt", "-v"]]


# ---------------------------------------------------------------------------
# handle_type
# ---------------------------------------------------------------------------

class TestHandleType:
    @pytest.mark.parametrize("builtin_cmd", sorted(main.BUILTINS))
    def test_reports_shell_builtin_for_each_builtin(self, builtin_cmd, capsys):
        main.handle_type(builtin_cmd)

        captured = capsys.readouterr()
        assert captured.out == f"{builtin_cmd} is a shell builtin\n"

    def test_reports_path_for_external_command(self, monkeypatch, capsys):
        monkeypatch.setattr(main, "find_command", lambda cmd: Path("/usr/bin/ls"))

        main.handle_type("ls")

        captured = capsys.readouterr()
        assert captured.out == "ls is /usr/bin/ls\n"

    def test_reports_not_found_for_unknown_command(self, monkeypatch, capsys):
        monkeypatch.setattr(main, "find_command", lambda cmd: None)

        main.handle_type("bogus")

        captured = capsys.readouterr()
        assert captured.out == "bogus: not found\n"

    def test_builtin_takes_precedence_over_path_lookup(self, monkeypatch, capsys):
        monkeypatch.setattr(main, "find_command", lambda cmd: Path("/usr/bin/echo"))

        main.handle_type("echo")

        captured = capsys.readouterr()
        assert captured.out == "echo is a shell builtin\n"


# ---------------------------------------------------------------------------
# handle_command
# ---------------------------------------------------------------------------

class TestHandleCommand:
    def test_echo_prints_joined_args(self, capsys):
        main.handle_command("echo", ["hello", "world"])

        captured = capsys.readouterr()
        assert captured.out == "hello world\n"

    def test_echo_with_no_args_prints_blank_line(self, capsys):
        main.handle_command("echo", [])

        captured = capsys.readouterr()
        assert captured.out == "\n"

    def test_type_delegates_to_handle_type_with_first_arg(self, monkeypatch):
        seen = []
        monkeypatch.setattr(main, "handle_type", lambda cmd: seen.append(cmd))

        main.handle_command("type", ["echo", "ignored_extra_arg"])

        assert seen == ["echo"]

    def test_unrecognized_command_delegates_to_external_programs(self, monkeypatch):
        seen = []
        monkeypatch.setattr(
            main, "handle_external_programs", lambda cmd, args: seen.append((cmd, args))
        )

        main.handle_command("ls", ["-la"])

        assert seen == [("ls", ["-la"])]

    def test_startswith_matching_is_prefix_based_not_exact(self, capsys):
        # cmd.startswith("echo") means any command beginning with "echo"
        # (e.g. "echoing") is routed to the echo branch, not just "echo" itself.
        main.handle_command("echoing", ["surprise"])

        captured = capsys.readouterr()
        assert captured.out == "surprise\n"


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

class TestMain:
    def test_exits_immediately_on_exit_command(self, monkeypatch, capsys):
        monkeypatch.setattr("builtins.input", lambda: "exit")
        calls = []
        monkeypatch.setattr(main, "handle_command", lambda cmd, args: calls.append((cmd, args)))

        main.main()

        assert calls == []
        assert capsys.readouterr().out == "$ "

    def test_processes_commands_until_exit(self, monkeypatch, capsys):
        inputs = iter(["echo hi", "type ls", "exit"])
        monkeypatch.setattr("builtins.input", lambda: next(inputs))
        calls = []
        monkeypatch.setattr(main, "handle_command", lambda cmd, args: calls.append((cmd, args)))

        main.main()

        assert calls == [("echo", ["hi"]), ("type", ["ls"])]

    def test_collapses_repeated_whitespace_between_args(self, monkeypatch):
        inputs = iter(["echo    hi     there", "exit"])
        monkeypatch.setattr("builtins.input", lambda: next(inputs))
        calls = []
        monkeypatch.setattr(main, "handle_command", lambda cmd, args: calls.append((cmd, args)))

        main.main()

        assert calls == [("echo", ["hi", "there"])]

    def test_empty_line_raises_indexerror(self, monkeypatch):
        # Known edge case/bug: an empty input line makes `line.split()` return
        # [], and `parts[0]` then raises IndexError instead of being handled.
        monkeypatch.setattr("builtins.input", lambda: "")

        with pytest.raises(IndexError):
            main.main()
