#!/usr/bin/env python3
"""Canonical cross-tool checker: ручные переносы посреди предложений в markdown.

Разрыв строки посреди фразы ломает чтение в редакторе с мягким переносом и
делает diff шумным: правка одного слова перекладывает весь абзац. Накапливается
он незаметно — генератор текста переносит по привычной ширине, и за несколько
сессий файл оказывается размечен вручную целиком.

Проверка и исправление — один и тот же код: `--fix` записывает то, что
`--check` считает правильным, поэтому разойтись они не могут.

Не трогаем ничего, где перенос значим: YAML-фронтматтер, HTML-разметку,
таблицы, блоки кода, заголовки, цитаты и явные переносы markdown из двух
пробелов. Внутри пункта списка продолжение склеиваем целиком — строка с
отступом там всегда продолжение того же пункта. В самостоятельных абзацах
осторожнее: только посреди фразы и только если предыдущая строка длинная,
потому что короткая означает, что разрыв поставлен нарочно.
"""

from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys

# Знаки, после которых перенос мог быть намеренным. Двоеточие здесь потому,
# что за ним обычно идёт список.
ENDS_SENTENCE = re.compile(r'[.!?:;)»"`\]]\s*$|^\s*$')
HTMLISH = re.compile(r"^\s*<|>\s*$")
LIST_ITEM = re.compile(r"^\s*([-*+]\s|\d+[.)]\s)")

# Ниже этой длины строка не могла быть перенесена по ширине.
WRAP_WIDTH = 60


def _hard(line: str) -> bool:
    """Строка, которую нельзя склеивать ни с чем."""
    stripped = line.strip()
    return (
        not stripped
        or stripped.startswith(("#", "|", ">", "```", "~~~"))
        or stripped in ("---", "***", "___")
        or HTMLISH.search(line) is not None
        or line.startswith(("    ", "\t"))
        or line.endswith("  ")
    )


def _continues_item(line: str) -> bool:
    """Продолжение пункта списка: отступ 1-3 пробела, сам не пункт."""
    return (
        re.match(r"^ {1,3}\S", line) is not None
        and not LIST_ITEM.match(line)
        and not _hard(line)
    )


def normalize(text: str) -> str:
    """Склеить переносы посреди фраз, оставив значимые."""
    lines = text.split("\n")
    out: list[str] = []
    index = 0
    in_fence = False

    # Фронтматтер переносим как есть: там значим каждый перевод строки.
    if lines and lines[0].strip() == "---":
        for end in range(1, len(lines)):
            if lines[end].strip() == "---":
                out.extend(lines[: end + 1])
                index = end + 1
                break

    while index < len(lines):
        line = lines[index]
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
            out.append(line)
            index += 1
            continue
        if in_fence or HTMLISH.search(line) or (_hard(line) and not LIST_ITEM.match(line)):
            out.append(line)
            index += 1
            continue

        is_item = LIST_ITEM.match(line) is not None
        if not is_item and line.strip().startswith("**"):
            # Строка-поле («**Статус:** …») — соседние такие же самостоятельны.
            out.append(line)
            index += 1
            continue

        buffer = [line.rstrip()]
        cursor = index + 1
        while cursor < len(lines):
            following = lines[cursor]
            if following.lstrip().startswith(("```", "~~~")):
                break
            if is_item:
                if not _continues_item(following):
                    break
            elif (
                len(buffer[-1].rstrip()) < WRAP_WIDTH
                or ENDS_SENTENCE.search(buffer[-1])
                or _hard(following)
                or LIST_ITEM.match(following)
                or following.strip().startswith("**")
            ):
                break
            buffer.append(following.strip())
            cursor += 1
        out.append(" ".join(buffer))
        index = cursor

    return "\n".join(out)


def _targets(argv: list[str]) -> list[Path]:
    if argv:
        return [Path(a) for a in argv if a.endswith(".md") and Path(a).is_file()]
    listed = subprocess.run(
        ["git", "ls-files", "*.md"], capture_output=True, text=True, check=False
    ).stdout.split()
    return [Path(f) for f in listed if Path(f).is_file()]


def main() -> int:
    argv = [a for a in sys.argv[1:] if a != "--fix"]
    fix = "--fix" in sys.argv[1:]

    offenders: list[tuple[Path, int]] = []
    for path in _targets(argv):
        original = path.read_text(encoding="utf-8")
        updated = normalize(original)
        if updated == original:
            continue
        # Страховка: правка обязана менять только пробелы. Если текст поехал —
        # молча пропускаем файл, лучше не тронуть, чем испортить.
        if re.sub(r"\s+", " ", original).strip() != re.sub(r"\s+", " ", updated).strip():
            print(f"⚠️  {path}: пропущен, нормализация изменила бы текст")
            continue
        joined = original.count("\n") - updated.count("\n")
        if fix:
            path.write_text(updated, encoding="utf-8")
        offenders.append((path, joined))

    if not offenders:
        print("Markdown wrap scan passed")
        return 0

    verb = "склеено" if fix else "нужно склеить"
    for path, joined in offenders:
        print(f"  {path}: {verb} переносов посреди фраз: {joined}")
    if fix:
        print(f"✅ Исправлено файлов: {len(offenders)}")
        return 0
    print("❌ Переносы посреди предложений. Исправить: "
          "bash .agents/hooks/check-markdown-wrap.sh --fix")
    return 1


if __name__ == "__main__":
    sys.exit(main())
