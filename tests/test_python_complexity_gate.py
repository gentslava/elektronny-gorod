"""Exercise the Python complexity gate against real Git commits and Ruff."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


HOOK = Path(__file__).parents[1] / ".agents/hooks/check-python-complexity.py"
PACKAGE = Path("custom_components/elektronny_gorod")


def _function(name: str, branches: int, *, ignore: bool = False) -> str:
    suppression = "  # noqa: C901" if ignore else ""
    cases = "".join(
        f"    if value == {value}:\n        return {value}\n" for value in range(branches)
    )
    return f"def {name}(value):{suppression}\n{cases}    return 0\n"


@unittest.skipUnless(shutil.which("ruff"), "requires the Ruff job's Ruff executable")
class PythonComplexityGateTests(unittest.TestCase):
    def setUp(self) -> None:
        scratch = TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.repo = Path(scratch.name)
        self._git("init", "-b", "master")
        self._git("config", "user.name", "Gate tests")
        self._git("config", "user.email", "gate@example.com")
        (self.repo / PACKAGE).mkdir(parents=True)
        self.source = self.repo / PACKAGE / "example.py"

    def _git(self, *args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=self.repo, check=True, capture_output=True, text=True
        ).stdout.strip()

    def _commit_files(self) -> str:
        self._git("add", "--all")
        self._git("commit", "--no-gpg-sign", "-m", "fixture")
        return self._git("rev-parse", "HEAD")

    def _commit(self, body: str) -> str:
        self.source.write_text(body, encoding="utf-8")
        return self._commit_files()

    def _check(self, base: str, head: str = "HEAD") -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(HOOK), base, head],
            cwd=self.repo,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_new_complex_function_fails_despite_noqa(self) -> None:
        base = self._commit("pass\n")
        self._commit(_function("new_complex_function", 9, ignore=True))
        result = self._check(base)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("new_complex_function has a new or growing C901 violation (10 > 9)", result.stdout)

    def test_growing_complex_function_reports_qualified_name_and_delta(self) -> None:
        base = self._commit("class Example:\n" + _indent(_function("method", 9)))
        self._commit("class Example:\n" + _indent(_function("method", 10)))
        result = self._check(base)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("Example.method has a new or growing C901 violation (10 -> 11)", result.stdout)

    def test_line_shifts_and_improvements_pass(self) -> None:
        base = self._commit(_function("legacy", 11) + _function("improving", 10))
        self._commit("# Leading comments shift both definitions.\n\n" + _function("legacy", 11) + _function("improving", 9))
        result = self._check(base)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("compared 1 file(s)", result.stdout)

    def test_overloads_preserve_implementation_identity(self) -> None:
        base = self._commit(_function("legacy", 10))
        overloads = (
            "from typing import overload\n\n"
            "@overload\ndef legacy(value: int) -> int: ...\n\n"
            "@overload\ndef legacy(value: str) -> int:\n"
            '    """"""\n    pass\n\n'
        )
        for branches, expected in ((10, 0), (9, 0), (11, 1)):
            with self.subTest(branches=branches):
                self._commit(overloads + _function("legacy", branches))
                result = self._check(base)
                self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
                if expected:
                    self.assertIn("legacy has a new or growing C901 violation (11 -> 12)", result.stdout)

    def test_exact_function_and_file_renames_pass(self) -> None:
        base = self._commit(_function("legacy", 9))
        renamed_function = self._commit(_function("renamed", 9))
        result = self._check(base, renamed_function)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.source.rename(self.source.with_name("moved.py"))
        renamed_file = self._commit_files()
        result = self._check(renamed_function, renamed_file)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_explicit_head_and_merge_base_are_used(self) -> None:
        common = self._commit("pass\n")
        self._git("switch", "-c", "feature")
        feature = self._commit(_function("simple", 2))
        self._git("switch", "master")
        base = self._commit(_function("simple", 10))
        self.source.write_text(_function("uncommitted", 20), encoding="utf-8")
        result = self._check(base, feature)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"from {common[:12]} to {feature[:12]}", result.stdout)

    def test_invalid_source_fails_closed(self) -> None:
        base = self._commit("pass\n")
        self._commit("def incomplete(:\n    pass\n")
        result = self._check(base)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("Cannot check Python complexity", result.stderr)


def _indent(body: str) -> str:
    return "".join(f"    {line}" for line in body.splitlines(keepends=True))


if __name__ == "__main__":
    unittest.main()
