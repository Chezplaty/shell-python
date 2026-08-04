import os
import stat
import sys
from pathlib import Path

import pytest

from app import executor, main, path_utils, shell_builtins
from app.errors import BuiltinError
from app.lexer import Lexer, LexState, TokenType, finish_token
from app.parser import Instruction, Redirect
from app.redirects import resolve_redirect_targets, open_redirects, redirected_fds


def make_executable(path: Path) -> None:
    path.write_text("#!/bin/sh\necho hi\n")
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def make_instruction(cmd: str, args: list[str] | None = None, redirects: list | None = None) -> Instruction:
    return Instruction(cmd, args if args is not None else [], redirects if redirects is not None else [])


def token_values(tokens: list) -> list[str]:
    return [token.value for token in tokens]


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
        monkeypatch.setattr(executor.subprocess, "run", lambda args, **kwargs: calls.append((args, kwargs)))

        executor.handle_external_programs("ls", ["-la"], {})

        assert calls == [(["ls", "-la"], {"stdin": None, "stdout": None, "stderr": None})]

    def test_prints_not_found_when_missing(self, monkeypatch, capsys):
        monkeypatch.setattr(executor, "get_executable", lambda cmd: None)

        executor.handle_external_programs("nope", [], {})

        captured = capsys.readouterr()
        assert captured.out == "nope: command not found\n"

    def test_runs_with_no_args(self, monkeypatch):
        monkeypatch.setattr(executor, "get_executable", lambda cmd: Path("/usr/bin/ls"))
        calls = []
        monkeypatch.setattr(executor.subprocess, "run", lambda args, **kwargs: calls.append((args, kwargs)))

        executor.handle_external_programs("ls", [], {})

        assert calls == [(["ls"], {"stdin": None, "stdout": None, "stderr": None})]

    def test_runs_with_multiple_args(self, monkeypatch):
        monkeypatch.setattr(executor, "get_executable", lambda cmd: Path("/usr/bin/cp"))
        calls = []
        monkeypatch.setattr(executor.subprocess, "run", lambda args, **kwargs: calls.append((args, kwargs)))

        executor.handle_external_programs("cp", ["a.txt", "b.txt", "-v"], {})

        assert calls == [(["cp", "a.txt", "b.txt", "-v"], {"stdin": None, "stdout": None, "stderr": None})]

    def test_forwards_resolved_redirect_files_to_subprocess_run(self, monkeypatch):
        monkeypatch.setattr(executor, "get_executable", lambda cmd: Path("/usr/bin/cat"))
        calls = []
        monkeypatch.setattr(executor.subprocess, "run", lambda args, **kwargs: calls.append((args, kwargs)))
        stdout_file, stderr_file = object(), object()

        executor.handle_external_programs("cat", ["a.txt"], {1: stdout_file, 2: stderr_file})

        assert calls == [(["cat", "a.txt"], {"stdin": None, "stdout": stdout_file, "stderr": stderr_file})]


# ---------------------------------------------------------------------------
# handle_type
# ---------------------------------------------------------------------------

class TestHandleType:
    @pytest.mark.parametrize("builtin_cmd", sorted(shell_builtins.BUILTINS))
    def test_reports_shell_builtin_for_each_builtin(self, builtin_cmd, capsys):
        shell_builtins.handle_type(make_instruction("type", [builtin_cmd]))

        captured = capsys.readouterr()
        assert captured.out == f"{builtin_cmd} is a shell builtin\n"

    def test_reports_path_for_external_command(self, monkeypatch, capsys):
        monkeypatch.setattr(shell_builtins, "get_executable", lambda cmd: Path("/usr/bin/ls"))

        shell_builtins.handle_type(make_instruction("type", ["ls"]))

        captured = capsys.readouterr()
        assert captured.out == "ls is /usr/bin/ls\n"

    def test_reports_not_found_for_unknown_command(self, monkeypatch, capsys):
        monkeypatch.setattr(shell_builtins, "get_executable", lambda cmd: None)

        shell_builtins.handle_type(make_instruction("type", ["bogus"]))

        captured = capsys.readouterr()
        assert captured.out == "bogus: not found\n"

    def test_builtin_takes_precedence_over_path_lookup(self, monkeypatch, capsys):
        monkeypatch.setattr(shell_builtins, "get_executable", lambda cmd: Path("/usr/bin/echo"))

        shell_builtins.handle_type(make_instruction("type", ["echo"]))

        captured = capsys.readouterr()
        assert captured.out == "echo is a shell builtin\n"

    def test_loops_through_multiple_args_in_order(self, monkeypatch, capsys):
        monkeypatch.setattr(
            shell_builtins, "get_executable", lambda cmd: Path("/usr/bin/ls") if cmd == "ls" else None
        )

        shell_builtins.handle_type(make_instruction("type", ["echo", "ls", "bogus"]))

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

        shell_builtins.handle_cd(make_instruction("cd", ["/some/dir"]))

        assert calls == ["/some/dir"]

    def test_tilde_expands_to_home_directory(self, monkeypatch):
        home = Path("/home/user")
        monkeypatch.setattr(Path, "home", lambda: home)
        calls = []
        monkeypatch.setattr(os, "chdir", lambda path: calls.append(path))

        shell_builtins.handle_cd(make_instruction("cd", ["~"]))

        assert calls == [home]

    def test_tilde_takes_precedence_over_matching_named_directory(self, monkeypatch):
        home = Path("/home/user")
        monkeypatch.setattr(Path, "home", lambda: home)
        calls = []
        monkeypatch.setattr(os, "chdir", lambda path: calls.append(path))

        shell_builtins.handle_cd(make_instruction("cd", ["~"]))

        assert calls == [home]
        assert calls != ["~"]

    def test_raises_error_for_too_many_arguments(self, monkeypatch):
        monkeypatch.setattr(os, "chdir", lambda path: pytest.fail("should not chdir"))

        with pytest.raises(BuiltinError) as exc_info:
            shell_builtins.handle_cd(make_instruction("cd", ["dir1", "dir2"]))

        assert str(exc_info.value) == "cd: too many arguments"

    def test_raises_error_when_directory_not_found(self, monkeypatch):
        def raise_not_found(path):
            raise FileNotFoundError(2, "No such file or directory")

        monkeypatch.setattr(os, "chdir", raise_not_found)

        with pytest.raises(BuiltinError) as exc_info:
            shell_builtins.handle_cd(make_instruction("cd", ["/does/not/exist"]))

        assert str(exc_info.value) == "cd: /does/not/exist: No such file or directory"

    def test_raises_error_when_path_is_not_a_directory(self, monkeypatch):
        def raise_not_a_directory(path):
            raise NotADirectoryError(20, "Not a directory")

        monkeypatch.setattr(os, "chdir", raise_not_a_directory)

        with pytest.raises(BuiltinError) as exc_info:
            shell_builtins.handle_cd(make_instruction("cd", ["/some/file"]))

        assert str(exc_info.value) == "cd: /some/file: Not a directory"

    def test_raises_error_when_permission_denied(self, monkeypatch):
        def raise_permission_error(path):
            raise PermissionError(13, "Permission denied")

        monkeypatch.setattr(os, "chdir", raise_permission_error)

        with pytest.raises(BuiltinError) as exc_info:
            shell_builtins.handle_cd(make_instruction("cd", ["/locked"]))

        assert str(exc_info.value) == "cd: /locked: Permission denied"

    def test_bare_cd_with_no_arguments_changes_to_home_directory(self, monkeypatch):
        home = Path("/home/user")
        monkeypatch.setattr(Path, "home", lambda: home)
        calls = []
        monkeypatch.setattr(os, "chdir", lambda path: calls.append(path))

        shell_builtins.handle_cd(make_instruction("cd", []))

        assert calls == [home]


# ---------------------------------------------------------------------------
# handle_pwd
# ---------------------------------------------------------------------------

class TestHandlePwd:
    def test_prints_current_working_directory(self, monkeypatch, capsys, tmp_path):
        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)

        shell_builtins.handle_pwd(make_instruction("pwd", []))

        captured = capsys.readouterr()
        assert captured.out == f"{tmp_path}\n"

    def test_raises_error_for_extra_arguments(self, monkeypatch, tmp_path):
        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)

        with pytest.raises(BuiltinError) as exc_info:
            shell_builtins.handle_pwd(make_instruction("pwd", ["extra"]))

        assert str(exc_info.value) == "pwd: too many arguments"

    def test_does_not_print_cwd_when_extra_arguments(self, monkeypatch, capsys, tmp_path):
        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)

        with pytest.raises(BuiltinError):
            shell_builtins.handle_pwd(make_instruction("pwd", ["extra", "args"]))

        captured = capsys.readouterr()
        assert str(tmp_path) not in captured.out


# ---------------------------------------------------------------------------
# resolve_redirect_targets
# ---------------------------------------------------------------------------

class TestResolveRedirectTargets:
    def test_maps_overwrite_to_fd_1_in_write_mode(self, tmp_path):
        target = tmp_path / "out.md"
        instruction = make_instruction("echo", ["hi"], [Redirect(TokenType.REDIRECT_STDOUT, str(target))])

        assert resolve_redirect_targets(instruction) == {1: (str(target), "w")}

    def test_maps_redirect_stderr_to_fd_2_in_write_mode(self, tmp_path):
        target = tmp_path / "err.md"
        instruction = make_instruction("cat", [], [Redirect(TokenType.REDIRECT_STDERR, str(target))])

        assert resolve_redirect_targets(instruction) == {2: (str(target), "w")}

    def test_stdout_and_stderr_redirects_resolve_to_independent_targets(self, tmp_path):
        out = tmp_path / "out.md"
        err = tmp_path / "err.md"
        instruction = make_instruction(
            "cat",
            [],
            [Redirect(TokenType.REDIRECT_STDOUT, str(out)), Redirect(TokenType.REDIRECT_STDERR, str(err))],
        )

        assert resolve_redirect_targets(instruction) == {1: (str(out), "w"), 2: (str(err), "w")}

    def test_later_redirect_for_the_same_fd_overrides_the_earlier_one(self, tmp_path):
        first = tmp_path / "first.md"
        second = tmp_path / "second.md"
        instruction = make_instruction(
            "echo",
            ["hi"],
            [Redirect(TokenType.REDIRECT_STDOUT, str(first)), Redirect(TokenType.REDIRECT_STDOUT, str(second))],
        )

        assert resolve_redirect_targets(instruction) == {1: (str(second), "w")}

    def test_no_redirects_returns_an_empty_mapping(self, tmp_path):
        instruction = make_instruction("echo", ["hi"], [])

        assert resolve_redirect_targets(instruction) == {}

    def test_maps_append_stdout_to_fd_1_in_append_mode(self, tmp_path):
        target = tmp_path / "out.md"
        instruction = make_instruction("echo", ["hi"], [Redirect(TokenType.APPEND_STDOUT, str(target))])

        assert resolve_redirect_targets(instruction) == {1: (str(target), "a")}

    def test_append_stdout_after_overwrite_for_the_same_fd_overrides_it(self, tmp_path):
        target = tmp_path / "out.md"
        instruction = make_instruction(
            "echo",
            ["hi"],
            [Redirect(TokenType.REDIRECT_STDOUT, str(target)), Redirect(TokenType.APPEND_STDOUT, str(target))],
        )

        assert resolve_redirect_targets(instruction) == {1: (str(target), "a")}

    def test_maps_append_stderr_to_fd_2_in_append_mode(self, tmp_path):
        target = tmp_path / "err.md"
        instruction = make_instruction("cat", [], [Redirect(TokenType.APPEND_STDERR, str(target))])

        assert resolve_redirect_targets(instruction) == {2: (str(target), "a")}

    def test_append_stdout_and_append_stderr_resolve_to_independent_targets(self, tmp_path):
        out = tmp_path / "out.md"
        err = tmp_path / "err.md"
        instruction = make_instruction(
            "cat",
            [],
            [Redirect(TokenType.APPEND_STDOUT, str(out)), Redirect(TokenType.APPEND_STDERR, str(err))],
        )

        assert resolve_redirect_targets(instruction) == {1: (str(out), "a"), 2: (str(err), "a")}

    def test_append_stderr_after_overwrite_for_the_same_fd_overrides_it(self, tmp_path):
        target = tmp_path / "err.md"
        instruction = make_instruction(
            "cat",
            [],
            [Redirect(TokenType.REDIRECT_STDERR, str(target)), Redirect(TokenType.APPEND_STDERR, str(target))],
        )

        assert resolve_redirect_targets(instruction) == {2: (str(target), "a")}


# ---------------------------------------------------------------------------
# open_redirects
# ---------------------------------------------------------------------------

class TestOpenRedirects:
    def test_creates_file_when_it_does_not_exist(self, tmp_path):
        target = tmp_path / "out.md"
        instruction = make_instruction("echo", ["hello", "world"], [Redirect(TokenType.REDIRECT_STDOUT, str(target))])

        with open_redirects(instruction) as files:
            assert target.exists()
            assert set(files) == {1}

    def test_overwrite_mode_lets_the_caller_truncate_existing_content(self, tmp_path):
        target = tmp_path / "out.md"
        target.write_text("old content that is much longer than the new content")
        instruction = make_instruction("echo", ["new"], [Redirect(TokenType.REDIRECT_STDOUT, str(target))])

        with open_redirects(instruction) as files:
            files[1].write("new")

        assert target.read_text() == "new"

    def test_stdout_and_stderr_redirects_open_to_their_own_targets(self, tmp_path):
        out = tmp_path / "out.md"
        err = tmp_path / "err.md"
        instruction = make_instruction(
            "cat",
            [],
            [Redirect(TokenType.REDIRECT_STDOUT, str(out)), Redirect(TokenType.REDIRECT_STDERR, str(err))],
        )

        with open_redirects(instruction) as files:
            files[1].write("stdout content")
            files[2].write("stderr content")

        assert out.read_text() == "stdout content"
        assert err.read_text() == "stderr content"

    def test_closes_opened_files_once_the_block_exits(self, tmp_path):
        target = tmp_path / "out.md"
        instruction = make_instruction("echo", ["hi"], [Redirect(TokenType.REDIRECT_STDOUT, str(target))])

        with open_redirects(instruction) as files:
            opened_file = files[1]

        assert opened_file.closed

    def test_does_nothing_when_there_are_no_redirects(self, tmp_path):
        instruction = make_instruction("echo", ["hi"], [])

        with open_redirects(instruction) as files:
            assert files == {}

    def test_raises_builtin_error_when_parent_directory_is_missing(self, tmp_path):
        target = tmp_path / "missing_dir" / "out.md"
        instruction = make_instruction("echo", ["hi"], [Redirect(TokenType.REDIRECT_STDOUT, str(target))])

        with pytest.raises(BuiltinError) as exc_info:
            with open_redirects(instruction):
                pass

        assert str(exc_info.value) == f"echo: {target}: No such file or directory"

    def test_raises_builtin_error_when_target_is_a_directory(self, tmp_path):
        target = tmp_path / "a_directory"
        target.mkdir()
        instruction = make_instruction("echo", ["hi"], [Redirect(TokenType.REDIRECT_STDOUT, str(target))])

        with pytest.raises(BuiltinError) as exc_info:
            with open_redirects(instruction):
                pass

        assert str(exc_info.value) == f"echo: {target}: Is a directory"

    @pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses file permission checks")
    def test_raises_builtin_error_when_permission_denied(self, tmp_path):
        locked_dir = tmp_path / "locked"
        locked_dir.mkdir()
        locked_dir.chmod(0o500)
        target = locked_dir / "out.md"
        instruction = make_instruction("echo", ["hi"], [Redirect(TokenType.REDIRECT_STDOUT, str(target))])

        try:
            with pytest.raises(BuiltinError) as exc_info:
                with open_redirects(instruction):
                    pass
            assert str(exc_info.value) == f"echo: {target}: Permission denied"
        finally:
            locked_dir.chmod(0o700)

    def test_error_message_uses_the_instructions_own_cmd(self, tmp_path):
        target = tmp_path / "missing_dir" / "out.md"
        instruction = make_instruction("cat", [], [Redirect(TokenType.REDIRECT_STDOUT, str(target))])

        with pytest.raises(BuiltinError) as exc_info:
            with open_redirects(instruction):
                pass

        assert str(exc_info.value).startswith("cat:")

    def test_does_not_create_parent_directories_when_redirect_fails(self, tmp_path):
        target = tmp_path / "missing_dir" / "out.md"
        instruction = make_instruction("echo", ["hi"], [Redirect(TokenType.REDIRECT_STDOUT, str(target))])

        with pytest.raises(BuiltinError):
            with open_redirects(instruction):
                pass

        assert not target.parent.exists()

    def test_append_mode_creates_file_when_it_does_not_exist(self, tmp_path):
        target = tmp_path / "out.md"
        instruction = make_instruction("echo", ["hi"], [Redirect(TokenType.APPEND_STDOUT, str(target))])

        with open_redirects(instruction) as files:
            assert target.exists()
            assert set(files) == {1}

    def test_append_mode_preserves_existing_content_and_writes_after_it(self, tmp_path):
        target = tmp_path / "out.md"
        target.write_text("existing\n")
        instruction = make_instruction("echo", ["new"], [Redirect(TokenType.APPEND_STDOUT, str(target))])

        with open_redirects(instruction) as files:
            files[1].write("new\n")

        assert target.read_text() == "existing\nnew\n"

    def test_append_stderr_mode_creates_file_when_it_does_not_exist(self, tmp_path):
        target = tmp_path / "err.md"
        instruction = make_instruction("cat", [], [Redirect(TokenType.APPEND_STDERR, str(target))])

        with open_redirects(instruction) as files:
            assert target.exists()
            assert set(files) == {2}

    def test_append_stderr_mode_preserves_existing_content_and_writes_after_it(self, tmp_path):
        target = tmp_path / "err.md"
        target.write_text("existing error\n")
        instruction = make_instruction("cat", [], [Redirect(TokenType.APPEND_STDERR, str(target))])

        with open_redirects(instruction) as files:
            files[2].write("new error\n")

        assert target.read_text() == "existing error\nnew error\n"


# ---------------------------------------------------------------------------
# redirected_fds
# ---------------------------------------------------------------------------

class TestRedirectedFds:
    def test_no_redirects_is_a_no_op(self, capsys):
        with redirected_fds({}):
            print("hi")

        assert capsys.readouterr().out == "hi\n"

    def test_print_lands_in_the_redirected_file_instead_of_stdout(self, tmp_path, capfd):
        # capfd.disabled() hands fd 1 back to the real terminal for this block.
        # Without it, pytest's own capture already owns fd 1 through a separate
        # duplicated descriptor, so our dup2 swap wouldn't affect where
        # sys.stdout's writes actually land.
        target = tmp_path / "out.md"

        with capfd.disabled():
            with open(target, "w") as f:
                with redirected_fds({1: f}):
                    print("hi")

        assert target.read_text() == "hi\n"

    def test_fd_1_is_restored_to_its_original_target_after_the_block(self, tmp_path):
        target = tmp_path / "out.md"
        before = os.fstat(1)

        with open(target, "w") as f:
            with redirected_fds({1: f}):
                during = os.fstat(1)

        after = os.fstat(1)

        assert (during.st_dev, during.st_ino) == (os.stat(target).st_dev, os.stat(target).st_ino)
        assert (during.st_dev, during.st_ino) != (before.st_dev, before.st_ino)
        assert (after.st_dev, after.st_ino) == (before.st_dev, before.st_ino)

    def test_stdout_and_stderr_are_redirected_independently(self, tmp_path, capfd):
        out = tmp_path / "out.md"
        err = tmp_path / "err.md"

        with capfd.disabled():
            with open(out, "w") as out_file, open(err, "w") as err_file:
                with redirected_fds({1: out_file, 2: err_file}):
                    print("stdout line")
                    print("stderr line", file=sys.stderr)

        assert out.read_text() == "stdout line\n"
        assert err.read_text() == "stderr line\n"


# ---------------------------------------------------------------------------
# handle_command
# ---------------------------------------------------------------------------

class TestHandleCommand:
    def test_echo_prints_joined_args(self, capsys):
        executor.handle_command(make_instruction("echo", ["hello", "world"]))

        captured = capsys.readouterr()
        assert captured.out == "hello world\n"

    def test_echo_with_no_args_prints_blank_line(self, capsys):
        executor.handle_command(make_instruction("echo", []))

        captured = capsys.readouterr()
        assert captured.out == "\n"

    def test_type_delegates_to_handle_type_with_all_args(self, monkeypatch):
        seen = []
        monkeypatch.setitem(shell_builtins.BUILTINS, "type", lambda instruction: seen.append(instruction.args))

        executor.handle_command(make_instruction("type", ["echo", "ls"]))

        assert seen == [["echo", "ls"]]

    def test_unrecognized_command_delegates_to_external_programs(self, monkeypatch):
        seen = []
        monkeypatch.setattr(
            executor, "handle_external_programs", lambda cmd, args, files: seen.append((cmd, args, files))
        )

        executor.handle_command(make_instruction("ls", ["-la"]))

        assert seen == [("ls", ["-la"], {})]

    def test_echo_redirected_to_a_file_writes_there_instead_of_stdout(self, capfd, tmp_path):
        target = tmp_path / "out.md"

        with capfd.disabled():
            executor.handle_command(
                make_instruction("echo", ["hello", "world"], [Redirect(TokenType.REDIRECT_STDOUT, str(target))])
            )

        assert target.read_text() == "hello world\n"

    def test_external_command_stderr_redirect_leaves_stdout_untouched(self, monkeypatch, tmp_path):
        target = tmp_path / "err.md"
        monkeypatch.setattr(executor, "get_executable", lambda cmd: Path("/usr/bin/cat"))
        calls = []
        monkeypatch.setattr(executor.subprocess, "run", lambda args, **kwargs: calls.append(kwargs))

        executor.handle_command(
            make_instruction("cat", ["missing"], [Redirect(TokenType.REDIRECT_STDERR, str(target))])
        )

        assert calls[0]["stdout"] is None
        assert calls[0]["stderr"].name == str(target)

    def test_exact_match_required_not_prefix(self, capsys):
        executor.handle_command(make_instruction("echoing", ["surprise"]))

        captured = capsys.readouterr()
        assert captured.out == "echoing: command not found\n"


# ---------------------------------------------------------------------------
# finish_token
# ---------------------------------------------------------------------------

class TestFinishToken:
    def test_appends_joined_current_to_tokens(self):
        tokens = []
        current = ["h", "i"]

        finish_token(tokens, current)

        assert token_values(tokens) == ["hi"]

    def test_clears_current_after_appending(self):
        tokens = []
        current = ["h", "i"]

        finish_token(tokens, current)

        assert current == []

    def test_does_nothing_when_current_is_empty(self):
        tokens = ["existing"]
        current = []

        finish_token(tokens, current)

        assert tokens == ["existing"]

    def test_preserves_existing_tokens_when_appending(self):
        tokens = ["echo"]
        current = ["h", "i"]

        finish_token(tokens, current)

        assert tokens[0] == "echo"
        assert token_values(tokens[1:]) == ["hi"]


# ---------------------------------------------------------------------------
# Lexer.disable_escape
# ---------------------------------------------------------------------------

class TestDisableEscape:
    def test_sets_escaping_to_false(self):
        lexer = Lexer()
        lexer._escaping = True

        lexer.disable_escape()

        assert lexer._escaping is False

    def test_is_a_no_op_when_already_off(self):
        lexer = Lexer()

        lexer.disable_escape()

        assert lexer._escaping is False


# ---------------------------------------------------------------------------
# Lexer.handle_normal
# ---------------------------------------------------------------------------

class TestHandleNormal:
    def test_appends_ordinary_character_to_current(self):
        lexer = Lexer()

        lexer.handle_normal("a")

        assert lexer._current == ["a"]

    def test_whitespace_finishes_current_token(self):
        lexer = Lexer()
        lexer._current = ["h", "i"]

        lexer.handle_normal(" ")

        assert token_values(lexer._tokens) == ["hi"]
        assert lexer._current == []

    def test_whitespace_with_empty_current_does_not_add_empty_token(self):
        lexer = Lexer()

        lexer.handle_normal(" ")

        assert lexer._tokens == []

    def test_single_quote_switches_state_to_single(self):
        lexer = Lexer()

        lexer.handle_normal("'")

        assert lexer._state == LexState.SINGLE
        assert lexer._current == []

    def test_double_quote_switches_state_to_double(self):
        lexer = Lexer()

        lexer.handle_normal('"')

        assert lexer._state == LexState.DOUBLE
        assert lexer._current == []

    def test_backslash_turns_on_escaping_without_appending(self):
        lexer = Lexer()

        lexer.handle_normal("\\")

        assert lexer._escaping is True
        assert lexer._current == []

    def test_escaping_appends_char_literally_and_turns_escaping_off(self):
        lexer = Lexer()
        lexer._escaping = True

        lexer.handle_normal(" ")

        assert lexer._current == [" "]
        assert lexer._escaping is False

    def test_escaping_treats_quote_characters_as_literal(self):
        lexer = Lexer()
        lexer._escaping = True

        lexer.handle_normal("'")

        assert lexer._current == ["'"]
        assert lexer._state == LexState.NORMAL


# ---------------------------------------------------------------------------
# Lexer.handle_single
# ---------------------------------------------------------------------------

class TestHandleSingle:
    def test_appends_ordinary_character_to_current(self):
        lexer = Lexer()

        lexer.handle_single("a")

        assert lexer._current == ["a"]

    def test_single_quote_switches_state_back_to_normal(self):
        lexer = Lexer()
        lexer._state = LexState.SINGLE

        lexer.handle_single("'")

        assert lexer._state == LexState.NORMAL
        assert lexer._current == []

    def test_backslash_is_appended_literally(self):
        lexer = Lexer()

        lexer.handle_single("\\")

        assert lexer._current == ["\\"]

    def test_double_quote_is_appended_literally(self):
        lexer = Lexer()

        lexer.handle_single('"')

        assert lexer._current == ['"']


# ---------------------------------------------------------------------------
# Lexer.handle_double
# ---------------------------------------------------------------------------

class TestHandleDouble:
    def test_appends_ordinary_character_to_current(self):
        lexer = Lexer()

        lexer.handle_double("a")

        assert lexer._current == ["a"]

    def test_double_quote_switches_state_back_to_normal(self):
        lexer = Lexer()
        lexer._state = LexState.DOUBLE

        lexer.handle_double('"')

        assert lexer._state == LexState.NORMAL
        assert lexer._current == []

    def test_backslash_turns_on_escaping_without_appending(self):
        lexer = Lexer()

        lexer.handle_double("\\")

        assert lexer._escaping is True
        assert lexer._current == []

    def test_single_quote_has_no_special_meaning(self):
        lexer = Lexer()
        lexer._state = LexState.DOUBLE

        lexer.handle_double("'")

        assert lexer._current == ["'"]
        assert lexer._state == LexState.DOUBLE

    @pytest.mark.parametrize("special_char", sorted(Lexer.DOUBLE_ESCAPES))
    def test_escaping_a_special_character_drops_the_backslash(self, special_char):
        lexer = Lexer()
        lexer._escaping = True

        lexer.handle_double(special_char)

        assert lexer._current == [special_char]
        assert lexer._escaping is False

    def test_escaping_an_ordinary_character_keeps_the_backslash(self):
        lexer = Lexer()
        lexer._escaping = True

        lexer.handle_double("a")

        assert lexer._current == ["\\", "a"]
        assert lexer._escaping is False


# ---------------------------------------------------------------------------
# Lexer.tokenize
# ---------------------------------------------------------------------------

class TestTokenize:
    def test_splits_on_single_space(self):
        assert token_values(Lexer().tokenize("echo hello")) == ["echo", "hello"]

    def test_collapses_repeated_whitespace(self):
        assert token_values(Lexer().tokenize("echo    hi     there")) == ["echo", "hi", "there"]

    def test_ignores_leading_and_trailing_whitespace(self):
        assert token_values(Lexer().tokenize("  echo hi  ")) == ["echo", "hi"]

    def test_empty_line_returns_empty_list(self):
        assert Lexer().tokenize("") == []

    def test_whitespace_only_line_returns_empty_list(self):
        assert Lexer().tokenize("   ") == []

    def test_single_quotes_preserve_spaces_between_words(self):
        assert token_values(Lexer().tokenize("echo 'shell hello'")) == ["echo", "shell hello"]

    def test_single_quotes_preserve_repeated_internal_whitespace(self):
        assert token_values(Lexer().tokenize("echo 'world     test'")) == ["echo", "world     test"]

    def test_multiple_single_quoted_arguments(self):
        result = token_values(Lexer().tokenize("cat '/tmp/file name' '/tmp/file name with spaces'"))

        assert result == ["cat", "/tmp/file name", "/tmp/file name with spaces"]

    def test_single_quotes_can_produce_empty_argument(self):
        assert token_values(Lexer().tokenize("echo ''")) == ["echo"]

    def test_single_quoted_argument_alone(self):
        assert token_values(Lexer().tokenize("'hello world'")) == ["hello world"]

    def test_mixes_quoted_and_unquoted_arguments(self):
        result = token_values(Lexer().tokenize("echo hello 'shell world' again"))

        assert result == ["echo", "hello", "shell world", "again"]

    def test_double_quotes_preserve_spaces_between_words(self):
        assert token_values(Lexer().tokenize('echo "shell hello"')) == ["echo", "shell hello"]

    def test_double_quotes_preserve_repeated_internal_whitespace(self):
        assert token_values(Lexer().tokenize('echo "world     test"')) == ["echo", "world     test"]

    def test_multiple_double_quoted_arguments(self):
        result = token_values(Lexer().tokenize('cat "/tmp/file name" "/tmp/file name with spaces"'))

        assert result == ["cat", "/tmp/file name", "/tmp/file name with spaces"]

    def test_double_quotes_can_produce_empty_argument(self):
        assert token_values(Lexer().tokenize('echo ""')) == ["echo"]

    def test_double_quoted_argument_alone(self):
        assert token_values(Lexer().tokenize('"hello world"')) == ["hello world"]

    def test_mixes_double_quoted_and_unquoted_arguments(self):
        result = token_values(Lexer().tokenize('echo hello "shell world" again'))

        assert result == ["echo", "hello", "shell world", "again"]

    def test_double_quotes_preserve_single_quote_inside(self):
        result = token_values(Lexer().tokenize("""echo "bar"  "shell's"  "foo" """))

        assert result == ["echo", "bar", "shell's", "foo"]

    def test_double_quotes_escaped_double_quote_is_literal(self):
        result = token_values(Lexer().tokenize('echo "say \\"hi\\""'))

        assert result == ["echo", 'say "hi"']

    def test_double_quotes_escaped_backslash_is_single_literal_backslash(self):
        result = token_values(Lexer().tokenize('echo "a\\\\b"'))

        assert result == ["echo", "a\\b"]

    def test_double_quotes_escaped_dollar_sign_is_literal(self):
        result = token_values(Lexer().tokenize('echo "\\$HOME"'))

        assert result == ["echo", "$HOME"]

    def test_double_quotes_escaped_backtick_is_literal(self):
        result = token_values(Lexer().tokenize('echo "\\`cmd\\`"'))

        assert result == ["echo", "`cmd`"]

    def test_double_quotes_escaped_newline_is_literal(self):
        result = token_values(Lexer().tokenize('echo "a\\\nb"'))

        assert result == ["echo", "a\nb"]

    def test_double_quotes_escapes_multiple_special_characters_in_sequence(self):
        line = 'echo "' + '\\$' + '\\`' + '\\"' + '\\\\' + '"'
        result = token_values(Lexer().tokenize(line))

        assert result == ["echo", '$`"\\']

    def test_double_quotes_escaped_ordinary_character_keeps_backslash(self):
        # 'a' is not a special character, so the backslash is preserved
        # literally alongside it rather than being consumed as an escape.
        result = token_values(Lexer().tokenize('echo "\\a"'))

        assert result == ["echo", "\\a"]

    def test_double_quotes_escaped_single_quote_keeps_backslash_since_not_special(self):
        # A single quote has no meaning inside double quotes, so it isn't in
        # the special-character set and the backslash before it is literal.
        result = token_values(Lexer().tokenize('echo "\\\'"'))

        assert result == ["echo", "\\'"]

    def test_double_quotes_unterminated_escape_at_end_is_dropped(self):
        # Mirrors the trailing-lone-backslash behavior outside quotes:
        # escaping is set but the string ends before a char arrives to apply
        # it to, so the backslash silently disappears.
        line = 'echo "abc' + '\\'
        result = token_values(Lexer().tokenize(line))

        assert result == ["echo", "abc"]

    def test_single_quotes_preserve_backslashes_literally(self):
        result = token_values(Lexer().tokenize(r"echo 'multiple\\slashes'"))

        assert result == ["echo", "multiple\\\\slashes"]

    def test_backslash_escapes_a_following_space_into_a_literal_space(self):
        result = token_values(Lexer().tokenize(r"echo multiple\ \ \ \ spaces"))

        assert result == ["echo", "multiple    spaces"]

    def test_backslash_escapes_quote_characters_outside_quotes(self):
        result = token_values(Lexer().tokenize("echo \\'\\\"literal quotes\\\"\\'"))

        assert result == ["echo", "'\"literal", "quotes\"'"]

    def test_backslash_before_ordinary_character_just_drops_the_backslash(self):
        assert token_values(Lexer().tokenize(r"echo ignore\_backslash")) == ["echo", "ignore_backslash"]

    def test_backslash_escaped_backslash_produces_a_single_literal_backslash(self):
        result = token_values(Lexer().tokenize(r"cat /tmp/\_ignored_1 /tmp/ignore_\2 /tmp/just_one_\\_3"))

        assert result == [
            "cat",
            "/tmp/_ignored_1",
            "/tmp/ignore_2",
            "/tmp/just_one_\\_3",
        ]

    def test_trailing_lone_backslash_is_dropped(self):
        # Known edge case: a backslash as the final character sets BACKSLASH
        # state but the loop ends before another char arrives, so it's never
        # appended anywhere and silently disappears.
        assert token_values(Lexer().tokenize("echo test\\")) == ["echo", "test"]


# ---------------------------------------------------------------------------
# Tab-completion for builtins: find_insertion_point / get_candidates
# ---------------------------------------------------------------------------

class TestFindInsertionPoint:
    def test_returns_index_of_matching_builtin(self):
        assert main.find_insertion_point("echo") == main.BUILTINS.index("echo")

    def test_returns_index_where_a_missing_prefix_would_be_inserted(self):
        # "ex" sorts between "echo" and "exit" in the builtin list.
        assert main.find_insertion_point("ex") == main.BUILTINS.index("exit")

    def test_empty_prefix_returns_zero(self):
        assert main.find_insertion_point("") == 0

    def test_prefix_sorting_after_every_builtin_returns_list_length(self):
        assert main.find_insertion_point("zzz") == len(main.BUILTINS)


class TestGetCandidates:
    def test_unique_prefix_returns_single_match(self):
        assert main.get_candidates("ech") == ["echo"]

    def test_shared_prefix_returns_all_matches_in_sorted_order(self):
        assert main.get_candidates("e") == ["echo", "exit"]

    def test_no_matching_builtin_returns_empty_list(self):
        assert main.get_candidates("zz") == []

    def test_prefix_equal_to_a_full_builtin_name_matches_it(self):
        assert main.get_candidates("cd") == ["cd"]

    def test_empty_prefix_returns_every_builtin(self):
        assert main.get_candidates("") == main.BUILTINS


# ---------------------------------------------------------------------------
# Tab-completion for builtins: redraw / autocomplete
# ---------------------------------------------------------------------------

class TestRedraw:
    def test_writes_clear_line_then_prompt_and_output(self, capsys):
        main.redraw("echo")

        assert capsys.readouterr().out == "\r\033[2K$ echo"

    def test_writes_bare_prompt_for_empty_output(self, capsys):
        main.redraw("")

        assert capsys.readouterr().out == "\r\033[2K$ "


class TestAutocomplete:
    def test_unique_prefix_completes_in_place(self, capsys):
        buffer = list("ech")

        result = main.autocomplete(buffer)

        assert result == ["echo"]
        assert buffer == ["echo"]

    def test_shared_prefix_completes_to_the_first_match_alphabetically(self, capsys):
        buffer = list("e")

        result = main.autocomplete(buffer)

        assert result == ["echo"]

    def test_completion_redraws_the_line_with_the_full_word(self, capsys):
        buffer = list("ech")

        main.autocomplete(buffer)

        assert capsys.readouterr().out == "\r\033[2K$ echo"

    def test_no_match_rings_the_bell(self, capsys):
        buffer = list("zzz")

        main.autocomplete(buffer)

        assert capsys.readouterr().out == "\x07"

    def test_no_match_leaves_the_buffer_unchanged(self, capsys):
        buffer = list("zzz")

        result = main.autocomplete(buffer)

        assert result == list("zzz")
        assert buffer == list("zzz")

    def test_no_match_does_not_redraw_the_line(self, capsys):
        buffer = list("zzz")

        main.autocomplete(buffer)

        assert "\033[2K" not in capsys.readouterr().out


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

class TestMain:
    def test_exits_immediately_on_exit_command(self, monkeypatch, capsys):
        monkeypatch.setattr(main, "line_editor", lambda: "exit")
        calls = []
        monkeypatch.setattr(
            main, "handle_command", lambda instruction: calls.append((instruction.cmd, instruction.args))
        )

        main.main()

        assert calls == []
        assert capsys.readouterr().out == "$ "

    def test_processes_commands_until_exit(self, monkeypatch, capsys):
        inputs = iter(["echo hi", "type ls", "exit"])
        monkeypatch.setattr(main, "line_editor", lambda: next(inputs))
        calls = []
        monkeypatch.setattr(
            main, "handle_command", lambda instruction: calls.append((instruction.cmd, instruction.args))
        )

        main.main()

        assert calls == [("echo", ["hi"]), ("type", ["ls"])]

    def test_collapses_repeated_whitespace_between_args(self, monkeypatch):
        inputs = iter(["echo    hi     there", "exit"])
        monkeypatch.setattr(main, "line_editor", lambda: next(inputs))
        calls = []
        monkeypatch.setattr(
            main, "handle_command", lambda instruction: calls.append((instruction.cmd, instruction.args))
        )

        main.main()

        assert calls == [("echo", ["hi", "there"])]

    def test_empty_line_produces_empty_command_without_crashing(self, monkeypatch):
        # Previously an empty line crashed with IndexError (line.split()[0] on
        # an empty list). The lexer/parser refactor fixed this: tokenize("")
        # returns no tokens, and parse() only reads tokens[0] inside the loop
        # guard, so an empty line now parses to an empty, harmless command.
        inputs = iter(["", "exit"])
        monkeypatch.setattr(main, "line_editor", lambda: next(inputs))
        calls = []
        monkeypatch.setattr(
            main, "handle_command", lambda instruction: calls.append((instruction.cmd, instruction.args))
        )

        main.main()

        assert calls == [("", [])]
