Status: Active
Owner: Documentation / AIDD Agent
Last reviewed: 2026-08-11 (candidate-bound security/release plus ADR-0015 evidence/CI prompts)

Source files:
- этот документ

Related docs:
- `skills.md`
- `multi-agent-workflow.md`
- `quality-gates.md`
- `../testing/strategy.md`
- `../../.claude/commands/`

Used by agents:
- Любой агент при выборе готового prompt-шаблона

Quality gates:
- AUDIT_DONE

---

# Prompt Library

Готовые промпты для повторяющихся задач этого проекта. Каждый промпт имеет:
- **Цель**: чего достигаем.
- **Входы**: какие файлы / контекст агент должен прочитать.
- **Ожидаемый output**: формат результата.
- **Ограничения**: что нельзя.
- **Критерии качества**: как проверить, что получилось.

## P-01. Глубокий аудит проекта

```text
Ты — Lead AI-Driven Development Architect / Staff Engineer / HA Integration Expert.

Проведи глубокий аудит проекта elektronny-gorod по методологии docs/.

Inputs:
- весь репозиторий
- ../index.md → ../summary.md → ../project/project-map.md → ../audit/project-audit.md

Output:
- список новых findings с приоритетами P0..P3
- evidence (file:line) на каждый
- recommended fix + first step
- сравнение с предыдущим audit (что закрылось, что появилось)

Ограничения:
- не предлагать поверхностные «улучшить тесты»/«улучшить архитектуру»
- не модифицировать код без отдельного разрешения
- если HEAD сдвинулся с последнего аудита — обязательно зафиксировать в начале отчёта
```

## P-02. Независимый security review замороженного кандидата

```text
Ты — независимый Security & Privacy Reviewer. Skill: agent-skills:security-and-hardening.

Цель: проверить exact frozen candidate и закрыть SECURITY_OK только при
отсутствии незакрытых Critical/Important security findings.

Inputs:
- evidence CANDIDATE_FROZEN: clean status, base SHA, head SHA, tree SHA
- exact diff base..head и файлы из этого candidate
- ../audit/security.md
- quality-gates.md

Действия:
1. Подтвердить, что reviewer не участвовал в implementation и проверяет именно
   указанные base/head/tree; self-review не закрывает SECURITY_OK.
2. Проверить diff и затронутые пути на логирование/сохранение секретов,
   redaction, auth/token lifecycle и сообщения сторонних зависимостей.
3. Запустить релевантные secret/redaction checks и security regressions.
4. Для каждой находки указать severity и evidence. Critical/Important блокируют
   SECURITY_OK; после fix нужен новый freeze и повторный независимый review.

Output:
- reviewer identity и подтверждение независимости
- base SHA, head SHA, tree SHA
- список совпадений с file:line
- severity per finding
- команды/evidence выполненных проверок
- verdict: SECURITY_OK или changes requested

Ограничения:
- review read-only: не «исправлять» молча, только отчёт
- не подавлять предупреждения
- не выдавать SECURITY_OK без CANDIDATE_FROZEN или для другого candidate
```

## P-03. Запустить и дополнить тесты config_flow

```text
Ты — QA Agent. Skill: agent-skills:test-driven-development.

Цель: запустить и дополнить существующие pytest-тесты config_flow по canonical
плану docs/testing/strategy.md.

Inputs:
- custom_components/elektronny_gorod/config_flow.py
- docs/testing/strategy.md (раздел "1. Config flow")
- tests/conftest.py
- pytest-homeassistant-custom-component docs

Действия:
1. Перечитай config_flow.py, идентифицируй все steps и error/abort пути.
2. Запусти существующий
   `PYTHONPATH=. .venv/bin/pytest tests/test_config_flow.py -v` и сопоставь
   реальные тесты с изменённым поведением, acceptance criteria и gaps из
   strategy.
3. Для отсутствующего сценария сначала получи ожидаемый RED, затем минимальный
   GREEN; используй сложившиеся PHC fixtures и mock-подход модуля.
4. Повторно запусти весь `tests/test_config_flow.py`.

Output:
- точечный diff к существующим tests и перечень защищённых сценариев
- команда и свежий результат прогона
- если test fails — НЕ упрощать тест; зафиксировать как баг и предложить исправление в коде.

Ограничения:
- не «зелёные» тесты ценой потери проверки
- не удалять и не переписывать рабочий test module без доказанной причины
- не импортировать несуществующие сущности
```

## P-04. Подготовить hotfix-релиз для security-фиксов

```text
Ты — DevOps / Release Agent. Skill: agent-skills:shipping-and-launch.

Цель: подготовить hotfix-релиз с security-фиксами для exact frozen candidate.

Inputs:
- evidence CANDIDATE_FROZEN: clean status, base SHA, head SHA, tree SHA
- candidate-bound independent REVIEW_OK и SECURITY_OK с теми же идентификаторами
- durable PR evidence comment и `CI_GREEN` текущего head
- diff с фиксами и результаты обязательных проверок
- docs/audit/security.md
- docs/aidd/quality-gates.md
- .github/workflows/release.yaml

Действия:
1. Сверить base/head/tree у CANDIDATE_FROZEN, REVIEW_OK, SECURITY_OK и PR
   evidence comment;
   self-review или review другого candidate не принимается.
2. Проверить, что все Critical/Important findings обязательных code/profile
   reviews закрыты и повторно проверены; открытый release-blocking security
   finding из audit также блокирует релиз.
3. Проверить остальные обязательные quality gates и свежие test/hassfest/HACS
   результаты для этого candidate.
4. Сформировать CHANGELOG entry и release notes: что было, что стало и нужны ли
   действия пользователя. Перевыпуск токена рекомендовать только когда риск
   утечки действительно подтверждён.
5. Повторить релевантные secret/redaction checks; каждое совпадение оценивать по
   контексту, а не считать пустой grep единственным доказательством.

Output:
- черновик release notes
- список действий пользователя в notes (если нужно)
- base/head/tree проверенного candidate и evidence gates
- verdict: готов ли релиз; иначе точный список блокеров

Ограничения:
- не релизить без CANDIDATE_FROZEN, независимых candidate-bound
  REVIEW_OK/SECURITY_OK, REVIEW_EVIDENCE_PUBLISHED и CI_GREEN
- не релизить при открытом Critical/Important finding обязательного review
- НЕ делать `git push --tags` без явного approval owner
```

## P-05. Обновить AIDD-документацию под новый HEAD

```text
Ты — Documentation Agent.

Цель: синхронизировать docs/* с реальным состоянием кода.

Inputs:
- git diff <last-reviewed-commit>..HEAD
- docs/project/project-map.md (раздел maintenance rules)

Действия:
1. По maintenance rules определить, какие docs затронуты.
2. Для каждого:
   - перечитать актуальную часть кода
   - обновить ссылки file:line (если сдвинулись после рефакторинга — использовать функцию/класс)
   - обновить раздел `Last reviewed:`
3. Зафиксировать новые findings в `audit/project-audit.md` (если есть).
4. Зафиксировать закрытые findings (как RESOLVED).

Output:
- обновлённые docs/* файлы
- summary изменений

Ограничения:
- не фиксировать конкретные версии в тексте (см. conventions.md)
- сохранить anchor-ссылки актуальными
```

## P-06. Code review (5 осей)

```text
Ты — code-reviewer agent. Skill: agent-skills:code-review-and-quality.

Цель: review diff по 5 осям.

Inputs:
- exact clean committed base/head/tree candidate (local, review branch or PR)
- spec / plan / acceptance criteria
- docs/audit/project-audit.md (для контекста — какие проблемы уже известны)
- docs/architecture/ha-compatibility.md (для HA-проверок)
- conventions.md

Оси:
1. Correctness — функционирует ли правильно? edge cases?
2. Readability — понятен ли код через 6 месяцев?
3. Architecture — соответствует ли паттернам проекта? нет ли cycles?
4. Security — нет ли утечек / уязвимостей?
5. Performance — нет ли blocking I/O / лишних запросов?

Output:
- список замечаний по каждой оси
- severity per finding
- approve / changes requested

Ограничения:
- reviewer не участвовал в implementation и работает read-only
- self-review не закрывает REVIEW_OK
- все Critical/Important findings требуют fix, новый freeze и re-review до merge
- не повторять автоматически проверяемое (linter)
- сосредоточиться на том, что машина не поймает
```

## P-07. Спроектировать новую entity платформу

```text
Ты — Architecture Agent + HA Expert Agent.

Цель: спроектировать новую entity платформу (например, switch для включения/выключения уведомлений).

Inputs:
- описание use case
- docs/architecture/overview.md
- docs/architecture/ha-compatibility.md
- docs/architecture/quality-scale.md

Действия:
1. Surface assumptions явно.
2. Определить:
   - нужна ли отдельная platform или достаточно атрибута существующей
   - какой `device_class` / `state_class`
   - `unique_id` (стабильный, без `name`)
   - `device_info` (привязка к place)
   - `_attr_has_entity_name` + `translation_key`
3. Влияет ли на config-flow (новые поля)?
4. Влияет ли на migration?

Output:
- ADR-шаблон с decision
- list файлов, которые будут затронуты
- migration plan (если нужен)

Ограничения:
- не писать код в этой задаче — только дизайн
- не предлагать «breaking changes» без явного user-impact analysis
```

## P-08. Спроектировать ADR

```text
Ты — Architecture Agent + Documentation Agent. Skill: agent-skills:documentation-and-adrs.

Цель: записать архитектурное решение в docs/decisions/NNNN-title.md.

Inputs:
- контекст решения (issue / discussion / PR)
- docs/decisions/ (для нумерации)
- templates/adr.template.md

Шаблон:
- Status (proposed/accepted/rejected/deprecated/superseded by NNNN)
- Date
- Context (что заставило задуматься)
- Decision (что выбрали)
- Consequences (positive/negative/neutral)
- Alternatives considered (если применимо)

Output:
- новый файл docs/decisions/NNNN-kebab-title.md
- обновление docs/decisions/README.md (index)

Ограничения:
- ADR не редактируется после accepted; для изменения — новый ADR с пометкой "supersedes NNNN"
- не делать ADR для тривиальных решений
```

## Принципы

1. **Не использовать prompt с другого LLM-инструмента дословно.** Этот project имеет свои conventions.
2. **Prompts — не магия.** Каждый агент должен прочитать referenced docs.
3. **Output формат — обязательная часть prompt.** Без него — каша.
4. **Constraints важнее, чем инструкции.** "Что нельзя" гасит галлюцинации.

## Next reading

- For skills: `skills.md`
- For agents: `../../.claude/agents/`
- For commands: `../../.claude/commands/`
- For MCP tools: `mcp-tools.md`
