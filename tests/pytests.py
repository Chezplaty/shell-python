import os
import stat
from pathlib import Path

import pytest

from app import executor, main, path_utils, shell_builtins


def make_executable(path: Path) -> None:
    path.write_text("#!/bin/sh\necho hi\n")
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


# ---------------------------------------------------------------------------
# get_executable
# ---------------------------------------------------------------------------

class TestFindCommand:
    def test_returns_path_when_executable_found(self, tmp_path, monkeypatch):
        exe = tmp_path / "mycmd"
        make_executable(exe)
        monkeypatch.setenv("PATH", str(tmp_path))

        result = path_utils.get_executable("mycmd")

        assert result == exe

    def test_returns_none_when_not_found(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PATH", str(tmp_path))

        assert path_utils.get_executable("does_not_exist") is None

    def test_empty_path_returns_none(self, monkeypatch):
        monkeypatch.setenv("PATH", "")

        assert path_utils.get_executable("ls") is None

    def test_returns_first_match_in_path_order(self, tmp_path, monkeypatch):
        first_dir = tmp_path / "first"
        second_dir = tmp_path / "second"
        first_dir.mkdir()
        second_dir.mkdir()
        make_executable(first_dir / "mycmd")
        make_executable(second_dir / "mycmd")
        monkeypatch.setenv("PATH", os.pathsep.join([str(first_dir), str(second_dir)]))

        result = path_utils.get_executable("mycmd")

        assert result == first_dir / "mycmd"

    def test_file_exists_but_not_executable_is_skipped(self, tmp_path, monkeypatch):
        non_exec = tmp_path / "mycmd"
        non_exec.write_text("not executable")
        non_exec.chmod(stat.S_IREAD)
        monkeypatch.setenv("PATH", str(tmp_path))

        assert path_utils.get_executable("mycmd") is None


# ---------------------------------------------------------------------------
# handle_external_programs
# ---------------------------------------------------------------------------

class TestHandleExternalPrograms:
    def test_runs_command_when_found(self, monkeypatch):
        monkeypatch.setattr(executor, "get_executable", lambda cmd: Path("/usr/bin/ls"))
        calls = []
        monkeypatch.setattr(executor.subprocess, "run", lambda args: calls.append(args))

        executor.handle_external_programs("ls", ["-la"])

        assert calls == [["ls", "-la"]]

    def test_prints_not_found_when_missing(self, monkeypatch, capsys):
        monkeypatch.setattr(executor, "get_executable", lambda cmd: None)

        executor.handle_external_programs("nope", [])

        captured = capsys.readouterr()
        assert captured.out == "nope: command not found\n"

    def test_runs_with_no_args(self, monkeypatch):
        monkeypatch.setattr(executor, "get_executable", lambda cmd: Path("/usr/bin/ls"))
        calls = []
        monkeypatch.setattr(executor.subprocess, "run", lambda args: calls.append(args))

        executor.handle_external_programs("ls", [])

        assert calls == [["ls"]]

    def test_runs_with_multiple_args(self, monkeypatch):
        monkeypatch.setattr(executor, "get_executable", lambda cmd: Path("/usr/bin/cp"))
        calls = []
        monkeypatch.setattr(executor.subprocess, "run", lambda args: calls.append(args))

        executor.handle_external_programs("cp", ["a.txt", "b.txt", "-v"])

        assert calls == [["cp", "a.txt", "b.txt", "-v"]]


# ---------------------------------------------------------------------------
# handle_type
# ---------------------------------------------------------------------------

class TestHandleType:
    @pytest.mark.parametrize("builtin_cmd", sorted(shell_builtins.BUILTINS))
    def test_reports_shell_builtin_for_each_builtin(self, builtin_cmd, capsys):
        shell_builtins.handle_type([builtin_cmd])

        captured = capsys.readouterr()
        assert captured.out == f"{builtin_cmd} is a shell builtin\n"

    def test_reports_path_for_external_command(self, monkeypatch, capsys):
        monkeypatch.setattr(shell_builtins, "get_executable", lambda cmd: Path("/usr/bin/ls"))

        shell_builtins.handle_type(["ls"])

        captured = capsys.readouterr()
        assert captured.out == "ls is /usr/bin/ls\n"

    def test_reports_not_found_for_unknown_command(self, monkeypatch, capsys):
        monkeypatch.setattr(shell_builtins, "get_executable", lambda cmd: None)

        shell_builtins.handle_type(["bogus"])

        captured = capsys.readouterr()
        assert captured.out == "bogus: not found\n"

    def test_builtin_takes_precedence_over_path_lookup(self, monkeypatch, capsys):
        monkeypatch.setattr(shell_builtins, "get_executable", lambda cmd: Path("/usr/bin/echo"))

        shell_builtins.handle_type(["echo"])

        captured = capsys.readouterr()
        assert captured.out == "echo is a shell builtin\n"

    def test_loops_through_multiple_args_in_order(self, monkeypatch, capsys):
        monkeypatch.setattr(
            shell_builtins, "get_executable", lambda cmd: Path("/usr/bin/ls") if cmd == "ls" else None
        )

        shell_builtins.handle_type(["echo", "ls", "bogus"])

        captured = capsys.readouterr()
        assert captured.out == (
            "echo is a shell builtin\n"
            "ls is /usr/bin/ls\n"
            "bogus: not found\n"
        )


# ---------------------------------------------------------------------------
# handle_cd
# ---------------------------------------------------------------------------

class TestHandleCd:
    def test_changes_to_given_directory(self, monkeypatch):
        calls = []
        monkeypatch.setattr(os, "chdir", lambda path: calls.append(path))

        shell_builtins.handle_cd(["/some/dir"])

        assert calls == ["/some/dir"]

    def test_tilde_expands_to_home_directory(self, monkeypatch):
        home = Path("/home/user")
        monkeypatch.setattr(Path, "home", lambda: home)
        calls = []
        monkeypatch.setattr(os, "chdir", lambda path: calls.append(path))

        shell_builtins.handle_cd(["~"])

        assert calls == [home]

    def test_tilde_takes_precedence_over_matching_named_directory(self, monkeypatch):
        home = Path("/home/user")
        monkeypatch.setattr(Path, "home", lambda: home)
        calls = []
        monkeypatch.setattr(os, "chdir", lambda path: calls.append(path))

        shell_builtins.handle_cd(["~"])

        assert calls == [home]
        assert calls != ["~"]

    def test_prints_error_for_too_many_arguments(self, monkeypatch, capsys):
        monkeypatch.setattr(os, "chdir", lambda path: pytest.fail("should not chdir"))

        shell_builtins.handle_cd(["dir1", "dir2"])

        captured = capsys.readouterr()
        assert captured.out == "cd: too many arguments\n"

    def test_prints_error_when_directory_not_found(self, monkeypatch, capsys):
        def raise_not_found(path):
            raise FileNotFoundError

        monkeypatch.setattr(os, "chdir", raise_not_found)

        shell_builtins.handle_cd(["/does/not/exist"])

        captured = capsys.readouterr()
        assert captured.out == "cd: /does/not/exist: No such file or directory\n"

    def test_prints_error_when_path_is_not_a_directory(self, monkeypatch, capsys):
        def raise_not_a_directory(path):
            raise NotADirectoryError

        monkeypatch.setattr(os, "chdir", raise_not_a_directory)

        shell_builtins.handle_cd(["/some/file"])

        captured = capsys.readouterr()
        assert captured.out == "cd /some/file: Not a directory\n"

    def test_prints_error_when_permission_denied(self, monkeypatch, capsys):
        def raise_permission_error(path):
            raise PermissionError

        monkeypatch.setattr(os, "chdir", raise_permission_error)

        shell_builtins.handle_cd(["/locked"])

        captured = capsys.readouterr()
        assert captured.out == "cd: /locked: Permission denied\n"

    def test_bare_cd_with_no_arguments_changes_to_home_directory(self, monkeypatch):
        home = Path("/home/user")
        monkeypatch.setattr(Path, "home", lambda: home)
        calls = []
        monkeypatch.setattr(os, "chdir", lambda path: calls.append(path))

        shell_builtins.handle_cd([])

        assert calls == [home]


# ---------------------------------------------------------------------------
# handle_pwd
# ---------------------------------------------------------------------------

class TestHandlePwd:
    def test_prints_current_working_directory(self, monkeypatch, capsys, tmp_path):
        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)

        shell_builtins.handle_pwd([])

        captured = capsys.readouterr()
        assert captured.out == f"{tmp_path}\n"

    def test_prints_error_for_extra_arguments(self, monkeypatch, capsys, tmp_path):
        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)

        shell_builtins.handle_pwd(["extra"])

        captured = capsys.readouterr()
        assert captured.out == "pwd: too many arguments\n"

    def test_does_not_print_cwd_when_extra_arguments(self, monkeypatch, capsys, tmp_path):
        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)

        shell_builtins.handle_pwd(["extra", "args"])

        captured = capsys.readouterr()
        assert str(tmp_path) not in captured.out


# ---------------------------------------------------------------------------
# handle_command
# ---------------------------------------------------------------------------

class TestHandleCommand:
    def test_echo_prints_joined_args(self, capsys):
        executor.handle_command("echo", ["hello", "world"])

        captured = capsys.readouterr()
        assert captured.out == "hello world\n"

    def test_echo_with_no_args_prints_blank_line(self, capsys):
        executor.handle_command("echo", [])

        captured = capsys.readouterr()
        assert captured.out == "\n"

    def test_type_delegates_to_handle_type_with_all_args(self, monkeypatch):
        seen = []
        monkeypatch.setitem(shell_builtins.BUILTINS, "type", lambda args: seen.append(args))

        executor.handle_command("type", ["echo", "ls"])

        assert seen == [["echo", "ls"]]

    def test_unrecognized_command_delegates_to_external_programs(self, monkeypatch):
        seen = []
        monkeypatch.setattr(
            executor, "handle_external_programs", lambda cmd, args: seen.append((cmd, args))
        )

        executor.handle_command("ls", ["-la"])

        assert seen == [("ls", ["-la"])]

    def test_exact_match_required_not_prefix(self, capsys):
        executor.handle_command("echoing", ["surprise"])

        captured = capsys.readouterr()
        assert captured.out == "echoing: command not found\n"


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
