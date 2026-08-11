#!/usr/bin/env bash
# Hook: check-audit-reconciliation.sh
# Сверяет AIDD-документацию с git-реальностью (ADR-0010, дефекты D-01/D-02).
#
# Проверяет:
#   1. Каждый "✅ RESOLVED" finding проверен: SHA реально в master либо тот же
#      статус уже унаследован из master (legacy reconciliation evidence).
#   2. "resolved-in-branch" findings — перечисляет (они блокируют READY_FOR_RELEASE
#      до merge, но не являются drift-ошибкой сами по себе).
#   3. REMEDIATION-IN-REVIEW status имеет определение в vocabulary.
#   4. Entry-контракты (AGENTS.md/CLAUDE.md/workflow.md) не содержат stale-маркеров,
#      опровергаемых текущим кодом.
#
# Использование:
#   bash .codex/hooks/check-audit-reconciliation.sh          # Codex adapter
#   bash .claude/hooks/check-audit-reconciliation.sh         # Claude adapter
#   Вызывается из /audit (шаг 2a) и /release-check (шаг 0, обязателен).
#
# Exit: 0 = чисто; 1 = найден drift (RESOLVED не в master ИЛИ stale-маркер).
# resolved-in-branch findings — WARNING (не меняет exit code сам по себе).

set -uo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
AUDIT="$ROOT/docs/audit/project-audit.md"
MASTER_REF="master"

fail=0
pending_count=0

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

# ── 1. Каждый RESOLVED finding должен иметь master evidence ────────────────
if [[ -n "$MASTER_REF" ]]; then
    inherited_count=0
    while IFS=$'\t' read -r finding status_block; do
        [[ -n "$finding" ]] || continue
        shas=$(echo "$status_block" | grep -oE '`[0-9a-f]{7,40}`' | tr -d '`' || true)
        if [[ -z "$shas" ]]; then
            # Старые записи могут не содержать SHA. Они допустимы только если
            # тот же finding уже был RESOLVED в target master; новое закрытие
            # в feature-ветке без immutable evidence остаётся ошибкой.
            if git show "$MASTER_REF:docs/audit/project-audit.md" 2>/dev/null |
                awk -v target="$finding" '
                    /^### A-[0-9]+\./ { in_target = ($2 == target) }
                    in_target && /^- \*\*Status:\*\*.*✅ \*\*RESOLVED\*\*/ {
                        found = 1
                    }
                    END { exit(found ? 0 : 1) }
                '
            then
                inherited_count=$((inherited_count + 1))
                continue
            fi
            echo "❌ $finding RESOLVED без commit SHA и отсутствует как RESOLVED в $MASTER_REF"
            fail=1
            continue
        fi
        for sha in $shas; do
            if ! git cat-file -e "${sha}^{commit}" 2>/dev/null; then
                echo "❌ $finding RESOLVED ссылается на несуществующий commit: $sha"
                fail=1
            elif ! git merge-base --is-ancestor "$sha" "$MASTER_REF" 2>/dev/null; then
                echo "❌ $finding RESOLVED, но commit $sha НЕ в $MASTER_REF (drift D-02)"
                fail=1
            fi
        done
    done < <(
        awk '
            function emit() {
                if (finding != "" && status ~ /✅ \*\*RESOLVED\*\*/) {
                    gsub(/\t/, " ", status)
                    print finding "\t" status
                }
            }
            /^### A-[0-9]+\./ {
                emit()
                finding = $2
                status = ""
                capture = 0
                next
            }
            /^- \*\*Status:\*\*/ {
                status = $0
                capture = 1
                next
            }
            capture && /^  / { status = status " " $0; next }
            capture { capture = 0 }
            END { emit() }
        ' "$AUDIT"
    )
    if [[ "$inherited_count" -gt 0 ]]; then
        echo "ℹ️  legacy RESOLVED inherited from $MASTER_REF: $inherited_count"
    fi
fi

# ── 2. resolved-in-branch → WARNING (блокируют релиз до merge) ─────────────
# Только Status-строки findings (не определение словаря).
pending_lines=$(grep -niE '\*\*Status:\*\*.*resolved-in-branch' "$AUDIT" || true)
if [[ -n "$pending_lines" ]]; then
    cnt=$(echo "$pending_lines" | grep -c '' )
    pending_count=$((pending_count + cnt))
    echo "⚠️  resolved-in-branch findings: $cnt — НЕ в master, блокируют READY_FOR_RELEASE:"
    echo "$pending_lines" | sed 's/^/     /'
fi

# ── 3. REMEDIATION-IN-REVIEW → определённый открытый candidate status ──────
remediation_lines=$(grep -nE '\*\*Status:\*\*.*REMEDIATION-IN-REVIEW' "$AUDIT" || true)
if [[ -n "$remediation_lines" ]]; then
    if ! grep -qE '^- \*\*🟡 REMEDIATION-IN-REVIEW\*\*' "$AUDIT"; then
        echo "❌ REMEDIATION-IN-REVIEW используется без определения в Status vocabulary"
        fail=1
    else
        cnt=$(echo "$remediation_lines" | grep -c '')
        pending_count=$((pending_count + cnt))
        echo "⚠️  remediation-in-review findings: $cnt — candidate lifecycle ещё не завершён:"
        echo "$remediation_lines" | sed 's/^/     /'
    fi
fi

# ── 4. Stale-маркеры в контрактах (D-01) ───────────────────────────────────
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

# ── 5. PR TBD без статуса (запрещено ADR-0010) ─────────────────────────────
if grep -qE 'PR TBD' "$AUDIT"; then
    echo "❌ В project-audit.md остался 'PR TBD' — нужен merged-SHA или 'pending merge <ref>'"
    fail=1
fi

# ── 6. Vocabulary: 🟢 зарезервирован только за resolved-in-branch ───────────
green_status_lines=$(grep -nE '\*\*Status:\*\*.*🟢' "$AUDIT" || true)
bad_vocab=$(echo "$green_status_lines" | grep -viE '🟢[[:space:]]+\*\*resolved-in-branch\*\*' || true)
if [[ -n "$bad_vocab" ]]; then
    echo "❌ Неверный зелёный status (🟢 разрешён только для resolved-in-branch):"
    echo "$bad_vocab" | sed 's/^/     /'
    fail=1
fi

if [[ "$fail" -eq 0 ]]; then
    if [[ "$pending_count" -gt 0 ]]; then
        echo "✅ Reconciliation consistent; $pending_count pending findings remain open."
    else
        echo "✅ Reconciliation clean (RESOLVED↔master согласованы, контракты без stale)."
    fi
else
    echo "── Drift найден. Исправь project-audit.md / контракты (ADR-0010). ──"
fi

exit "$fail"
