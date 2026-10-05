"""Regression tests for the git-tidy cleanup of agent worktrees and service branches."""

from __future__ import annotations

from pathlib import Path
import os
import subprocess

import pytest

import custom_components.elektronny_gorod  # noqa: F401  # load patch targets

REPO_ROOT = Path(__file__).parents[1]
HOOKS = (
    REPO_ROOT / ".agents/hooks/git-tidy.sh",
    REPO_ROOT / ".claude/hooks/git-tidy.sh",
    REPO_ROOT / ".codex/hooks/git-tidy.sh",
)
TIDY = HOOKS[0]


def _git(repo: Path, *args: str, date: str | None = None) -> str:
    env = {**os.environ, "GIT_COMMITTER_DATE": date} if date else None
    result = subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True, env=env
    )
    return result.stdout.strip()


def _commit(repo: Path, name: str) -> str:
    (repo / name).write_text(name)
    _git(repo, "add", name)
    _git(repo, "commit", "-q", "-m", name)
    return _git(repo, "rev-parse", "HEAD")


def _tidy(repo: Path, *args: str, hook: Path = TIDY) -> str:
    result = subprocess.run(
        ["bash", str(hook), *args], cwd=repo, check=True, capture_output=True, text=True
    )
    return result.stdout


def _branches(repo: Path) -> set[str]:
    return set(_git(repo, "for-each-ref", "--format=%(refname:short)", "refs/heads").splitlines())


def _agent(repo: Path, name: str, at: str) -> Path:
    """Worktree агента так, как его оставляет ревьюер: создан от master, checkout кандидата."""
    path = repo / ".claude/worktrees" / name
    _git(repo, "worktree", "add", "-q", "-b", f"worktree-{name}", str(path), "master")
    _git(path, "checkout", "-q", "--detach", at)
    return path


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "master", str(origin))
    repo = tmp_path / "repo"
    _git(tmp_path, "clone", "-q", str(origin), str(repo))
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "user.email", "test@example.com")
    (repo / ".gitignore").write_text(".claude/worktrees/\n")
    _git(repo, "add", ".gitignore")
    _git(repo, "commit", "-q", "-m", "init")
    _git(repo, "push", "-q", "origin", "master")
    _git(repo, "remote", "set-head", "origin", "master")
    return repo


def _merge_pr(repo: Path, branch: str, *, owner: str = "owner", date: str | None = None) -> None:
    _git(repo, "checkout", "-q", "-B", branch)
    _commit(repo, f"{branch.replace('/', '_')}_{owner}")
    _git(repo, "push", "-q", "origin", branch)
    _git(repo, "checkout", "-q", "master")
    _git(
        repo, "merge", "-q", "--no-ff", branch,
        "-m", f"Merge pull request #1 from {owner}/{branch}", date=date,
    )
    _git(repo, "push", "-q", "origin", "master")


def _backup(repo: Path, name: str, at: str) -> None:
    """Backup, созданный в прошлом: всё, что влито сейчас, — новее него."""
    _git(repo, "branch", name, at, date="2020-01-01T00:00:00")


def test_reviewer_worktree_with_checkout_only_is_removed(repo: Path) -> None:
    head = _git(repo, "rev-parse", "HEAD")
    path = _agent(repo, "agent-review", head)

    _tidy(repo, "--apply")

    assert not path.exists()
    assert "worktree-agent-review" not in _branches(repo)


def test_superseded_candidate_does_not_count_as_agent_work(repo: Path) -> None:
    """Кандидат заменён amend — HEAD ревьюера ничей, но работы агента в нём нет."""
    _git(repo, "checkout", "-q", "-b", "feat/x")
    old = _commit(repo, "candidate")
    _git(repo, "commit", "-q", "--amend", "-m", "candidate v2")
    path = _agent(repo, "agent-old", old)

    _tidy(repo, "--apply")

    assert not path.exists()


def test_agent_commit_is_kept(repo: Path) -> None:
    path = _agent(repo, "agent-work", _git(repo, "rev-parse", "HEAD"))
    _git(path, "config", "user.name", "Agent")
    _git(path, "config", "user.email", "agent@example.com")
    _commit(path, "probe")

    out = _tidy(repo, "--apply")

    assert path.exists()
    assert "коммиты агента" in out


def test_agent_branch_with_own_commits_is_kept(repo: Path) -> None:
    path = _agent(repo, "agent-branch", _git(repo, "rev-parse", "HEAD"))
    _git(path, "checkout", "-q", "worktree-agent-branch")
    _commit(path, "on-branch")
    _git(repo, "worktree", "remove", str(path))

    _tidy(repo, "--apply")

    assert "worktree-agent-branch" in _branches(repo)


def test_abandoned_detached_commit_keeps_worktree(repo: Path) -> None:
    """Агент закоммитил на detached HEAD и ушёл checkout-ом — коммит всё равно его работа."""
    head = _git(repo, "rev-parse", "HEAD")
    path = _agent(repo, "agent-left", head)
    _git(path, "config", "user.name", "Agent")
    _git(path, "config", "user.email", "agent@example.com")
    _commit(path, "probe")
    _git(path, "checkout", "-q", "--detach", head)

    _tidy(repo, "--apply")

    assert path.exists()


def test_commit_reset_away_on_agent_branch_keeps_worktree(repo: Path) -> None:
    head = _git(repo, "rev-parse", "HEAD")
    path = _agent(repo, "agent-reset", head)
    _git(path, "checkout", "-q", "worktree-agent-reset")
    _git(path, "config", "user.name", "Agent")
    _git(path, "config", "user.email", "agent@example.com")
    _commit(path, "probe")
    _git(path, "checkout", "-q", "-B", "worktree-agent-reset", head)

    _tidy(repo, "--apply")

    assert path.exists()


def test_own_worktree_is_never_removed(repo: Path) -> None:
    path = _agent(repo, "agent-self", _git(repo, "rev-parse", "HEAD"))

    _tidy(path, "--apply", "--unlock")

    assert path.exists()


def test_user_worktree_under_claude_dir_is_untouched(repo: Path) -> None:
    path = repo / ".claude/worktrees/brave-otter"
    _git(repo, "worktree", "add", "-q", "--detach", str(path), "master")

    _tidy(repo, "--apply")

    assert path.exists()


def test_agent_worktree_on_its_branch_keeps_branch_until_removed(repo: Path) -> None:
    path = _agent(repo, "agent-onbranch", _git(repo, "rev-parse", "HEAD"))
    _git(path, "checkout", "-q", "worktree-agent-onbranch")
    (path / "wip.txt").write_text("unsaved")

    _tidy(repo, "--apply")

    assert path.exists()
    assert "worktree-agent-onbranch" in _branches(repo)


def test_protected_branch_survives_merged_pr_of_same_name(repo: Path) -> None:
    _git(repo, "branch", "dev")
    _merge_pr(repo, "dev")

    _tidy(repo, "--apply")

    assert "dev" in _branches(repo)


def test_missing_origin_head_falls_back_to_origin_master(repo: Path) -> None:
    _git(repo, "remote", "set-head", "origin", "-d")
    _merge_pr(repo, "feat/fallback")

    _tidy(repo, "--apply")

    assert "feat/fallback" not in _branches(repo)


def test_locked_worktree_keeps_its_branch(repo: Path) -> None:
    path = _agent(repo, "agent-live", _git(repo, "rev-parse", "HEAD"))
    _git(repo, "worktree", "lock", str(path))

    _tidy(repo, "--apply")

    assert "worktree-agent-live" in _branches(repo)


def test_branch_named_like_tag_does_not_crash(repo: Path) -> None:
    _git(repo, "tag", "v1")
    _git(repo, "branch", "v1")
    path = _agent(repo, "agent-tag", _git(repo, "rev-parse", "HEAD"))
    _git(path, "config", "user.name", "Agent")
    _git(path, "config", "user.email", "agent@example.com")
    _commit(path, "probe")

    out = _tidy(repo)

    assert "оставлено: worktree agent-tag" in out


def test_unreadable_worktree_is_kept(repo: Path) -> None:
    """Не смогли проверить — не обещаем, что работы нет."""
    path = _agent(repo, "agent-broken", _git(repo, "rev-parse", "HEAD"))
    (Path(_git(path, "rev-parse", "--absolute-git-dir")) / "index").write_bytes(b"garbage")

    out = _tidy(repo)

    assert "оставлено: worktree agent-broken — не удалось проверить" in out


def test_dirty_worktree_is_kept(repo: Path) -> None:
    path = _agent(repo, "agent-dirty", _git(repo, "rev-parse", "HEAD"))
    (path / "scratch.txt").write_text("unsaved")

    out = _tidy(repo, "--apply")

    assert path.exists()
    assert "незакоммиченные" in out


def test_locked_worktree_needs_unlock(repo: Path) -> None:
    path = _agent(repo, "agent-locked", _git(repo, "rev-parse", "HEAD"))
    _git(repo, "worktree", "lock", "--reason", "claude agent", str(path))

    _tidy(repo, "--apply")
    assert path.exists()

    _tidy(repo, "--apply", "--unlock")
    assert not path.exists()


def test_backup_lives_until_pr_merge(repo: Path) -> None:
    _backup(repo, "backup/feat-y-20261005", _commit(repo, "rewritten"))
    _git(repo, "reset", "-q", "--hard", "HEAD~1")

    _tidy(repo, "--apply")
    assert "backup/feat-y-20261005" in _branches(repo)

    _merge_pr(repo, "feat/y")
    _tidy(repo, "--apply")
    assert "backup/feat-y-20261005" not in _branches(repo)


def test_merged_feature_branch_is_removed_but_fresh_one_kept(repo: Path) -> None:
    _merge_pr(repo, "feat/done")
    _git(repo, "branch", "feat/fresh", "HEAD~1")  # предок master, но PR не было

    _tidy(repo, "--apply")

    assert "feat/done" not in _branches(repo)
    assert "feat/fresh" in _branches(repo)


def test_reused_branch_name_waits_for_its_own_pr(repo: Path) -> None:
    _merge_pr(repo, "feat/again", date="2019-01-01T00:00:00")
    _git(repo, "branch", "-D", "feat/again")
    _git(repo, "branch", "feat/again")
    _git(repo, "push", "-q", "origin", "feat/again")

    _tidy(repo, "--apply")

    assert "feat/again" in _branches(repo)


def test_unpushed_work_on_merged_branch_is_kept(repo: Path) -> None:
    _merge_pr(repo, "feat/more")
    _git(repo, "checkout", "-q", "feat/more")
    _commit(repo, "after-merge")
    _git(repo, "checkout", "-q", "master")

    _tidy(repo, "--apply")

    assert "feat/more" in _branches(repo)


def test_branches_do_not_shield_each_other(repo: Path) -> None:
    """Влитая ветка с неотправленной работой и backup на той же вершине — обе остаются.

    Каждая видит общий коммит в соседней; удали обе — и работа только в reflog.
    """
    # Ветка старше своего merge — иначе она и не кандидат, и проверять нечего.
    _git(repo, "branch", "fix/s", date="2018-01-01T00:00:00")
    _merge_pr(repo, "fix/s", date="2019-01-01T00:00:00")
    _git(repo, "checkout", "-q", "fix/s")
    tip = _commit(repo, "next-pr")
    _backup(repo, "backup/fix/s-20261005", tip)
    _git(repo, "checkout", "-q", "master")

    _tidy(repo, "--apply")

    assert {"fix/s", "backup/fix/s-20261005"} <= _branches(repo)


def test_agent_branch_does_not_shield_unpushed_work(repo: Path) -> None:
    _merge_pr(repo, "feat/x")
    _git(repo, "checkout", "-q", "feat/x")
    tip = _commit(repo, "unpushed")
    _git(repo, "checkout", "-q", "master")
    _git(repo, "branch", "worktree-agent-r", tip)

    _tidy(repo, "--apply")

    assert _git(repo, "for-each-ref", "--contains", tip, "--format=%(refname)")


def test_backup_survives_older_pr_with_same_branch_name(repo: Path) -> None:
    _merge_pr(repo, "feat/r", date="2019-01-01T00:00:00")
    _backup(repo, "backup/feat-r-20261005", _commit(repo, "rewritten"))
    _git(repo, "reset", "-q", "--hard", "HEAD~1")

    _tidy(repo, "--apply")

    assert "backup/feat-r-20261005" in _branches(repo)


def test_fork_pr_with_same_branch_name_does_not_count(repo: Path) -> None:
    _git(repo, "remote", "set-url", "--push", "origin", str(repo.parent / "origin.git"))
    _git(repo, "remote", "set-url", "origin", "git@github.com:owner/repo.git")
    _backup(repo, "backup/feat-f-20261005", _commit(repo, "rewritten"))
    _git(repo, "reset", "-q", "--hard", "HEAD~1")
    _merge_pr(repo, "feat/f", owner="stranger")

    _tidy(repo, "--apply")

    assert "backup/feat-f-20261005" in _branches(repo)


def _ignore(repo: Path, *patterns: str) -> None:
    (repo / ".gitignore").write_text("\n".join([".claude/worktrees/", *patterns]) + "\n")
    _git(repo, "commit", "-q", "-am", "ignore")


def test_ignored_research_file_keeps_worktree(repo: Path) -> None:
    _ignore(repo, "*.har")
    path = _agent(repo, "agent-har", _git(repo, "rev-parse", "HEAD"))
    (path / "session.har").write_text("{}")

    _tidy(repo, "--apply")

    assert (path / "session.har").exists()


def test_regenerable_caches_do_not_keep_worktree(repo: Path) -> None:
    _ignore(repo, "__pycache__/", ".coverage")
    path = _agent(repo, "agent-cache", _git(repo, "rev-parse", "HEAD"))
    (path / "pkg" / "__pycache__").mkdir(parents=True)
    (path / "pkg" / "__pycache__" / "m.cpython-314.pyc").write_bytes(b"")
    (path / ".coverage").write_text("")

    _tidy(repo, "--apply")

    assert not path.exists()


def test_without_origin_head_worktrees_are_still_cleaned(repo: Path) -> None:
    _git(repo, "remote", "remove", "origin")
    path = _agent(repo, "agent-noremote", _git(repo, "rev-parse", "HEAD"))

    out = _tidy(repo, "--apply")

    assert not path.exists()
    assert "нет origin/HEAD" in out


def test_dry_run_changes_nothing(repo: Path) -> None:
    path = _agent(repo, "agent-dry", _git(repo, "rev-parse", "HEAD"))
    before = _branches(repo)

    out = _tidy(repo)

    assert path.exists()
    assert _branches(repo) == before
    assert "к уборке: worktree agent-dry" in out


def test_quiet_is_silent_when_clean(repo: Path) -> None:
    assert _tidy(repo, "--quiet") == ""


@pytest.mark.parametrize("hook", HOOKS, ids=lambda h: str(h.relative_to(REPO_ROOT)))
def test_launchers_reach_canonical_script(repo: Path, hook: Path) -> None:
    path = _agent(repo, "agent-launch", _git(repo, "rev-parse", "HEAD"))

    out = _tidy(repo, "--quiet", hook=hook)

    assert path.exists()
    assert "к уборке: worktree agent-launch" in out
