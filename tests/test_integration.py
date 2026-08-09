"""
End-to-end tests that spawn the shell as a real subprocess and drive it
through stdin/stdout, mirroring how the CodeCrafters tester exercises each
stage (pwd, running programs, locating executables, type, echo, exit, the
REPL loop, invalid commands, and the prompt).

Unlike pytests.py (which calls functions in app.main directly), these tests
treat the shell as a black box: they never import app.main.
"""

import os
import pty
import select
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def make_executable(path: Path, body: str) -> None:
    path.write_text(body)
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


PROMPT = "$ "


class _PtyShell:
    """
    Drives app.main over a pseudo-terminal, one line at a time, only writing
    the next line once the shell's prompt has reappeared.

    main.py's line editor puts stdin into cbreak mode via tty.setcbreak(fd)
    (and later restores it via termios.tcsetattr), both using TCSAFLUSH -
    which discards any input sitting unread in the terminal's buffer at that
    exact moment. Writing every line up front races those flushes and
    silently loses whatever hadn't been read yet, so instead each line is
    held back until the shell has actually finished reading and processing
    the previous one.
    """

    def __init__(self, cwd: Path, env: dict | None, timeout: float):
        run_env = {**(env if env is not None else os.environ)}
        run_env["PYTHONPATH"] = str(REPO_ROOT)

        self.master_fd, slave_fd = pty.openpty()
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "app.main"],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            cwd=cwd,
            env=run_env,
        )
        os.close(slave_fd)

        self.output = b""
        self.deadline = time.monotonic() + timeout

    def _read_more(self) -> bool:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"timed out; output so far: {self.output!r}")

        ready, _, _ = select.select([self.master_fd], [], [], remaining)
        if not ready:
            return True

        try:
            chunk = os.read(self.master_fd, 4096)
        except OSError:
            return False
        if not chunk:
            return False

        self.output += chunk
        return True

    def wait_for_prompt(self) -> bool:
        """Blocks until output *newly arrived since this call started* ends with the prompt."""
        baseline = len(self.output)
        while len(self.output) <= baseline or not self.output[baseline:].decode(errors="replace").endswith(PROMPT):
            if not self._read_more():
                return False
        return True

    def send_line(self, line: str) -> None:
        # main.py's line editor calls tty.setcbreak(fd) (TCSAFLUSH) once per
        # line, right after printing "$ " but before it starts reading. That
        # call discards any input that arrived before it runs, so writing
        # the instant the prompt is observed races it: verified empirically
        # to fail intermittently with no delay, and to succeed reliably
        # (15/15 trials) with this one.
        time.sleep(0.01)
        os.write(self.master_fd, (line + "\n").encode())

    def drain(self) -> None:
        while self._read_more():
            pass
        self.proc.wait(timeout=max(self.deadline - time.monotonic(), 0.1))

    def close(self) -> None:
        # Belt-and-suspenders: if the process is still alive here (a timeout,
        # an assertion error mid-test, anything that skipped drain()'s clean
        # wait), kill it outright. Closing master_fd alone sends the child's
        # stdin to EOF, but main.py's line_editor() doesn't check for EOF on
        # read() - it spins in a tight loop appending "" forever instead of
        # exiting, which leaks a 100%-CPU orphan process if we don't kill it.
        if self.proc.poll() is None:
            self.proc.kill()
            self.proc.wait(timeout=5)
        os.close(self.master_fd)


def run_shell(commands: list[str], cwd: Path = REPO_ROOT, env: dict | None = None, timeout: float = 10):
    """
    Runs the shell as a subprocess, feeding it `commands` one per line
    (a trailing "exit" is required to terminate the REPL), and returns
    (stdout, returncode).
    """
    shell = _PtyShell(cwd, env, timeout)
    try:
        for command in commands:
            if not shell.wait_for_prompt():
                break
            shell.send_line(command)
        shell.drain()
        # The pty's line discipline translates outgoing "\n" to "\r\n" (normal
        # terminal output processing), which isn't something the shell itself
        # is doing. Undo it so assertions can keep comparing against plain
        # "\n" as before. This leaves bare "\r" (e.g. clear_candidates'
        # "\r" cursor-to-column-0 reset) untouched.
        out = shell.output.decode(errors="replace").replace("\r\n", "\n")
        return out, shell.proc.returncode
    finally:
        shell.close()


# ---------------------------------------------------------------------------
# #EI0 - Navigation: the pwd builtin
# ---------------------------------------------------------------------------

class TestPwdBuiltin:
    def test_type_pwd_reports_shell_builtin(self):
        out, _ = run_shell(["type pwd", "exit"])

        assert "pwd is a shell builtin\n" in out

    def test_pwd_prints_current_working_directory(self, tmp_path):
        out, _ = run_shell(["pwd", "exit"], cwd=tmp_path)

        # The prompt is followed by the echoed "pwd" command text before
        # pwd's own printed output, so the path no longer immediately
        # follows "$ " the way it would with silent (non-echoing) input.
        assert f"\n{tmp_path}\n" in out


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

        assert f"\n{target}\n" in out

    def test_cd_to_relative_path_changes_directory(self, tmp_path):
        (tmp_path / "nested").mkdir()

        out, _ = run_shell(["cd nested", "pwd", "exit"], cwd=tmp_path)

        assert f"\n{tmp_path / 'nested'}\n" in out

    def test_cd_to_parent_directory_with_dotdot(self, tmp_path):
        nested = tmp_path / "nested"
        nested.mkdir()

        out, _ = run_shell(["cd ..", "pwd", "exit"], cwd=nested)

        assert f"\n{tmp_path}\n" in out

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

        assert f"\n{home}\n" in out


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
        # main() breaks out of the loop as soon as "exit" is parsed, before
        # printing another prompt, so the transcript ends with the echoed
        # "exit" line rather than a bare "$ ".
        assert out.endswith("$ exit\n")
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
        # "Hello James" is echoed as part of the typed command line itself
        # (e.g. "echo Hello James > foo.md"), so check it doesn't ALSO show
        # up as echo's own printed result on its own line.
        assert "\nHello James\n" not in out

    def test_1gt_behaves_identically_to_gt(self, tmp_path):
        target = tmp_path / "foo.md"

        out, _ = run_shell([f"echo Hello James 1> {target}", "exit"], cwd=tmp_path)

        assert target.read_text() == "Hello James\n"
        assert "\nHello James\n" not in out

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
# Output redirection: the >> and 1>> operators
# ---------------------------------------------------------------------------

class TestAppendStdoutRedirection:
    def test_gtgt_creates_the_target_file_when_it_does_not_exist(self, tmp_path):
        target = tmp_path / "bar.md"
        (tmp_path / "baz").mkdir()
        (tmp_path / "baz" / "apple").write_text("")
        (tmp_path / "baz" / "banana").write_text("")
        (tmp_path / "baz" / "blueberry").write_text("")

        out, _ = run_shell([f"ls {tmp_path / 'baz'} >> {target}", "exit"], cwd=tmp_path)

        assert target.read_text() == "apple\nbanana\nblueberry\n"
        assert "apple" not in out

    def test_1gtgt_appends_across_multiple_invocations_instead_of_overwriting(self, tmp_path):
        target = tmp_path / "baz.md"

        out, _ = run_shell(
            [f"echo Hello Emily 1>> {target}", f"echo Hello Maria 1>> {target}", "exit"], cwd=tmp_path
        )

        assert target.read_text() == "Hello Emily\nHello Maria\n"
        assert "\nHello Emily\n" not in out
        assert "\nHello Maria\n" not in out

    def test_gtgt_appends_after_content_written_by_a_prior_overwrite_redirect(self, tmp_path):
        target = tmp_path / "qux.md"
        (tmp_path / "baz").mkdir()
        (tmp_path / "baz" / "apple").write_text("")
        (tmp_path / "baz" / "banana").write_text("")
        (tmp_path / "baz" / "blueberry").write_text("")

        run_shell(
            [f"echo List of files: > {target}", f"ls {tmp_path / 'baz'} >> {target}", "exit"], cwd=tmp_path
        )

        assert target.read_text() == "List of files:\napple\nbanana\nblueberry\n"

    def test_gtgt_does_not_truncate_existing_file_content(self, tmp_path):
        target = tmp_path / "existing.md"
        target.write_text("original content\n")

        run_shell([f"echo appended >> {target}", "exit"], cwd=tmp_path)

        assert target.read_text() == "original content\nappended\n"

    def test_gtgt_redirect_failure_prints_error_to_terminal_and_writes_no_file(self, tmp_path):
        missing_dir_target = tmp_path / "does_not_exist" / "out.md"

        out, _ = run_shell([f"echo hi >> {missing_dir_target}", "exit"], cwd=tmp_path)

        assert f"echo: {missing_dir_target}: No such file or directory\n" in out
        assert not missing_dir_target.parent.exists()


# ---------------------------------------------------------------------------
# Output redirection: the 2> operator
# ---------------------------------------------------------------------------

class TestAppendStderrRedirection:
    def test_gtgt_only_redirects_stdout_so_stderr_still_prints_to_terminal(self, tmp_path):
        target = tmp_path / "baz.md"

        out, _ = run_shell([f"ls nonexistent >> {target}", "exit"], cwd=tmp_path)

        assert "ls: nonexistent: No such file or directory" in out
        assert not target.exists() or target.read_text() == ""

    def test_2gtgt_redirects_stderr_to_file_instead_of_terminal(self, tmp_path):
        target = tmp_path / "qux.md"

        out, _ = run_shell([f"ls nonexistent 2>> {target}", "exit"], cwd=tmp_path)

        assert "No such file or directory" not in out
        assert "ls: nonexistent: No such file or directory" in target.read_text()

    def test_2gtgt_leaves_stdout_untouched(self, tmp_path):
        target = tmp_path / "quz.md"

        out, _ = run_shell([f"echo James says Error 2>> {target}", "exit"], cwd=tmp_path)

        assert "James says Error\n" in out

    def test_2gtgt_appends_across_multiple_invocations_instead_of_overwriting(self, tmp_path):
        target = tmp_path / "quz.md"

        out, _ = run_shell(
            [f"cat nonexistent 2>> {target}", f"ls nonexistent 2>> {target}", "exit"], cwd=tmp_path
        )

        assert "No such file or directory" not in out
        assert target.read_text() == (
            "cat: nonexistent: No such file or directory\n"
            "ls: nonexistent: No such file or directory\n"
        )

    def test_2gtgt_does_not_truncate_existing_file_content(self, tmp_path):
        target = tmp_path / "existing.md"
        target.write_text("original content\n")

        run_shell([f"cat nonexistent 2>> {target}", "exit"], cwd=tmp_path)

        assert target.read_text() == "original content\ncat: nonexistent: No such file or directory\n"

    def test_2gtgt_redirect_failure_prints_error_to_terminal_and_writes_no_file(self, tmp_path):
        missing_dir_target = tmp_path / "does_not_exist" / "err.md"

        out, _ = run_shell([f"cat nonexistent 2>> {missing_dir_target}", "exit"], cwd=tmp_path)

        assert f"cat: {missing_dir_target}: No such file or directory\n" in out
        assert not missing_dir_target.parent.exists()

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

        # "exit" itself is echoed back by the line editor, so the transcript
        # is the prompt followed by the echoed command, not a bare "$ ".
        assert out == "$ exit\n"
        assert returncode == 0


# ---------------------------------------------------------------------------
# Tab autocompletion for builtins
# ---------------------------------------------------------------------------

class TestTabAutocompletion:
    def test_tab_completes_a_unique_prefix_and_runs_the_completed_command(self):
        # Types "ec", presses Tab (completing to "echo"), then types " hi"
        # and Enter - so the executed command is "echo hi", not "ec hi".
        out, _ = run_shell(["ec\t hi", "exit"])

        # A unique match still bells (see handle_tab's cursor-creation
        # branch) even though it completes immediately with no list shown.
        assert "\x07\033[2D\033[0Kecho" in out
        assert "hi\n" in out

    def test_tab_with_no_matching_builtin_rings_the_bell_and_leaves_the_buffer_untouched(self):
        out, _ = run_shell(["zzzcmd\t", "exit"])

        assert "\x07" in out
        assert "zzzcmd: command not found\n" in out

    def test_tab_with_multiple_matches_shows_list_on_first_tab_then_completes_on_second(self, tmp_path):
        # Both "echo" and "exit" start with "e"; get_candidates returns them
        # sorted. The first Tab only lists the candidates (see
        # TestTabCandidateList for that in detail); the second Tab is what
        # completes to the first match alphabetically ("echo", not "exit").
        # PATH is pinned to an empty directory so no other "e"-prefixed
        # executable from the real PATH can interfere with the ordering.
        env = {**os.environ, "PATH": str(tmp_path)}

        out, returncode = run_shell(["e\t\t", "exit"], env=env)

        assert "\033[1D\033[0Kecho" in out
        assert returncode == 0

    def test_tab_cycles_through_multiple_matches_and_wraps_around(self, tmp_path):
        # Types "e" then presses Tab four times: the first Tab only lists
        # "echo"/"exit" without completing, so the completion cycle itself
        # is echo -> exit -> back to echo across taps 2-4. PATH is pinned to
        # an empty directory so only the builtins are candidates.
        env = {**os.environ, "PATH": str(tmp_path)}

        out, returncode = run_shell(["e\t\t\t\t", "exit"], env=env)

        # Each redraw's move-back distance changes across taps (it erases
        # whatever's currently displayed, not the original "e"), so match on
        # the erase+write marker common to every redraw call instead.
        echo_redraw = "\033[0Kecho"
        exit_redraw = "\033[0Kexit"
        first_echo = out.find(echo_redraw)
        exit_at = out.find(exit_redraw)
        second_echo = out.find(echo_redraw, first_echo + 1)

        assert -1 not in (first_echo, exit_at, second_echo)
        assert first_echo < exit_at < second_echo
        assert returncode == 0


# ---------------------------------------------------------------------------
# Tab autocompletion for custom PATH executables (compile_choices)
# ---------------------------------------------------------------------------

class TestTabAutocompletionForPathExecutables:
    def test_tab_completes_a_custom_executable_found_on_path(self, tmp_path):
        bin_dir = tmp_path / "fox"
        bin_dir.mkdir()
        make_executable(bin_dir / "custom_exe_9492", "#!/bin/sh\necho hi\n")
        env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"}

        out, returncode = run_shell(["custom_exe_94\t", "exit"], env=env)

        assert "\033[13D\033[0Kcustom_exe_9492" in out
        assert returncode == 0


# ---------------------------------------------------------------------------
# Tab autocompletion: candidate list display/clear for multiple matches
# ---------------------------------------------------------------------------

class TestTabCandidateList:
    def test_first_tab_lists_candidates_second_tab_completes_and_clears_the_list(self, tmp_path):
        # "e" matches only "echo" and "exit" among the builtins; PATH is
        # pinned to an empty directory so no external executable can add a
        # third match and change the list or its layout.
        env = {**os.environ, "PATH": str(tmp_path)}

        out, returncode = run_shell(["e\t\t", "exit"], env=env)

        # First Tab: bell, then the candidate list is printed on the line
        # below the prompt, and the cursor is walked back up to the column
        # it was at (column 4: "$ " + "e" + 1).
        assert "$ e\x07\n\recho  exit\033[1A\033[4G" in out
        # Second Tab: the buffer completes to the first candidate in place -
        # the list is left on screen rather than cleared here.
        assert "\033[1D\033[0Kecho" in out
        # Enter: the still-displayed candidate line is erased (move down,
        # clear, move back up) before the completed "echo" command runs.
        assert "\033[B\033[2K\033[1A\r" in out
        assert returncode == 0

# ---------------------------------------------------------------------------
# Backspace editing
# ---------------------------------------------------------------------------

class TestBackspace:
    def test_backspace_deletes_the_previous_character_before_the_command_runs(self):
        # Types "echo ab", presses Backspace (erasing "b"), then types "c"
        # and Enter - so the executed command is "echo ac", not "echo ab".
        out, _ = run_shell(["echo ab\x7fc", "exit"])

        assert "\b \b" in out
        assert "ac\n" in out
