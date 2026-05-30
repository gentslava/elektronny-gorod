#!/usr/bin/env bash
# Hook: check-audit-reconciliation.sh
# Сверяет AIDD-документацию с git-реальностью (ADR-0010, дефекты D-01/D-02).
#
# Проверяет:
#   1. Каждый "✅ RESOLVED" finding с commit-SHA — этот SHA реально в master.
#   2. "resolved-in-branch" findings — перечисляет (они блокируют READY_FOR_RELEASE
#      до merge, но не являются drift-ошибкой сами по себе).
#   3. Entry-контракты (AGENTS.md/CLAUDE.md/workflow.md) не содержат stale-маркеров,
#      опровергаемых текущим кодом.
#
# Использование:
#   bash .claude/hooks/check-audit-reconciliation.sh         # полная проверка
#   Вызывается из /audit (шаг 2a) и /release-check (шаг 0, обязателен).
#
# Exit: 0 = чисто; 1 = найден drift (RESOLVED не в master ИЛИ stale-маркер).
# resolved-in-branch findings — WARNING (не меняет exit code сам по себе).

set -uo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
AUDIT="$ROOT/docs/audit/project-audit.md"
MASTER_REF="master"

fail=0

echo "── AIDD reconciliation (ADR-0010) ──"

if [[ ! -f "$AUDIT" ]]; then
    echo "❌ Не найден $AUDIT"
    exit 1
fi

# Определяем ref master (локальный или origin/).
if ! git rev-parse --verify --quiet "$MASTER_REF" >/dev/null; then
    if git rev-parse --verify --quiet "origin/master" >/dev/null; then
        MASTER_REF="origin/master"
    else
        echo "⚠️  Нет ветки master/origin/master — пропуск SHA-сверки."
        MASTER_REF=""
    fi
fi

# ── 1. RESOLVED findings с SHA → должны быть в master ──────────────────────
if [[ -n "$MASTER_REF" ]]; then
    # Строки вида: "RESOLVED — merged в master (commit `71eb4dd`...)"
    while IFS= read -r line; do
        # извлекаем 7-40-символьные hex SHA из backtick-обёрток
        shas=$(echo "$line" | grep -oE '`[0-9a-f]{7,40}`' | tr -d '`' || true)
        for sha in $shas; do
            if ! git cat-file -e "${sha}^{commit}" 2>/dev/null; then
                echo "❌ RESOLVED ссылается на несуществующий commit: $sha"
                fail=1
            elif ! git merge-base --is-ancestor "$sha" "$MASTER_REF" 2>/dev/null; then
                echo "❌ RESOLVED, но commit $sha НЕ в $MASTER_REF (drift D-02)"
                fail=1
            fi
        done
    done < <(grep -E '✅ \*\*RESOLVED\*\*' "$AUDIT" | grep -E '`[0-9a-f]{7,40}`')
fi

# ── 2. resolved-in-branch → WARNING (блокируют релиз до merge) ─────────────
# Только Status-строки findings (не определение словаря).
pending_lines=$(grep -nE '\*\*Status:\*\*.*resolved-in-branch' "$AUDIT" || true)
if [[ -n "$pending_lines" ]]; then
    cnt=$(echo "$pending_lines" | grep -c '' )
    echo "⚠️  resolved-in-branch findings: $cnt — НЕ в master, блокируют READY_FOR_RELEASE:"
    echo "$pending_lines" | sed 's/^/     /'
fi

# ── 3. Stale-маркеры в контрактах (D-01) ───────────────────────────────────
# Фразы, которые были истинны до фиксов, но теперь опровергаются кодом.
declare -a STALE_PATTERNS=(
    "pytest.*отсутствует"
    "нерабочий stub"
    "без update_interval"
    "per-request ClientSession.*антипаттерн"
    "hooks не настроены"
    "с fake-таймером"
)
for f in AGENTS.md CLAUDE.md workflow.md; do
    [[ -f "$ROOT/$f" ]] || continue
    for pat in "${STALE_PATTERNS[@]}"; do
        if grep -qiE "$pat" "$ROOT/$f"; then
            echo "❌ Stale-маркер в $f: /$pat/ (drift D-01 — код это опровергает)"
            fail=1
        fi
    done
done

# ── 4. PR TBD без статуса (запрещено ADR-0010) ─────────────────────────────
if grep -qE 'PR TBD' "$AUDIT"; then
    echo "❌ В project-audit.md остался 'PR TBD' — нужен merged-SHA или 'pending merge <ref>'"
    fail=1
fi

# ── 5. Vocabulary: '✅ RESOLVED' пара обязательна; '🟢 RESOLVED' запрещён ───
# 🟢 зарезервирован за 'resolved-in-branch'. RESOLVED (в master) = только ✅.
bad_vocab=$(grep -nE '🟢 \*\*RESOLVED\*\*' "$AUDIT" || true)
if [[ -n "$bad_vocab" ]]; then
    echo "❌ Неверный статус-эмодзи (RESOLVED должен быть ✅, 🟢 = resolved-in-branch):"
    echo "$bad_vocab" | sed 's/^/     /'
    fail=1
fi

if [[ "$fail" -eq 0 ]]; then
    echo "✅ Reconciliation clean (RESOLVED↔master согласованы, контракты без stale)."
else
    echo "── Drift найден. Исправь project-audit.md / контракты (ADR-0010). ──"
fi

exit "$fail"
