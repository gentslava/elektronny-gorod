#!/usr/bin/env python3
"""Canonical cross-tool уборка служебных веток и worktree после работы агентов.

Мусор копится из трёх источников, и ни один не убирает себя сам:

- worktree ревьюеров (`.claude/worktrees/agent-*`) и их ветки `worktree-agent-*`.
  Инструмент удаляет worktree, только если агент в нём ничего не трогал, а
  ревьюер по регламенту делает `git checkout <candidate>` — и worktree остаётся;
- `backup/<branch>-<date>` из правила git-history: нужен до merge PR, после —
  нет, но срока жизни у него раньше не было;
- локальные feature-ветки, чей PR уже влит в основную ветку.

Без `--apply` скрипт только печатает план — так он и работает на старте сессии.
Удаляет он только то, что не теряет работу:

- worktree — без правок, в том числе игнорируемых файлов (исследовательские
  `*.har`, `local/`), кроме кэшей, которые пересоздаются сами;
- ветку — без коммитов, которых нет на remote и в ветках, которые остаются.
  Ветки из того же плана на удаление и backup чужие коммиты не защищают:
  иначе две удаляемые ветки с общим неотправленным коммитом прикрыли бы друг
  друга и ушли обе.

Исключение — backup: его коммиты уникальны по построению (история
переписана), поэтому он удаляется по факту merge PR его ветки, причём
merge-коммит должен быть новее самого backup — имя ветки бывает повторным.
То же для влитой feature-ветки: merge старше ветки — это прошлый PR с тем же
именем.

Работа агента в worktree — это любой коммит из reflog его HEAD, а не только
текущий HEAD: агент мог закоммитить на detached HEAD и уйти checkout-ом дальше.
Чего скрипт не видит: коммит, созданный в обход reflog (`commit-tree` +
`update-ref`) или при выключенном `core.logAllRefUpdates`, после удаления
worktree остаётся только в object store до `gc`.

Заблокированный worktree не трогаем: блокировку держит запущенная сессия
агента, и по ней не отличить работающего ревьюера от закончившего. Оркестратор,
получивший все вердикты и не имеющий ни одного работающего агента, снимает её
флагом `--unlock`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import argparse
import re
import subprocess
import sys

AGENT_WORKTREE = re.compile(r"/\.claude/worktrees/agent-[^/]+$")
AGENT_BRANCH = "worktree-agent-"
BACKUP = re.compile(r"^backup/(?P<source>.+?)-(?:\d{8}|\d{4}-\d{2}-\d{2})$")
# Записи reflog, которые создают коммиты. `reset` сюда не входит: его пишет сам
# инструмент при создании worktree, и нового коммита он не делает.
WORK = re.compile(r"^(commit|merge|cherry-pick|rebase|revert|am|pull)\b")
MERGED_PR = re.compile(r"^Merge pull request #\d+ from (?P<owner>[^/]+)/(?P<branch>.+)$")
ORIGIN_OWNER = re.compile(r"github\.com[:/](?P<owner>[^/]+)/")
# Игнорируемое, что пересоздаётся само и работой не считается.
REGENERABLE = re.compile(
    r"(^|/)(__pycache__|\.pytest_cache|\.mypy_cache|\.ruff_cache|\.venv)/?$"
    r"|(^|/)\.coverage(\..+)?$|\.pyc$"
)
PROTECTED = {"master", "main", "dev"}


def git(*args: str, check: bool = True) -> str:
    # Без optional locks: `status` на чужом живом worktree не должен брать
    # index.lock из-под агента.
    result = subprocess.run(
        ["git", "--no-optional-locks", *args], capture_output=True, text=True, check=False
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {result.stderr.strip()}")
    return result.stdout.strip()


@dataclass
class Worktree:
    path: str
    head: str = ""
    branch: str | None = None
    locked: bool = False


@dataclass
class Plan:
    actions: list[tuple[str, list[str]]] = field(default_factory=list)
    kept: list[str] = field(default_factory=list)

    def remove(self, label: str, *command: str) -> None:
        self.actions.append((label, list(command)))

    def keep(self, label: str, reason: str) -> None:
        self.kept.append(f"{label} — {reason}")


@dataclass
class Merge:
    key: str
    time: int


def worktrees() -> list[Worktree]:
    found: list[Worktree] = []
    for line in git("worktree", "list", "--porcelain").splitlines():
        key, _, value = line.partition(" ")
        if key == "worktree":
            found.append(Worktree(value))
        elif key == "HEAD":
            found[-1].head = value
        elif key == "branch":
            found[-1].branch = value.removeprefix("refs/heads/")
        elif key == "locked":
            found[-1].locked = True
    return found


def default_branch() -> str | None:
    ref = git("symbolic-ref", "-q", "refs/remotes/origin/HEAD", check=False)
    base = ref.removeprefix("refs/remotes/") or "origin/master"
    return base if git("rev-parse", "--verify", "-q", base, check=False) else None


def _key(branch: str) -> str:
    """Имя ветки без разделителей: backup пишут и `feat/x-…`, и `feat-x-…`."""
    return branch.replace("/", "-")


def merges(base: str) -> list[Merge]:
    """Влитые PR по merge-коммитам GitHub «from <owner>/<branch>».

    Squash-merge такого коммита не оставляет — тогда ветка остаётся, и это
    безопасная сторона ошибки. Если origin — GitHub, PR из форка с тем же
    именем ветки не в счёт; у другого хостинга владельца не сверить.
    """
    url = git("remote", "get-url", "origin", check=False)
    owner = m["owner"] if (m := ORIGIN_OWNER.search(url)) else None
    found = []
    for line in git("log", base, "--merges", "--format=%ct%x09%s").splitlines():
        time, _, subject = line.partition("\t")
        if (pr := MERGED_PR.match(subject)) and owner in (None, pr["owner"]):
            found.append(Merge(_key(pr["branch"]), int(time)))
    return found


def created(branch: str) -> int:
    """Когда ветка появилась: первая запись её reflog, иначе время её вершины."""
    # Время записи reflog — в селекторе `%gd`; `%ct` здесь было бы временем коммита.
    entries = git(
        "reflog", "show", "--date=unix", "--format=%gd", f"refs/heads/{branch}", check=False
    ).splitlines()
    if entries and (stamp := re.search(r"@\{(\d+)\}$", entries[-1])):
        return int(stamp[1])
    return int(git("log", "-1", "--format=%ct", f"refs/heads/{branch}"))


def unique_commits(tip: str, protectors: list[str]) -> int:
    """Коммиты `tip`, которых нет ни на remote, ни в ветках-защитниках."""
    # После `--not` ссылки уже исключающие: `^ref` здесь снова сделал бы их включающими.
    out = git("rev-list", "--count", tip, "--not", "--remotes", *protectors)
    return int(out or 0)


def agent_work(path: str, protectors: list[str]) -> int:
    """Коммиты агента из этого worktree, которых нет в остающихся ветках.

    Смотрим все коммиты, созданные в worktree (по его reflog HEAD), а не только
    текущий HEAD. Одна недостижимость HEAD работу тоже не доказывает: ревьюер
    делает checkout кандидата, а кандидат потом заменяет amend.
    """
    made = [
        sha
        for sha, _, subject in (
            line.partition("\t")
            for line in git("-C", path, "log", "-g", "--format=%H%x09%gs", "HEAD").splitlines()
        )
        if WORK.match(subject)
    ]
    return sum(unique_commits(sha, protectors) for sha in dict.fromkeys(made))


def changes(path: str) -> list[str]:
    """Правки worktree, включая игнорируемые файлы, кроме пересоздаваемых кэшей."""
    lines = git("-C", path, "status", "--porcelain", "--ignored=matching").splitlines()
    return [
        line
        for line in lines
        if not (line.startswith("!! ") and REGENERABLE.search(line[3:]))
    ]


def candidate_branches(base: str | None, busy: set[str]) -> tuple[list[str], dict[str, str]]:
    """Ветки, которые план собирается удалить, и причины оставить остальные служебные.

    `busy` — ветки, вычекнутые в worktree, которые остаются.
    """
    if base is None:
        return [], {}
    merged = merges(base)
    current = git("branch", "--show-current", check=False)
    kept: dict[str, str] = {}
    chosen: list[str] = []

    def merged_after(source: str, since: int) -> bool:
        # Не старше ветки: в одну секунду ветку создают и вливают только в тестах.
        return any(m.key == _key(source) and m.time >= since for m in merged)

    for name in local_branches():
        if name in PROTECTED or name == current or name in busy:
            continue
        if backup := BACKUP.match(name):
            source = backup["source"]
            if merged_after(source, created(name)):
                chosen.append(name)
            else:
                kept[name] = f"PR ветки {source} не влит в {base} после создания backup"
        elif name.startswith(AGENT_BRANCH) or merged_after(name, created(name)):
            # Предок основной ветки — ещё не «влита»: так выглядит и только что
            # созданная пустая ветка. Для своих веток доказательство одно — merge PR.
            chosen.append(name)
    return chosen, kept


def local_branches() -> list[str]:
    # Полные имена: `%(refname:short)` отдаёт `heads/v1`, если есть тег `v1`.
    refs = git("for-each-ref", "--format=%(refname)", "refs/heads").splitlines()
    return [ref.removeprefix("refs/heads/") for ref in refs]


def plan(unlock: bool) -> Plan:
    result = Plan()
    trees = worktrees()
    here = git("rev-parse", "--show-toplevel")
    agents = [
        t for t in trees
        if AGENT_WORKTREE.search(t.path) and t.path != here and Path(t.path).exists()
    ]
    base = default_branch()
    if base is None:
        result.keep("ветки", "нет origin/HEAD — с чем сверять merge, неизвестно")

    # Кандидатов считаем, будто все worktree агентов уйдут: защитников так
    # меньше всего, и каждая проверка ниже — самая строгая из возможных.
    agent_paths = {t.path for t in agents}
    busy = {t.branch for t in trees if t.branch and t.path not in agent_paths}
    chosen, kept_reasons = candidate_branches(base, busy)
    local = local_branches()
    protectors = [
        f"refs/heads/{name}"
        for name in local
        if name not in chosen and not BACKUP.match(name)
    ]

    removed: set[str] = set()
    kept_agents: set[str] = set()
    for tree in agents:
        name = Path(tree.path).name
        label = f"worktree {name}"
        kept_agents.add(name)
        try:
            pending, work = changes(tree.path), agent_work(tree.path, protectors)
        except RuntimeError as err:
            # Не смогли проверить — значит, не можем и обещать, что работы нет.
            result.keep(label, f"не удалось проверить: {err}")
            continue
        if pending:
            result.keep(label, f"есть незакоммиченные или игнорируемые файлы ({len(pending)})")
        elif work:
            result.keep(label, "в нём коммиты агента, которых нет в остающихся ветках")
        elif tree.locked and not unlock:
            result.keep(label, "заблокирован сессией агента; если вердикт получен — --unlock")
        else:
            if tree.locked:
                result.remove(f"{label} (снять блокировку)", "worktree", "unlock", tree.path)
            result.remove(label, "worktree", "remove", tree.path)
            removed.add(tree.path)
            kept_agents.discard(name)

    still_busy = {t.branch for t in agents if t.branch and t.path not in removed}
    for name in local:
        label = f"ветка {name}"
        if name in kept_reasons:
            result.keep(label, kept_reasons[name])
        elif name not in chosen:
            continue
        elif name in still_busy:
            result.keep(label, "вычекнута в оставленном worktree")
        elif name.removeprefix("worktree-") in kept_agents:
            result.keep(label, "её worktree агента оставлен")
        elif not BACKUP.match(name) and unique_commits(f"refs/heads/{name}", protectors):
            result.keep(label, "в ней коммиты, которых нет на remote и в остающихся ветках")
        else:
            # -D, потому что `-d` сверяется с HEAD, а не с основной веткой;
            # потерю работы исключают проверки выше.
            result.remove(label, "branch", "-D", name)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Уборка worktree агентов и служебных веток.")
    parser.add_argument("--apply", action="store_true", help="выполнить план")
    parser.add_argument("--unlock", action="store_true", help="убрать и заблокированные worktree агентов")
    parser.add_argument("--quiet", action="store_true", help="молчать, если убирать нечего")
    args = parser.parse_args()

    todo = plan(args.unlock)
    if not todo.actions and args.quiet:
        return 0
    if not todo.actions:
        print("git-tidy: убирать нечего.")
    failed = False
    for label, command in todo.actions:
        if not args.apply:
            print(f"к уборке: {label}")
            continue
        try:
            git(*command)
        except RuntimeError as err:
            failed = True
            print(f"не удалось: {label} — {err}")
        else:
            print(f"убрано: {label}")
    for line in todo.kept:
        print(f"оставлено: {line}")
    if args.apply:
        git("worktree", "prune")
    elif todo.actions:
        print("Выполнить: bash .agents/hooks/git-tidy.sh --apply")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
