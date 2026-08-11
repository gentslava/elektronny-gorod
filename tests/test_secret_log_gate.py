"""Regression tests for the repository secret-log gate."""

from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import subprocess
from types import ModuleType

import pytest

import custom_components.elektronny_gorod  # noqa: F401  # load patch targets


REPO_ROOT = Path(__file__).parents[1]
SCANNER_PATH = REPO_ROOT / ".codex/hooks/check-secret-logs.py"
WRAPPER_PATH = REPO_ROOT / ".codex/hooks/check-secret-logs.sh"
CLAUDE_HOOK_PATH = REPO_ROOT / ".claude/hooks/post-edit-redaction-check.sh"


@pytest.fixture(scope="module")
def scanner() -> ModuleType:
    spec = importlib.util.spec_from_file_location("secret_log_checker", SCANNER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _is_blocked(scanner: ModuleType, source: str) -> bool:
    tree = ast.parse(source)
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and scanner._logger_method(node) is not None
    ]
    return any(scanner._unsafe_arguments(call) for call in calls)


@pytest.mark.parametrize(
    "source",
    [
        'LOGGER.warning("token=%s", token)',
        'LOGGER.warning("Access token: %s", value)',
        'LOGGER.warning("SMS code: %s", code)',
        'LOGGER.warning("%s", redact(access_token))',
        'LOGGER.warning("%s", redact(credentials))',
        'LOGGER.log(logging.WARNING, "token=%s", value)',
        'LOGGER.warning("%s", config_entry.data)',
        'LOGGER.warning("%s", self._entry.data)',
        'LOGGER.warning("%s", config_entry.options)',
        'LOGGER.warning("%s", request_headers)',
        'LOGGER.warning("%(token)s", payload)',
        'LOGGER.warning("%s", sms_code)',
        'LOGGER.warning("%s", go2rtc_username)',
        'LOGGER.warning("%s", payload["access_token"])',
        'LOGGER.warning("%s", payload.get("refresh_token"))',
        'LOGGER.warning("%s", redact(payload))',
        'LOGGER.warning("auth response body=%s", body)',
        'LOGGER.warning("{token}".format_map(payload))',
        'LOGGER.warning("go2rtc username=%s", value)',
        (
            'LOGGER.warning("count={count} token={token}"'
            ".format(token=value, count=len(value)))"
        ),
        'LOGGER.warning("count=%(count)s token=%(token)s", payload)',
        'LOGGER.warning("token={token}".format(**payload))',
        'LOGGER.warning("token={token}".format(**redact(headers), **payload))',
        'LOGGER.warning("%s", self._go2rtc_username)',
        'LOGGER.warning("%s", go2rtc_username_default)',
        'LOGGER.warning("%s", auth_response)',
        'LOGGER.warning("%s", entry.as_dict())',
    ],
)
def test_secret_log_gate_blocks_sensitive_values(scanner: ModuleType, source: str):
    assert _is_blocked(scanner, source)


@pytest.mark.parametrize(
    "source",
    [
        'LOGGER.debug("Credentials captured (length=%d)", len(self.access_token))',
        'LOGGER.debug("Headers: %s", redact(headers))',
        'LOGGER.debug("Headers: %s", redact(request_headers))',
        'LOGGER.error("fallback %s; check username/password in config", status)',
        'LOGGER.log(level, "Camera %s: empty stream", camera_id)',
        'LOGGER.warning("Auth request failed: %s", status)',
    ],
)
def test_secret_log_gate_accepts_safe_summaries(scanner: ModuleType, source: str):
    assert not _is_blocked(scanner, source)


def test_secret_log_wrapper_is_worktree_portable():
    result = subprocess.run(
        ["bash", str(WRAPPER_PATH)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "Secret log scan passed" in result.stdout


def test_secret_log_wrapper_rejects_unsafe_file(tmp_path: Path):
    unsafe_file = tmp_path / "unsafe_log.py"
    unsafe_file.write_text('LOGGER.warning("token=%s", token)\n')

    result = subprocess.run(
        ["bash", str(WRAPPER_PATH), str(unsafe_file)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Direct secret logging detected" in result.stdout


def test_post_edit_hook_without_argument_runs_full_scan():
    result = subprocess.run(
        ["bash", str(CLAUDE_HOOK_PATH)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "Secret log scan passed" in result.stdout


def test_codex_hook_commands_are_repository_relative():
    config = json.loads((REPO_ROOT / ".codex/hooks.json").read_text())
    commands = [
        hook["command"].strip("'")
        for event_hooks in config["hooks"].values()
        for entry in event_hooks
        for hook in entry["hooks"]
    ]

    assert commands
    assert all(not Path(command).is_absolute() for command in commands)
