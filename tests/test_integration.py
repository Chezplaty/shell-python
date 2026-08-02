"""
End-to-end tests that spawn the shell as a real subprocess and drive it
through stdin/stdout, mirroring how the CodeCrafters tester exercises each
stage (pwd, running programs, locating executables, type, echo, exit, the
REPL loop, invalid commands, and the prompt).

Unlike pytests.py (which calls functions in app.main directly), these tests
treat the shell as a black box: they never import app.main.
"""

import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def make_executable(path: Path, body: str) -> None:
    path.write_text(body)
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def run_shell(commands: list[str], cwd: Path = REPO_ROOT, env: dict | None = None, timeout: float = 10):
    """
    Runs the shell as a subprocess, feeding it `commands` one per line
    (a trailing "exit" is required to terminate the REPL), and returns
    (stdout, returncode).
    """
    stdin_text = "\n".join(commands) + "\n"
    run_env = {**(env if env is not None else os.environ)}
    run_env["PYTHONPATH"] = str(REPO_ROOT)
    proc = subprocess.Popen(
        [sys.executable, "-m", "app.main"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=cwd,
        env=run_env,
    )
    out, _ = proc.communicate(stdin_text, timeout=timeout)
    return out, proc.returncode


# ---------------------------------------------------------------------------
# #EI0 - Navigation: the pwd builtin
# ---------------------------------------------------------------------------

class TestPwdBuiltin:
    def test_type_pwd_reports_shell_builtin(self):
        out, _ = run_shell(["type pwd", "exit"])

        assert "pwd is a shell builtin\n" in out

    def test_pwd_prints_current_working_directory(self, tmp_path):
        out, _ = run_shell(["pwd", "exit"], cwd=tmp_path)

        assert f"$ {tmp_path}\n" in out


# ---------------------------------------------------------------------------
# Navigation: the cd builtin
# ---------------------------------------------------------------------------

class TestCdBuiltin:
    def test_type_cd_reports_shell_builtin(self):
        out, _ = run_shell(["type cd", "exit"])

        assert "cd is a shell builtin\n" in out

    def test_cd_to_absolute_path_changes_directory(self, tmp_path):
        target = tmp_path / "nested"
        target.mkdir()

        out, _ = run_shell([f"cd {target}", "pwd", "exit"], cwd=tmp_path)

        assert f"$ {target}\n" in out

    def test_cd_to_relative_path_changes_directory(self, tmp_path):
        (tmp_path / "nested").mkdir()

        out, _ = run_shell(["cd nested", "pwd", "exit"], cwd=tmp_path)

        assert f"$ {tmp_path / 'nested'}\n" in out

    def test_cd_to_parent_directory_with_dotdot(self, tmp_path):
        nested = tmp_path / "nested"
        nested.mkdir()

        out, _ = run_shell(["cd ..", "pwd", "exit"], cwd=nested)

        assert f"$ {tmp_path}\n" in out

    def test_cd_nonexistent_path_prints_error(self, tmp_path):
        missing = tmp_path / "does_not_exist"

        out, _ = run_shell([f"cd {missing}", "exit"], cwd=tmp_path)

        assert f"cd: {missing}: No such file or directory\n" in out

    def test_cd_into_a_file_prints_not_a_directory_error(self, tmp_path):
        file_path = tmp_path / "just_a_file"
        file_path.write_text("not a directory")

        out, _ = run_shell([f"cd {file_path}", "exit"], cwd=tmp_path)

        assert f"cd: {file_path}: Not a directory\n" in out

    @pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses directory permission checks")
    def test_cd_into_unreadable_directory_prints_permission_denied(self, tmp_path):
        locked = tmp_path / "locked"
        locked.mkdir()
        locked.chmod(0)

        try:
            out, _ = run_shell([f"cd {locked}", "exit"], cwd=tmp_path)
        finally:
            locked.chmod(0o700)

        assert f"cd: {locked}: Permission denied\n" in out

    def test_cd_with_too_many_arguments_prints_error(self, tmp_path):
        (tmp_path / "nested").mkdir()

        out, _ = run_shell(["cd nested extra_arg", "exit"], cwd=tmp_path)

        assert "cd: too many arguments\n" in out

    def test_cd_tilde_changes_to_home_directory(self, tmp_path):
        home = tmp_path / "home"
        home.mkdir()
        env = {**os.environ, "HOME": str(home)}

        out, _ = run_shell(["cd ~", "pwd", "exit"], cwd=tmp_path, env=env)

        assert f"$ {home}\n" in out


# ---------------------------------------------------------------------------
# #IP1 - Run a program
# ---------------------------------------------------------------------------

class TestRunProgram:
    def test_runs_external_program_with_single_arg(self, tmp_path):
        bin_dir = tmp_path / "fox"
        bin_dir.mkdir()
        make_executable(
            bin_dir / "custom_exe_9492",
            "#!/bin/sh\necho \"Program was passed $(($# + 1)) args (including program name).\"\n"
            "echo \"Arg #0 (program name): $(basename \"$0\")\"\n"
            "i=1\nfor a in \"$@\"; do echo \"Arg #$i: $a\"; i=$((i+1)); done\n",
        )
        env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"}

        out, _ = run_shell(["custom_exe_9492 Alice", "exit"], env=env)

        assert "Program was passed 2 args (including program name).\n" in out
        assert "Arg #0 (program name): custom_exe_9492\n" in out
        assert "Arg #1: Alice\n" in out

    def test_runs_external_program_with_multiple_args(self, tmp_path):
        bin_dir = tmp_path / "fox"
        bin_dir.mkdir()
        make_executable(
            bin_dir / "custom_exe_1588",
            "#!/bin/sh\necho \"Program was passed $(($# + 1)) args (including program name).\"\n"
            "echo \"Arg #0 (program name): $(basename \"$0\")\"\n"
            "i=1\nfor a in \"$@\"; do echo \"Arg #$i: $a\"; i=$((i+1)); done\n",
        )
        env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"}

        out, _ = run_shell(["custom_exe_1588 Alice James", "exit"], env=env)

        assert "Program was passed 3 args (including program name).\n" in out
        assert "Arg #0 (program name): custom_exe_1588\n" in out
        assert "Arg #1: Alice\n" in out
        assert "Arg #2: James\n" in out

    def test_runs_executable_named_with_spaces_via_single_quotes(self, tmp_path):
        bin_dir = tmp_path / "fox"
        bin_dir.mkdir()
        make_executable(
            bin_dir / "my program",
            "#!/bin/sh\necho \"ran with arg: $1\"\n",
        )
        env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"}

        out, _ = run_shell(["'my program' argument1", "exit"], env=env)

        assert "ran with arg: argument1\n" in out

    def test_runs_executable_named_with_spaces_via_double_quotes(self, tmp_path):
        bin_dir = tmp_path / "fox"
        bin_dir.mkdir()
        make_executable(
            bin_dir / "exe with spaces",
            "#!/bin/sh\necho \"ran with arg: $1\"\n",
        )
        env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"}

        out, _ = run_shell(['"exe with spaces" file.txt', "exit"], env=env)

        assert "ran with arg: file.txt\n" in out

    def test_runs_executable_named_with_spaces_via_backslash_escapes(self, tmp_path):
        bin_dir = tmp_path / "fox"
        bin_dir.mkdir()
        make_executable(
            bin_dir / "backslash program",
            "#!/bin/sh\necho \"ran with arg: $1\"\n",
        )
        env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"}

        out, _ = run_shell([r"backslash\ program argument1", "exit"], env=env)

        assert "ran with arg: argument1\n" in out


# ---------------------------------------------------------------------------
# #MG5 - Locate executable files
# ---------------------------------------------------------------------------

class TestLocateExecutableFiles:
    def test_type_resolves_to_first_executable_match_in_path_order(self, tmp_path):
        fox_dir, dog_dir, owl_dir = tmp_path / "fox", tmp_path / "dog", tmp_path / "owl"
        for d in (fox_dir, dog_dir, owl_dir):
            d.mkdir()

        (fox_dir / "my_exe").write_text("not executable")
        (owl_dir / "my_exe").write_text("not executable")
        make_executable(dog_dir / "my_exe", "#!/bin/sh\necho hi\n")

        env = {
            **os.environ,
            "PATH": os.pathsep.join([str(owl_dir), str(dog_dir), str(fox_dir)]),
        }

        out, _ = run_shell(["type my_exe", "exit"], env=env)

        assert f"my_exe is {dog_dir / 'my_exe'}\n" in out

    def test_type_reports_not_found_for_unknown_commands(self, tmp_path):
        env = {**os.environ, "PATH": str(tmp_path)}

        out, _ = run_shell(
            ["type invalid_apple_command", "type invalid_blueberry_command", "exit"],
            env=env,
        )

        assert "invalid_apple_command: not found\n" in out
        assert "invalid_blueberry_command: not found\n" in out


# ---------------------------------------------------------------------------
# #EZ5 - Implement type
# ---------------------------------------------------------------------------

class TestImplementType:
    def test_reports_shell_builtin_for_each_builtin(self):
        out, _ = run_shell(["type echo", "type exit", "type type", "exit"])

        assert "echo is a shell builtin\n" in out
        assert "exit is a shell builtin\n" in out
        assert "type is a shell builtin\n" in out

    def test_reports_not_found_for_invalid_commands(self, tmp_path):
        env = {**os.environ, "PATH": str(tmp_path)}

        out, _ = run_shell(
            ["type invalid_pineapple_command", "type invalid_orange_command", "exit"],
            env=env,
        )

        assert "invalid_pineapple_command: not found\n" in out
        assert "invalid_orange_command: not found\n" in out

    def test_reports_on_multiple_commands_in_a_single_call(self, tmp_path):
        env = {**os.environ, "PATH": str(tmp_path)}

        out, _ = run_shell(["type echo invalid_grape_command cd", "exit"], env=env)

        assert "echo is a shell builtin\n" in out
        assert "invalid_grape_command: not found\n" in out
        assert "cd is a shell builtin\n" in out


# ---------------------------------------------------------------------------
# #IZ3 - Implement echo
# ---------------------------------------------------------------------------

class TestImplementEcho:
    def test_echoes_back_multiple_words(self):
        out, _ = run_shell(["echo raspberry pear", "echo mango strawberry apple", "exit"])

        assert "raspberry pear\n" in out
        assert "mango strawberry apple\n" in out


# ---------------------------------------------------------------------------
# Single-quote parsing
# ---------------------------------------------------------------------------

class TestSingleQuoteParsing:
    def test_echo_preserves_spaces_inside_single_quotes(self):
        out, _ = run_shell(["echo 'shell hello'", "exit"])

        assert "shell hello\n" in out

    def test_echo_preserves_repeated_internal_whitespace(self):
        out, _ = run_shell(["echo 'world     test'", "exit"])

        assert "world     test\n" in out

    def test_cat_reads_multiple_quoted_paths_with_spaces(self, tmp_path):
        file1 = tmp_path / "file name"
        file2 = tmp_path / "file name with spaces"
        file1.write_text("content1 ")
        file2.write_text("content2")

        out, _ = run_shell([f"cat '{file1}' '{file2}'", "exit"], cwd=tmp_path)

        assert "content1 content2" in out

    def test_mixes_quoted_and_unquoted_arguments(self):
        out, _ = run_shell(["echo hello 'shell world' again", "exit"])

        assert "hello shell world again\n" in out


# ---------------------------------------------------------------------------
# Double-quote parsing
# ---------------------------------------------------------------------------

class TestDoubleQuoteParsing:
    def test_echo_preserves_spaces_inside_double_quotes(self):
        out, _ = run_shell(['echo "shell hello"', "exit"])

        assert "shell hello\n" in out

    def test_echo_preserves_repeated_internal_whitespace(self):
        out, _ = run_shell(['echo "world     test"', "exit"])

        assert "world     test\n" in out

    def test_cat_reads_multiple_quoted_paths_with_spaces(self, tmp_path):
        file1 = tmp_path / "file name"
        file2 = tmp_path / "file name with spaces"
        file1.write_text("content1 ")
        file2.write_text("content2")

        out, _ = run_shell([f'cat "{file1}" "{file2}"', "exit"], cwd=tmp_path)

        assert "content1 content2" in out

    def test_mixes_quoted_and_unquoted_arguments(self):
        out, _ = run_shell(['echo hello "shell world" again', "exit"])

        assert "hello shell world again\n" in out

    def test_escaped_double_quote_is_literal(self):
        out, _ = run_shell(['echo "say \\"hi\\""', "exit"])

        assert 'say "hi"\n' in out


# ---------------------------------------------------------------------------
# Backslash parsing (outside quotes)
# ---------------------------------------------------------------------------

class TestBackslashParsing:
    def test_escapes_a_following_space_into_a_literal_space(self):
        out, _ = run_shell([r"echo multiple\ \ \ \ spaces", "exit"])

        assert "multiple    spaces\n" in out

    def test_before_ordinary_character_drops_the_backslash(self):
        out, _ = run_shell([r"echo ignore\_backslash", "exit"])

        assert "ignore_backslash\n" in out

    def test_escaped_backslash_produces_a_single_literal_backslash(self):
        out, _ = run_shell([r"echo just_one_\\_slash", "exit"])

        assert "just_one_\\_slash\n" in out


# ---------------------------------------------------------------------------
# #PN5 - Implement exit
# ---------------------------------------------------------------------------

class TestImplementExit:
    def test_exits_cleanly_with_no_output_after_exit_command(self, tmp_path):
        env = {**os.environ, "PATH": str(tmp_path)}

        out, returncode = run_shell(["invalid_pear_command", "exit"], env=env)

        assert "invalid_pear_command: command not found\n" in out
        assert out.endswith("$ ")
        assert returncode == 0


# ---------------------------------------------------------------------------
# #FF0 - Implement a REPL
# ---------------------------------------------------------------------------

class TestReplLoop:
    def test_handles_a_sequence_of_invalid_commands(self, tmp_path):
        env = {**os.environ, "PATH": str(tmp_path)}
        commands = [f"invalid_command_{i}" for i in range(1, 5)]

        out, _ = run_shell([*commands, "exit"], env=env)

        for i in range(1, 5):
            assert f"invalid_command_{i}: command not found\n" in out


# ---------------------------------------------------------------------------
# #CZ2 - Handle invalid commands
# ---------------------------------------------------------------------------

class TestHandleInvalidCommands:
    def test_reports_command_not_found(self, tmp_path):
        env = {**os.environ, "PATH": str(tmp_path)}

        out, _ = run_shell(["invalid_apple_command", "exit"], env=env)

        assert "invalid_apple_command: command not found\n" in out


# ---------------------------------------------------------------------------
# Output redirection: the > and 1> operators
# ---------------------------------------------------------------------------

class TestOutputRedirection:
    def test_gt_redirects_output_to_file_instead_of_terminal(self, tmp_path):
        target = tmp_path / "foo.md"

        out, _ = run_shell([f"echo Hello James > {target}", "exit"], cwd=tmp_path)

        assert target.read_text() == "Hello James\n"
        assert "Hello James" not in out

    def test_1gt_behaves_identically_to_gt(self, tmp_path):
        target = tmp_path / "foo.md"

        out, _ = run_shell([f"echo Hello James 1> {target}", "exit"], cwd=tmp_path)

        assert target.read_text() == "Hello James\n"
        assert "Hello James" not in out

    def test_creates_the_target_file_when_it_does_not_exist(self, tmp_path):
        target = tmp_path / "new_file.md"
        assert not target.exists()

        run_shell([f"echo created > {target}", "exit"], cwd=tmp_path)

        assert target.read_text() == "created\n"

    def test_overwrites_an_existing_files_content(self, tmp_path):
        target = tmp_path / "existing.md"
        target.write_text("stale content that should be fully replaced")

        run_shell([f"echo fresh > {target}", "exit"], cwd=tmp_path)

        assert target.read_text() == "fresh\n"

    def test_target_path_can_be_quoted_with_spaces(self, tmp_path):
        target = tmp_path / "file with spaces.md"

        run_shell([f'echo hi > "{target}"', "exit"], cwd=tmp_path)

        assert target.read_text() == "hi\n"

    def test_redirect_failure_prints_error_to_terminal_and_writes_no_file(self, tmp_path):
        missing_dir_target = tmp_path / "does_not_exist" / "out.md"

        out, _ = run_shell([f"echo hi > {missing_dir_target}", "exit"], cwd=tmp_path)

        assert f"echo: {missing_dir_target}: No such file or directory\n" in out
        assert not missing_dir_target.parent.exists()

    def test_missing_redirect_target_is_a_parse_error(self, tmp_path):
        out, _ = run_shell(["echo hi >", "exit"], cwd=tmp_path)

        assert "shell: parse error near '\\n'\n" in out


# ---------------------------------------------------------------------------
# Output redirection: the 2> operator
# ---------------------------------------------------------------------------

class TestStderrRedirection:
    def test_2gt_redirects_an_external_commands_stderr_to_file(self, tmp_path):
        existing = tmp_path / "existing_file"
        existing.write_text("line one\n")
        errors = tmp_path / "errors.txt"

        out, _ = run_shell(
            [f"cat {existing} nonexistent 2> {errors}", "exit"], cwd=tmp_path
        )

        assert "line one\n" in out
        assert "No such file or directory" not in out
        assert "nonexistent: No such file or directory" in errors.read_text()

    def test_stdout_and_stderr_can_be_redirected_to_different_files_in_one_command(self, tmp_path):
        existing = tmp_path / "existing_file"
        existing.write_text("line one\n")
        stdout_file = tmp_path / "out.txt"
        errors = tmp_path / "errors.txt"

        out, _ = run_shell(
            [f"cat {existing} nonexistent > {stdout_file} 2> {errors}", "exit"], cwd=tmp_path
        )

        assert "line one" not in out
        assert "No such file or directory" not in out
        assert stdout_file.read_text() == "line one\n"
        assert "nonexistent: No such file or directory" in errors.read_text()


# ---------------------------------------------------------------------------
# #OO8 - Print a prompt
# ---------------------------------------------------------------------------

class TestPrintPrompt:
    def test_prints_prompt_before_reading_input(self):
        out, returncode = run_shell(["exit"])

        assert out == "$ "
        assert returncode == 0
