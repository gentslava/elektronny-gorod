#!/usr/bin/env python3
"""Canonical cross-tool scanner for sensitive values in LOGGER calls."""

from __future__ import annotations

import ast
from pathlib import Path
import re
import sys


LOGGER_METHODS = {
    "critical",
    "debug",
    "error",
    "exception",
    "info",
    "log",
    "warn",
    "warning",
}
SAFE_SUMMARIZERS = {"len"}
SENSITIVE_NAMES = {
    "access_token",
    "accesstoken",
    "api_key",
    "apikey",
    "authorization",
    "credential",
    "credentials",
    "entry.data",
    "entry.options",
    "fcm_token",
    "go2rtc_username",
    "headers",
    "password",
    "refresh_token",
    "refreshtoken",
    "secret",
    "sms",
    "token",
}
SENSITIVE_MESSAGE_PATTERN = re.compile(
    r"\b(?:access[\s_-]*token|api[\s_-]*key|auth(?:entication)?[\s_-]*"
    r"(?:body|response)|authorization|credentials?|go2rtc[\s_-]*username|"
    r"fcm[\s_-]*token|headers?|password|refresh[\s_-]*token|secret|"
    r"sms(?:[\s_-]*code)?|token)\b",
    re.IGNORECASE,
)
FORMAT_PLACEHOLDER_PATTERN = re.compile(
    r"%(?!%)(?:\([^)]+\))?[#0\- +]?\d*(?:\.\d+)?[diouxXeEfFgGcrsa]|"
    r"\{[^{}]*\}"
)


def _qualified_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _qualified_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return None


def _is_sensitive_name(name: str) -> bool:
    normalized = name.casefold()
    parts = [
        part.lstrip("_") for part in normalized.replace("-", "_").split(".")
    ]
    leaf_name = parts[-1]
    if leaf_name in {"entry_data", "entry_options", "headers", "sms_code"}:
        return True
    if leaf_name.endswith("_headers"):
        return True
    if leaf_name.startswith("sms_") or leaf_name.endswith("_sms_code"):
        return True
    if "go2rtc_username" in leaf_name:
        return True
    if "auth_response" in leaf_name or "auth_body" in leaf_name:
        return True
    if (
        len(parts) >= 2
        and leaf_name in {"data", "options"}
        and parts[-2].lstrip("_").endswith("entry")
    ):
        return True
    return normalized in SENSITIVE_NAMES or any(
        part in SENSITIVE_NAMES
        or part.endswith("_token")
        or part.endswith("_password")
        or part.endswith("_secret")
        or part.endswith("_credentials")
        for part in parts
    )


def _is_safe_summary(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False

    function_name = _qualified_name(node.func)
    if function_name and function_name.split(".")[-1] in SAFE_SUMMARIZERS:
        return len(node.args) == 1 and not node.keywords

    if not function_name or function_name.split(".")[-1] != "redact":
        return False
    if len(node.args) != 1 or node.keywords:
        return False

    value_name = _qualified_name(node.args[0])
    if value_name is None:
        return False
    leaf_name = value_name.casefold().split(".")[-1]
    return leaf_name == "headers" or leaf_name.endswith("_headers")


def _contains_sensitive_value(node: ast.AST) -> bool:
    if isinstance(node, ast.Call):
        if _is_safe_summary(node):
            return False
        function_name = _qualified_name(node.func)
        if function_name and function_name.split(".")[-1] == "redact":
            return True
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "as_dict"
            and (owner_name := _qualified_name(node.func.value)) is not None
            and owner_name.casefold().split(".")[-1].lstrip("_").endswith("entry")
        ):
            return True

    if (
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and _is_sensitive_name(node.value)
    ):
        return True

    qualified_name = _qualified_name(node)
    if qualified_name and _is_sensitive_name(qualified_name):
        return True

    return any(_contains_sensitive_value(child) for child in ast.iter_child_nodes(node))


def _logger_method(call: ast.Call) -> str | None:
    if not isinstance(call.func, ast.Attribute) or call.func.attr not in LOGGER_METHODS:
        return None
    owner = _qualified_name(call.func.value)
    if owner not in {"LOGGER", "_LOGGER"}:
        return None
    return call.func.attr


def _message_text(node: ast.AST) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            elif isinstance(value, ast.FormattedValue):
                parts.append("{}")
        return "".join(parts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
        return _message_text(node.left)
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"format", "format_map"}
    ):
        return _message_text(node.func.value)
    return ""


def _message_values(node: ast.AST) -> list[ast.AST]:
    if isinstance(node, ast.Constant):
        return []
    if isinstance(node, ast.JoinedStr):
        return [
            value.value
            for value in node.values
            if isinstance(value, ast.FormattedValue)
        ]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
        if isinstance(node.right, ast.Tuple):
            return list(node.right.elts)
        return [node.right]
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"format", "format_map"}
    ):
        return [*node.args, *(keyword.value for keyword in node.keywords)]
    return [node]


def _sensitive_placeholder_indexes(message: str) -> list[int]:
    indexes: list[int] = []
    previous_end = 0
    for index, placeholder in enumerate(FORMAT_PLACEHOLDER_PATTERN.finditer(message)):
        context = message[previous_end : placeholder.end()]
        if SENSITIVE_MESSAGE_PATTERN.search(context):
            indexes.append(index)
        previous_end = placeholder.end()
    return indexes


def _brace_field_root(placeholder: str) -> str:
    field = placeholder[1:-1]
    field = field.split("!", 1)[0].split(":", 1)[0]
    return re.split(r"[.\[]", field, maxsplit=1)[0]


def _placeholder_value(
    message: ast.AST,
    values: list[ast.AST],
    placeholders: list[str],
    index: int,
) -> ast.AST | None:
    placeholder = placeholders[index]

    # %-mapping uses one mapping argument for every named placeholder.
    if placeholder.startswith("%("):
        return values[0] if values else None

    if (
        isinstance(message, ast.Call)
        and isinstance(message.func, ast.Attribute)
        and message.func.attr == "format_map"
    ):
        return message.args[0] if message.args else None

    if (
        isinstance(message, ast.Call)
        and isinstance(message.func, ast.Attribute)
        and message.func.attr == "format"
        and placeholder.startswith("{")
    ):
        field_root = _brace_field_root(placeholder)
        if field_root.isdecimal():
            argument_index = int(field_root)
            return (
                message.args[argument_index]
                if argument_index < len(message.args)
                else None
            )
        if field_root:
            explicit_value = next(
                (
                    keyword.value
                    for keyword in message.keywords
                    if keyword.arg == field_root
                ),
                None,
            )
            if explicit_value is not None:
                return explicit_value
            return next(
                (
                    keyword.value
                    for keyword in message.keywords
                    if keyword.arg is None
                ),
                None,
            )

        automatic_index = sum(
            1
            for previous in placeholders[: index + 1]
            if previous.startswith("{") and not _brace_field_root(previous)
        ) - 1
        return (
            message.args[automatic_index]
            if automatic_index < len(message.args)
            else None
        )

    return values[index] if index < len(values) else None


def _unpacked_format_mappings(message: ast.AST, placeholder: str) -> list[ast.AST]:
    if (
        not isinstance(message, ast.Call)
        or not isinstance(message.func, ast.Attribute)
        or message.func.attr != "format"
        or not placeholder.startswith("{")
    ):
        return []

    field_root = _brace_field_root(placeholder)
    if not field_root or field_root.isdecimal():
        return []
    if any(keyword.arg == field_root for keyword in message.keywords):
        return []
    return [keyword.value for keyword in message.keywords if keyword.arg is None]


def _unsafe_arguments(call: ast.Call) -> list[ast.AST]:
    method = _logger_method(call)
    message_index = 1 if method == "log" else 0
    if method is None or len(call.args) <= message_index:
        return []

    message = call.args[message_index]
    values = [*_message_values(message), *call.args[message_index + 1 :]]
    unsafe = [value for value in values if _contains_sensitive_value(value)]
    unsafe.extend(
        keyword.value
        for keyword in call.keywords
        if _contains_sensitive_value(keyword.value)
    )

    message_text = _message_text(message)
    placeholders = [
        match.group() for match in FORMAT_PLACEHOLDER_PATTERN.finditer(message_text)
    ]
    for index in _sensitive_placeholder_indexes(message_text):
        unpacked_mappings = _unpacked_format_mappings(
            message, placeholders[index]
        )
        if unpacked_mappings:
            # The selected key may come from any **mapping. Even a generally
            # safe wrapper cannot prove that this specific field was redacted.
            unsafe.extend(unpacked_mappings)
            continue
        value = _placeholder_value(message, values, placeholders, index)
        if value is not None and not _is_safe_summary(value):
            unsafe.append(value)
    return unsafe


def _python_files(arguments: list[str]) -> list[Path]:
    roots = [Path(argument) for argument in arguments]
    if not roots:
        roots = [Path("custom_components/elektronny_gorod")]

    files: set[Path] = set()
    for root in roots:
        if root.is_dir():
            files.update(root.rglob("*.py"))
        elif root.suffix == ".py" and root.is_file():
            files.add(root)
    return sorted(files)


def main(arguments: list[str]) -> int:
    if sys.version_info < (3, 12):
        print("Secret log scan requires the project's Python 3.12+ environment")
        return 2

    files = _python_files(arguments)
    if not files:
        print("Secret log scan found no Python files; run it from the repository root")
        return 2

    findings: list[str] = []
    for path in files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError) as error:
            findings.append(f"{path}: unable to scan: {error}")
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or _logger_method(node) is None:
                continue
            if _unsafe_arguments(node):
                findings.append(
                    f"{path}:{node.lineno}: direct sensitive value in LOGGER call"
                )

    if findings:
        print("Direct secret logging detected:")
        print("\n".join(findings))
        print(
            "Use redact(), log only a safe summary such as len(value), "
            "or remove the log."
        )
        return 1

    print("Secret log scan passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
