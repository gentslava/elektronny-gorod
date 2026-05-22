Status: Active
Owner: Documentation / AIDD Agent
Last reviewed: 2026-05-22

Source files:
- этот документ

Related docs:
- `skills.md`
- `multi-agent-workflow.md`
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

## P-02. Security check на утечки токенов

```text
Ты — Security & Privacy Agent. Skill: agent-skills:security-and-hardening.

Цель: убедиться, что в diff (или в коде на HEAD) нет логирования секретов.

Inputs:
- diff PR ИЛИ снепшот файлов custom_components/elektronny_gorod/*.py
- ../audit/security.md

Действия:
1. grep -rE "LOGGER\.(debug|info|warning|error|exception)\(.*(token|password|sms|headers|entry\.data|api_key)" custom_components/
2. Для каждой находки оценить: это новая утечка или известная (S-NN).
3. Для каждой новой — recommended fix + ссылка на S-NN или предложение нового ID.

Output:
- список совпадений с file:line
- severity per finding
- список redaction-helper-ов, которые нужно добавить

Ограничения:
- не «исправлять» молча, только отчёт
- не подавлять предупреждения
```

## P-03. Сгенерировать тесты config_flow

```text
Ты — QA Agent. Skill: agent-skills:test-driven-development.

Цель: создать pytest-тесты для config_flow по плану docs/testing/strategy.md.

Inputs:
- custom_components/elektronny_gorod/config_flow.py
- docs/testing/strategy.md (раздел "1. Config flow")
- tests/conftest.py
- pytest-homeassistant-custom-component docs

Действия:
1. Перечитай config_flow.py, идентифицируй все steps и error/abort пути.
2. Для каждого test case из strategy.md — напиши тест.
3. Используй `aioresponses` для мокирования HTTP.
4. Используй `MockConfigEntry` для duplicate-entry проверок.

Output:
- новый файл `tests/test_config_flow.py` (полностью переписанный)
- если test fails — НЕ упрощать тест; зафиксировать как баг и предложить исправление в коде.

Ограничения:
- не использовать `unittest.mock.patch` где можно `aioresponses`
- не «зелёные» тесты ценой потери проверки
- не импортировать несуществующие сущности
```

## P-04. Подготовить hotfix-релиз для security-фиксов

```text
Ты — DevOps / Release Agent. Skill: agent-skills:shipping-and-launch.

Цель: подготовить hotfix-релиз с security-фиксами (S-01..S-05).

Inputs:
- diff с фиксами
- docs/audit/security.md
- .github/workflows/release.yaml

Действия:
1. Проверить, что все P0 из audit/security.md закрыты.
2. Сформировать CHANGELOG entry: что было, что стало, как пользователь должен реагировать (рекомендовать перевыпуск токена).
3. Подготовить release notes.
4. Проверить: `grep -rE "LOGGER\..*(token|headers|entry\.data)" custom_components/` → пусто.

Output:
- черновик release notes
- список действий пользователя в notes (если нужно)
- ответ: готов ли релиз (все P0 closed + tests pass + hassfest pass).

Ограничения:
- не релизить, пока есть открытые P0
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
- diff PR
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
