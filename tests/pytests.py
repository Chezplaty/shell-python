import os
import stat
from pathlib import Path

import pytest

from app import executor, main, path_utils, shell_builtins
from app.lexer import Lexer, LexState, finish_token


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
# finish_token
# ---------------------------------------------------------------------------

class TestFinishToken:
    def test_appends_joined_current_to_tokens(self):
        tokens = []
        current = ["h", "i"]

        finish_token(tokens, current)

        assert tokens == ["hi"]

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

        assert tokens == ["echo", "hi"]


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

        assert lexer._tokens == ["hi"]
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
        assert Lexer().tokenize("echo hello") == ["echo", "hello"]

    def test_collapses_repeated_whitespace(self):
        assert Lexer().tokenize("echo    hi     there") == ["echo", "hi", "there"]

    def test_ignores_leading_and_trailing_whitespace(self):
        assert Lexer().tokenize("  echo hi  ") == ["echo", "hi"]

    def test_empty_line_returns_empty_list(self):
        assert Lexer().tokenize("") == []

    def test_whitespace_only_line_returns_empty_list(self):
        assert Lexer().tokenize("   ") == []

    def test_single_quotes_preserve_spaces_between_words(self):
        assert Lexer().tokenize("echo 'shell hello'") == ["echo", "shell hello"]

    def test_single_quotes_preserve_repeated_internal_whitespace(self):
        assert Lexer().tokenize("echo 'world     test'") == ["echo", "world     test"]

    def test_multiple_single_quoted_arguments(self):
        result = Lexer().tokenize("cat '/tmp/file name' '/tmp/file name with spaces'")

        assert result == ["cat", "/tmp/file name", "/tmp/file name with spaces"]

    def test_single_quotes_can_produce_empty_argument(self):
        assert Lexer().tokenize("echo ''") == ["echo"]

    def test_single_quoted_argument_alone(self):
        assert Lexer().tokenize("'hello world'") == ["hello world"]

    def test_mixes_quoted_and_unquoted_arguments(self):
        result = Lexer().tokenize("echo hello 'shell world' again")

        assert result == ["echo", "hello", "shell world", "again"]

    def test_double_quotes_preserve_spaces_between_words(self):
        assert Lexer().tokenize('echo "shell hello"') == ["echo", "shell hello"]

    def test_double_quotes_preserve_repeated_internal_whitespace(self):
        assert Lexer().tokenize('echo "world     test"') == ["echo", "world     test"]

    def test_multiple_double_quoted_arguments(self):
        result = Lexer().tokenize('cat "/tmp/file name" "/tmp/file name with spaces"')

        assert result == ["cat", "/tmp/file name", "/tmp/file name with spaces"]

    def test_double_quotes_can_produce_empty_argument(self):
        assert Lexer().tokenize('echo ""') == ["echo"]

    def test_double_quoted_argument_alone(self):
        assert Lexer().tokenize('"hello world"') == ["hello world"]

    def test_mixes_double_quoted_and_unquoted_arguments(self):
        result = Lexer().tokenize('echo hello "shell world" again')

        assert result == ["echo", "hello", "shell world", "again"]

    def test_double_quotes_preserve_single_quote_inside(self):
        result = Lexer().tokenize("""echo "bar"  "shell's"  "foo" """)

        assert result == ["echo", "bar", "shell's", "foo"]

    def test_double_quotes_escaped_double_quote_is_literal(self):
        result = Lexer().tokenize('echo "say \\"hi\\""')

        assert result == ["echo", 'say "hi"']

    def test_double_quotes_escaped_backslash_is_single_literal_backslash(self):
        result = Lexer().tokenize('echo "a\\\\b"')

        assert result == ["echo", "a\\b"]

    def test_double_quotes_escaped_dollar_sign_is_literal(self):
        result = Lexer().tokenize('echo "\\$HOME"')

        assert result == ["echo", "$HOME"]

    def test_double_quotes_escaped_backtick_is_literal(self):
        result = Lexer().tokenize('echo "\\`cmd\\`"')

        assert result == ["echo", "`cmd`"]

    def test_double_quotes_escaped_newline_is_literal(self):
        result = Lexer().tokenize('echo "a\\\nb"')

        assert result == ["echo", "a\nb"]

    def test_double_quotes_escapes_multiple_special_characters_in_sequence(self):
        line = 'echo "' + '\\$' + '\\`' + '\\"' + '\\\\' + '"'
        result = Lexer().tokenize(line)

        assert result == ["echo", '$`"\\']

    def test_double_quotes_escaped_ordinary_character_keeps_backslash(self):
        # 'a' is not a special character, so the backslash is preserved
        # literally alongside it rather than being consumed as an escape.
        result = Lexer().tokenize('echo "\\a"')

        assert result == ["echo", "\\a"]

    def test_double_quotes_escaped_single_quote_keeps_backslash_since_not_special(self):
        # A single quote has no meaning inside double quotes, so it isn't in
        # the special-character set and the backslash before it is literal.
        result = Lexer().tokenize('echo "\\\'"')

        assert result == ["echo", "\\'"]

    def test_double_quotes_unterminated_escape_at_end_is_dropped(self):
        # Mirrors the trailing-lone-backslash behavior outside quotes:
        # escaping is set but the string ends before a char arrives to apply
        # it to, so the backslash silently disappears.
        line = 'echo "abc' + '\\'
        result = Lexer().tokenize(line)

        assert result == ["echo", "abc"]

    def test_single_quotes_preserve_backslashes_literally(self):
        result = Lexer().tokenize(r"echo 'multiple\\slashes'")

        assert result == ["echo", "multiple\\\\slashes"]

    def test_backslash_escapes_a_following_space_into_a_literal_space(self):
        result = Lexer().tokenize(r"echo multiple\ \ \ \ spaces")

        assert result == ["echo", "multiple    spaces"]

    def test_backslash_escapes_quote_characters_outside_quotes(self):
        result = Lexer().tokenize("echo \\'\\\"literal quotes\\\"\\'")

        assert result == ["echo", "'\"literal", "quotes\"'"]

    def test_backslash_before_ordinary_character_just_drops_the_backslash(self):
        assert Lexer().tokenize(r"echo ignore\_backslash") == ["echo", "ignore_backslash"]

    def test_backslash_escaped_backslash_produces_a_single_literal_backslash(self):
        result = Lexer().tokenize(r"cat /tmp/\_ignored_1 /tmp/ignore_\2 /tmp/just_one_\\_3")

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
        assert Lexer().tokenize("echo test\\") == ["echo", "test"]


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
