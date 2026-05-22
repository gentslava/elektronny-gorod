Status: Active
Owner: Documentation / AIDD Agent
Last reviewed: 2026-05-22

Source files:
- этот документ — индекс внешних источников

Related docs:
- `source-of-truth.md` (внутренние источники)
- `ha-compatibility.md`
- `contributing.md`

Used by agents:
- Все агенты при research-фазе

Quality gates:
- RESEARCH_DONE

---

# Source Base — внешние источники

Каталог внешних источников, на которые опирается этот проект и его AIDD-документация. Это **стартовая база**, не закрытый список. При обнаружении более актуальных источников — добавлять сюда.

## Уровни доверия

- **high** — официальная документация (HA, HACS, MCP, OpenAI, Anthropic).
- **medium** — Martin Fowler / Anthropic engineering blog / GitHub blog / Microsoft Developer.
- **low** — Habr / community posts / personal blogs.

При конфликте — high > medium > low.

## Home Assistant

| Источник | Тип | Доверие | Зачем |
|---|---|---|---|
| https://developers.home-assistant.io/ | official docs | high | основная dev-документация |
| https://developers.home-assistant.io/docs/creating_integration_manifest/ | official docs | high | `manifest.json` поля |
| https://developers.home-assistant.io/docs/core/integration/config_flow/ | official docs | high | config flow паттерны |
| https://developers.home-assistant.io/docs/creating_component_index/ | official docs | high | structure of integration |
| https://developers.home-assistant.io/docs/core/integration-quality-scale/ | official docs | high | Bronze/Silver/Gold/Platinum |
| https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/ | official docs | high | конкретные правила QS |
| https://developers.home-assistant.io/docs/core/integration-quality-scale/checklist/ | official docs | high | self-check |
| https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/config-flow-test-coverage/ | official docs | high | требования к тестам config_flow |
| https://github.com/home-assistant/core | source code | high | смотреть реализацию core-интеграций при сомнении |

## HACS

| Источник | Тип | Доверие | Зачем |
|---|---|---|---|
| https://www.hacs.xyz/docs/publish/start/ | official docs | high | general publish requirements |
| https://www.hacs.xyz/docs/publish/integration/ | official docs | high | integration-specific requirements |
| https://www.hacs.xyz/docs/publish/include/ | official docs | high | default repositories |

## AIDD / AI-DLC / Spec-driven / Context engineering

| Источник | Тип | Доверие | Зачем |
|---|---|---|---|
| https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents | engineering blog | medium | context engineering principles |
| https://martinfowler.com/articles/exploring-gen-ai/context-engineering-coding-agents.html | article | medium | context для coding agents |
| https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html | article | medium | spec-driven development уровни |
| https://addyosmani.com/blog/good-spec/ | blog | medium | как писать spec для AI |
| https://github.blog/ai-and-ml/generative-ai/spec-driven-development-with-ai-get-started-with-a-new-open-source-toolkit/ | official blog | medium | Spec Kit / GitHub |
| https://developer.microsoft.com/blog/spec-driven-development-spec-kit | official blog | medium | Spec Kit / Microsoft |
| https://developers.openai.com/codex/guides/build-ai-native-engineering-team | guide | medium | AI-native team practices |
| https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf | guide | medium | практическое руководство по агентам |
| https://habr.com/ru/articles/974924/ | community | low | «LLM как команда ролей» (RU) |
| https://habr.com/ru/articles/941934/ | community | low | про умный вайб-кодинг (RU) |
| https://vladislaveremeev.gitbook.io/qa_bible/ai-v-testirovanii/ai-driven-development | gitbook | low | QA Bible — AIDD (RU) |

## Agent-ready репозитории и инструкции

| Источник | Тип | Доверие | Зачем |
|---|---|---|---|
| https://agents.md/ | standard | high | стандарт AGENTS.md |
| https://developers.openai.com/codex/guides/agents-md | guide | high | OpenAI Codex AGENTS.md |
| https://developers.openai.com/codex/skills | guide | high | Codex Skills |
| https://developers.openai.com/codex/cli/reference | guide | high | Codex CLI |
| https://code.claude.com/docs/en/memory | guide | high | CLAUDE.md / memory |
| https://code.claude.com/docs/en/hooks | guide | high | Hooks |
| https://code.claude.com/docs/en/sub-agents | guide | high | Subagents |
| https://code.claude.com/docs/en/agent-teams | guide | high | Agent Teams |
| https://claude.com/blog/subagents-in-claude-code | blog | high | how/when to use subagents |
| https://docs.github.com/copilot/customizing-copilot/adding-custom-instructions-for-github-copilot | official docs | high | GitHub Copilot instructions |
| https://code.visualstudio.com/docs/copilot/customization/custom-instructions | official docs | high | VS Code custom instructions |
| https://cursor.com/blog/agent-best-practices | blog | high | Cursor agent practices |
| https://aider.chat/docs/usage/conventions.html | official docs | high | Aider conventions |

## MCP / Tools

| Источник | Тип | Доверие | Зачем |
|---|---|---|---|
| https://modelcontextprotocol.io/docs/getting-started/intro | official docs | high | MCP intro |
| https://www.anthropic.com/news/model-context-protocol | announcement | high | MCP overview |
| https://openai.github.io/openai-agents-python/mcp/ | official docs | high | OpenAI Agents SDK + MCP |
| https://developers.openai.com/api/docs/guides/agents | official docs | high | Agents API |

## Используется в этом проекте — внешние библиотеки

| Источник | Зачем |
|---|---|
| https://github.com/AlexxIT/go2rtc | референсная документация для интеграции go2rtc |
| https://docs.aiohttp.org/ | HTTP клиент |

## Что хотим добавить (TODO)

- [ ] Конкретные примеры HA-интеграций для российских сервисов (как референс).
- [ ] HA Brands repository ссылка после добавления brand-ассетов.
- [ ] Anthropic Claude Code best-practices snapshot.
- [ ] Список аналогичных HACS-интеграций других домофонов (для сравнения архитектуры).

## Принцип использования

1. **Сначала** — официальная HA / HACS документация.
2. **Затем** — реальный код HA core / похожих интеграций.
3. **Параллельно** — Context7 для актуальных API-снапшотов (`/Users/gentslava/.claude/rules/context7.md`).
4. **Для AIDD-методологии** — Anthropic / Martin Fowler / OpenAI / Microsoft.
5. **Для community-perspective** — Habr / Cursor blog / Aider docs.

Каждое значимое утверждение в AIDD-документах должно иметь evidence (источник из этого каталога или из `source-of-truth.md`).

## Next reading

- For internal source of truth: `source-of-truth.md`
- For HA-specific: `ha-compatibility.md`
- For contributing rules: `contributing.md`
