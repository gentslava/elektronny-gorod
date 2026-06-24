"""Парсинг SIP-сообщения с сохранением множественных заголовков.

🔴 Урок спайка (research-spike.md D1): voip-utils хранит заголовки в dict[str,str]
и теряет повторяющиеся Via/Record-Route. Kazoo шлёт несколько Via/Record-Route +
компактные формы (v/f/t/i/m); валидный 200 OK/BYE обязан эхо-ить их ВСЕ дословно.
Поэтому храним (нормализованное_имя, сырая_строка) в порядке прихода:
- `raw_lines(name)` — дословные строки для эхо;
- `first(name)`/`values(name)` — value-часть для извлечения dialog-state.
"""
from __future__ import annotations

from dataclasses import dataclass

# Компактные формы SIP-заголовков (RFC 3261 §7.3.3) -> полные имена.
_COMPACT = {
    "v": "via",
    "f": "from",
    "t": "to",
    "i": "call-id",
    "m": "contact",
    "l": "content-length",
    "c": "content-type",
    "s": "subject",
    "k": "supported",
    "e": "content-encoding",
}

_HEADER_BODY_SEP = "\r\n\r\n"


def _norm(name: str) -> str:
    """Нормализовать имя заголовка: lower + раскрыть компактную форму."""
    n = name.strip().lower()
    return _COMPACT.get(n, n)


@dataclass
class SipMessage:
    """Разобранное SIP-сообщение с multi-header-safe доступом."""

    start_line: str
    # (нормализованное_имя, сырая_строка) в порядке прихода — дословно для эхо.
    header_lines: list[tuple[str, str]]
    body: str

    def raw_lines(self, name: str) -> list[str]:
        """Дословные строки заголовка (для эхо в 200 OK/BYE)."""
        nn = _norm(name)
        return [raw for hn, raw in self.header_lines if hn == nn]

    def values(self, name: str) -> list[str]:
        """Value-части всех вхождений заголовка."""
        nn = _norm(name)
        return [
            raw.partition(":")[2].strip()
            for hn, raw in self.header_lines
            if hn == nn
        ]

    def first(self, name: str) -> str | None:
        """Value-часть первого вхождения заголовка или None."""
        vals = self.values(name)
        return vals[0] if vals else None


def parse_sip(raw: str) -> SipMessage:
    """Разобрать сырое SIP-сообщение в `SipMessage`."""
    head, _, body = raw.partition(_HEADER_BODY_SEP)
    lines = head.split("\r\n")
    start_line = lines[0] if lines else ""
    header_lines: list[tuple[str, str]] = []
    for ln in lines[1:]:
        if ":" not in ln:
            continue
        name = ln.partition(":")[0].strip()
        header_lines.append((_norm(name), ln))
    return SipMessage(start_line, header_lines, body)
