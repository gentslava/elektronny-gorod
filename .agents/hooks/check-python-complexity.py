#!/usr/bin/env python3
"""Reject new or growing C901 violations relative to a Git merge base."""

from __future__ import annotations

import argparse
import ast
from collections import Counter
from copy import copy
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
import subprocess
import sys


PACKAGE = "custom_components/elektronny_gorod"
MAX_COMPLEXITY = 9

type Function = ast.FunctionDef | ast.AsyncFunctionDef
type Symbol = tuple[tuple[str, ...], int]


@dataclass
class Scan:
    definitions: dict[Symbol, Function] = field(default_factory=dict)
    violations: dict[Symbol, int] = field(default_factory=dict)


def _git(*args: str, cwd: Path | None = None) -> bytes:
    return subprocess.check_output(["git", *args], cwd=cwd)


def _is_stub(node: Function) -> bool:
    """Exclude declaration-only bodies from implementation numbering."""
    body = node.body
    if ast.get_docstring(node, clean=False) is not None:
        body = body[1:]
    return all(
        isinstance(statement, ast.Pass)
        or (
            isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Constant)
            and statement.value.value is Ellipsis
        )
        for statement in body
    )


def _symbols(source: bytes) -> dict[int, tuple[Symbol, Function]]:
    by_line: dict[int, tuple[Symbol, Function]] = {}
    occurrences: Counter[tuple[str, ...]] = Counter()

    def visit(node: ast.AST, scope: tuple[str, ...]) -> None:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            scope = (*scope, node.name)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not _is_stub(node):
            occurrences[scope] += 1
            by_line[node.lineno] = ((scope, occurrences[scope]), node)
        for child in ast.iter_child_nodes(node):
            visit(child, scope)

    visit(ast.parse(source), ())
    return by_line


def _scan(repo: Path, revision: str, path: str) -> Scan:
    source = _git("show", f"{revision}:{path}", cwd=repo)
    by_line = _symbols(source)
    result = subprocess.run(
        [
            "ruff", "check", "--isolated", "--ignore-noqa", "--no-cache",
            "--target-version", "py314", "--select", "C901",
            "--config", f"lint.mccabe.max-complexity={MAX_COMPLEXITY}",
            "--output-format", "json", "--stdin-filename", path, "-",
        ],
        cwd=repo,
        input=source,
        capture_output=True,
        check=False,
    )
    if result.returncode not in (0, 1):
        raise ValueError(f"Ruff failed for {path!r}: {result.stderr.decode().strip()}")

    scan = Scan(definitions=dict(by_line.values()))
    findings = json.loads(result.stdout)
    if not isinstance(findings, list) or bool(findings) != (result.returncode == 1):
        raise ValueError(f"unexpected Ruff result for {path!r}")
    for finding in findings:
        message = finding["message"]
        match = re.fullmatch(r"`(.+)` is too complex \((\d+) > (\d+)\)", message)
        declared = by_line.get(finding["location"]["row"])
        if (
            finding["code"] != "C901"
            or not match
            or declared is None
            or declared[1].name != match[1]
            or int(match[3]) != MAX_COMPLEXITY
        ):
            raise ValueError(f"unexpected Ruff diagnostic for {path!r}: {message}")
        scan.violations[declared[0]] = int(match[2])
    return scan


def _fingerprint(node: Function) -> str:
    """Match exact ASTs when only a function name changed in the same scope."""
    unnamed = copy(node)
    unnamed.name = ""
    return ast.dump(unnamed)


def _regressions(before: Scan, after: Scan):
    removed = Counter(
        (symbol[0][:-1], score, _fingerprint(before.definitions[symbol]))
        for symbol, score in before.violations.items()
        if symbol not in after.definitions
    )
    for symbol, score in after.violations.items():
        previous = before.violations.get(symbol)
        if previous is not None and score <= previous:
            continue
        if symbol not in before.definitions and removed:
            rename = (symbol[0][:-1], score, _fingerprint(after.definitions[symbol]))
            if removed[rename]:
                removed[rename] -= 1
                continue
        yield symbol, previous, score


def _changed_python_files(repo: Path, base: str, head: str):
    changes = _git(
        "diff", "--name-status", "-z", "--find-renames", "--diff-filter=AMRT",
        base, head, "--", PACKAGE, cwd=repo,
    )
    fields = iter(changes.decode().rstrip("\0").split("\0") if changes else ())
    for status in fields:
        old_path = next(fields)
        path = next(fields) if status.startswith("R") else old_path
        if not path.endswith(".py"):
            continue
        previous = old_path if status != "A" and old_path.endswith(".py") else None
        if status != "R100" or previous is None:
            yield previous, path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", help="base commit or ref")
    parser.add_argument("head", nargs="?", default="HEAD", help="head commit or ref")
    args = parser.parse_args()

    try:
        repo = Path(_git("rev-parse", "--show-toplevel").decode().rstrip("\n"))
        base = _git("rev-parse", "--verify", "--end-of-options", f"{args.base}^{{commit}}", cwd=repo).decode().strip()
        head = _git("rev-parse", "--verify", "--end-of-options", f"{args.head}^{{commit}}", cwd=repo).decode().strip()
        merge_base = _git("merge-base", base, head, cwd=repo).decode().strip()
        files = list(_changed_python_files(repo, merge_base, head))
        failed = False
        for previous_path, path in files:
            before = _scan(repo, merge_base, previous_path) if previous_path else Scan()
            after = _scan(repo, head, path)
            for symbol, previous, score in _regressions(before, after):
                name = ".".join(symbol[0])
                detail = f"{previous} -> {score}" if previous is not None else f"{score} > {MAX_COMPLEXITY}"
                print(f"{path!r}:{after.definitions[symbol].lineno}: {name} has a new or growing C901 violation ({detail})")
                failed = True
    except (OSError, subprocess.CalledProcessError, SyntaxError, ValueError, KeyError, TypeError, StopIteration) as exc:
        print(f"Cannot check Python complexity: {exc}", file=sys.stderr)
        return 2

    print(f"Python complexity compared {len(files)} file(s) from {merge_base[:12]} to {head[:12]}.")
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
