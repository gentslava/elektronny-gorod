# Camera Archive Media Source Implementation Plan

> **For agentic workers:** Use the subagent-driven development workflow (recommended) or a task-by-task execution with checkpoints. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Browse forpost camera motion-event history by place → camera → day in the HA Media Browser and play each event's mp4 clip through a signed URL resolved on demand.

**Architecture:** New integration platform `media_source.py` (auto-discovered by HA's `media_source` component, no manifest change) builds a browse tree from `coordinator.data` + one `query_camera_events` call per day folder, and resolves playable events through a new `api.query_event_download`. Opaque IDs only; signed URLs are transient and never logged or persisted.

**Tech Stack:** Python 3.12+/3.14, Home Assistant 2024.10.4 and 2026.5.4 (both CI pins), pytest + pytest-homeassistant-custom-component.

**Spec:** [`docs/specs/2026-08-29-media-source-design.md`](../specs/2026-08-29-media-source-design.md)

## Global Constraints

- HA compatibility floor 2024.10.4 (PHC 0.13.175) and ceiling 2026.5.4 (PHC 0.13.333) — both use the `MediaSourceItem`-based `async_browse_media`/`async_resolve_media` API; never import APIs absent from 2024.10.4.
- Never log signed URLs, tokens, or headers content; `LOGGER`/logging uses `%`-formatting only, never f-strings.
- No blocking I/O in the event loop; all HTTP goes through the existing `api.py` → `HTTP` layer (shared `async_get_clientsession`).
- No new entities, storage, config options, config-entry migrations, or manifest changes.
- Error messages are plain English via `Unresolvable`/`BrowseError`; no translation keys (spec "Error mapping").
- Tests run locally with: `PYTHONPATH=. .venv/bin/pytest <file> -q` (bootstrap in Task 1, Step 0). CI runs the same tests on both PHC pins.
- Commit style: conventional commits (`feat:`, `test:`, `docs:`).
- `custom_components/**` changes are covered by this plan's approval; anything outside the files listed here requires user confirmation first (repo ask-first rule).

---

### Task 1: API wrapper — `query_event_download` + `ForpostDownloadError`

**Files:**
- Modify: `custom_components/elektronny_gorod/api.py` (add exception near the other DTOs at ~line 58, add method after `query_camera_events` ending at line 309)
- Test: `tests/test_api_media.py` (new)

**Interfaces:**
- Consumes: `self.http.get` (raises `ClientError` wrapping the `ClientResponse` for non-2xx, see `custom_components/elektronny_gorod/http.py:143-147`)
- Produces: `ForpostDownloadError(error_code: str | None)` exception class; `async def query_event_download(self, event_id: str) -> str` returning the signed mp4 URL string

- [ ] **Step 0: Bootstrap the local test environment (once for the whole plan)**

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements_test.txt pytest-homeassistant-custom-component==0.13.333
PYTHONPATH=. .venv/bin/pytest tests/test_api_history.py -q
```

Expected: existing API history tests PASS (bootstrap sanity).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_api_media.py`:

```python
"""Contract tests for the forpost event-download API wrapper."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from aiohttp import ClientError, ClientResponse

from custom_components.elektronny_gorod.api import (
    ForpostDownloadError,
    ElektronnyGorodAPI,
)
from custom_components.elektronny_gorod.user_agent import UserAgent


def _api(hass) -> ElektronnyGorodAPI:
    return ElektronnyGorodAPI(hass, UserAgent())


def _response(payload) -> MagicMock:
    response = MagicMock(spec=ClientResponse)
    response.json = AsyncMock(return_value=payload)
    return response


async def test_query_event_download_returns_signed_url(hass) -> None:
    """The endpoint returns `data` as a plain URL string, not an object."""
    api = _api(hass)
    api.http.get = AsyncMock(
        return_value=_response({"data": "https://myhome-savevideo.example/abc.mp4"})
    )

    url = await api.query_event_download("3001")

    api.http.get.assert_awaited_once_with(
        "/rest/v1/forpost/events/3001/downloads?container=mp4"
    )
    assert url == "https://myhome-savevideo.example/abc.mp4"


async def test_query_event_download_missing_data_is_no_recording(hass) -> None:
    """HTTP 200 with empty data degrades to a typed no-recording error."""
    api = _api(hass)
    api.http.get = AsyncMock(return_value=_response({"data": None}))

    try:
        await api.query_event_download("3001")
    except ForpostDownloadError as ex:
        assert ex.error_code is None
    else:
        raise AssertionError("ForpostDownloadError not raised")


async def test_query_event_download_parses_forpost_error_code(hass) -> None:
    """HTTP 500 business errors carry errorCode in the JSON body."""
    api = _api(hass)
    failed = _response({"errorCode": "11005", "errorMessage": "Архив доступен с 01.01"})
    api.http.get = AsyncMock(side_effect=ClientError(failed))

    try:
        await api.query_event_download("3001")
    except ForpostDownloadError as ex:
        assert ex.error_code == "11005"
    else:
        raise AssertionError("ForpostDownloadError not raised")


async def test_query_event_download_non_json_error_body(hass) -> None:
    """A non-JSON error body still yields a typed error with no code."""
    api = _api(hass)
    failed = MagicMock(spec=ClientResponse)
    failed.json = AsyncMock(side_effect=ValueError("not json"))
    api.http.get = AsyncMock(side_effect=ClientError(failed))

    try:
        await api.query_event_download("3001")
    except ForpostDownloadError as ex:
        assert ex.error_code is None
    else:
        raise AssertionError("ForpostDownloadError not raised")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_api_media.py -q`
Expected: FAIL — `ImportError: cannot import name 'ForpostDownloadError'`

- [ ] **Step 3: Implement in `api.py`**

Add `ClientError` to the existing aiohttp import (line 11): `from aiohttp import ClientError, ClientResponse`.

Add after the `CameraHistoryEvent` dataclass (line ~58):

```python
class ForpostDownloadError(Exception):
    """Forpost event-download failure with a parsed backend error code."""

    def __init__(self, error_code: str | None) -> None:
        super().__init__(f"forpost_download_failed_{error_code or 'unknown'}")
        self.error_code = error_code
```

Add method to `ElektronnyGorodAPI` after `query_camera_events`:

```python
    async def query_event_download(self, event_id: str) -> str:
        """Query the signed mp4 download URL for one forpost event."""
        api_url = f"/rest/v1/forpost/events/{event_id}/downloads?container=mp4"
        try:
            response = await self.http.get(api_url)
        except ClientError as ex:
            error_code: str | None = None
            if ex.args and isinstance(ex.args[0], ClientResponse):
                try:
                    error_body = await ex.args[0].json()
                except Exception:  # noqa: BLE001 - non-JSON bodies degrade
                    error_body = None
                if isinstance(error_body, dict) and error_body.get("errorCode"):
                    error_code = str(error_body["errorCode"])
            raise ForpostDownloadError(error_code) from ex
        if not isinstance(response, ClientResponse):
            raise TypeError(f"Unexpected response type: {type(response)!r}")
        payload = await response.json()
        url = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(url, str) or not url:
            raise ForpostDownloadError(None)
        return url
```

Note: the implementation must never log `url` or `error_body`. `errorMessage` from the backend is deliberately discarded (localized backend text is not shown to the user).

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_api_media.py -q`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add custom_components/elektronny_gorod/api.py tests/test_api_media.py
git commit -m "feat(api): add forpost event download wrapper with parsed error codes"
```

---

### Task 2: Media source skeleton + browse root (entries)

**Files:**
- Create: `custom_components/elektronny_gorod/media_source.py`
- Test: `tests/test_media_source.py` (new; this file grows in Tasks 3-6)

**Interfaces:**
- Consumes: `hass.data[DOMAIN][entry_id]` → coordinator (`.data` dict with `places`/`cameras`), `hass.config_entries.async_get_entry`
- Produces: `async def async_get_media_source(hass) -> ElektronnyGorodMediaSource`; `ElektronnyGorodMediaSource(hass)` with `async def async_browse_media(self, item: MediaSourceItem) -> BrowseMedia`; module-level helper `_uri(identifier: str) -> str`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_media_source.py`:

```python
"""Tests for the forpost camera archive Media Source."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.media_player import BrowseError
from homeassistant.components.media_source.error import Unresolvable
from homeassistant.components.media_source.models import MediaSourceItem
from homeassistant.helpers import entity_registry as er

from custom_components.elektronny_gorod.api import CameraHistoryEvent
from custom_components.elektronny_gorod.const import DOMAIN

_PLACE_ID = "1001"
_INTERCOM_ID = "111"
_PUBLIC_ID = "222"


def _coordinator(
    *,
    cameras: list | None = None,
    places: list | None = None,
    events: tuple = (),
) -> SimpleNamespace:
    return SimpleNamespace(
        api=SimpleNamespace(
            query_camera_events=AsyncMock(return_value=tuple(events)),
            query_event_download=AsyncMock(
                return_value="https://savevideo.example/signed-clip.mp4"
            ),
        ),
        data={
            "places": (
                places
                if places is not None
                else [{"place": {"id": _PLACE_ID, "address": "ул. Тестовая 1"}}]
            ),
            "cameras": (
                cameras
                if cameras is not None
                else [
                    {
                        "id": _INTERCOM_ID,
                        "name": "Подъезд",
                        "place_id": _PLACE_ID,
                        "source": "intercom",
                    },
                    {
                        "id": _PUBLIC_ID,
                        "name": "Двор",
                        "place_id": _PLACE_ID,
                        "source": "public",
                    },
                ]
            ),
        },
    )


def _entry(hass, coordinator, *, title: str = "Test Account") -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, title=title)
    entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    return entry


def _source(hass):
    from custom_components.elektronny_gorod.media_source import (
        ElektronnyGorodMediaSource,
    )

    return ElektronnyGorodMediaSource(hass)


def _item(hass, identifier: str) -> MediaSourceItem:
    return MediaSourceItem(
        hass=hass, domain=DOMAIN, identifier=identifier, target_media_player=None
    )


async def test_root_lists_entries_with_places(hass) -> None:
    entry = _entry(hass, _coordinator())
    _entry(hass, _coordinator(places=[]), title="Empty Account")

    result = await _source(hass).async_browse_media(_item(hass, ""))

    assert [child.title for child in result.children] == ["Test Account"]
    assert result.children[0].media_content_id == (
        f"media-source://{DOMAIN}/{entry.entry_id}"
    )
    assert result.children[0].can_expand is True
    assert result.children[0].can_play is False


async def test_root_without_entries_is_empty(hass) -> None:
    result = await _source(hass).async_browse_media(_item(hass, ""))
    assert result.children == []


async def test_browse_unknown_shape_raises(hass) -> None:
    with pytest.raises(BrowseError):
        await _source(hass).async_browse_media(_item(hass, "one-part"))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_media_source.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named ... media_source`

- [ ] **Step 3: Implement `media_source.py`**

```python
"""Native Media Source: forpost camera motion-event clips.

Browse: account entry → place → camera → day → events.
Resolve: one signed mp4 per event, fetched on demand and discarded.
Opaque IDs only — signed URLs are never logged or persisted
(spec: docs/specs/2026-08-29-media-source-design.md).
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.media_player import (
    BrowseError,
    BrowseMedia,
    MediaClass,
    MediaType,
)
from homeassistant.components.media_source.models import (
    MediaSource,
    MediaSourceItem,
)
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_SOURCE_TITLE = "Электронный город"


def _uri(identifier: str = "") -> str:
    """Build the media-source URI for one opaque identifier path."""
    return f"media-source://{DOMAIN}/{identifier}"


async def async_get_media_source(hass: HomeAssistant) -> ElektronnyGorodMediaSource:
    """Register the Elektronny Gorod archive as a HA media source."""
    return ElektronnyGorodMediaSource(hass)


class ElektronnyGorodMediaSource(MediaSource):
    """Forpost camera archive: motion-event clips per day."""

    name = _SOURCE_TITLE

    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__(DOMAIN)
        self._hass = hass

    def _coordinator(self, entry_id: str) -> Any | None:
        return (self._hass.data.get(DOMAIN) or {}).get(entry_id)

    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMedia:
        identifier = item.identifier or ""
        if not identifier:
            return self._browse_root()
        parts = identifier.split("/")
        if len(parts) == 2:
            raise BrowseError("Unknown media item")
        if len(parts) in (3, 4, 5):
            raise BrowseError("Unknown media item")
        raise BrowseError("Unknown media item")

    def _browse_root(self) -> BrowseMedia:
        children: list[BrowseMedia] = []
        for entry_id, coordinator in (self._hass.data.get(DOMAIN) or {}).items():
            entry = self._hass.config_entries.async_get_entry(entry_id)
            if entry is None or not (coordinator.data or {}).get("places"):
                continue
            children.append(
                self._folder(_uri(entry_id), entry.title)
            )
        children.sort(key=lambda child: child.title)
        return self._directory(_uri(), _SOURCE_TITLE, children)

    @staticmethod
    def _folder(
        identifier: str,
        title: str,
        *,
        children_media_class: MediaClass = MediaClass.DIRECTORY,
    ) -> BrowseMedia:
        return BrowseMedia(
            title=title,
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.VIDEOS,
            media_content_id=identifier,
            can_play=False,
            can_expand=True,
            children_media_class=children_media_class,
        )

    @staticmethod
    def _directory(
        identifier: str,
        title: str,
        children: list[BrowseMedia],
    ) -> BrowseMedia:
        return BrowseMedia(
            title=title,
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.VIDEOS,
            media_content_id=identifier,
            can_play=False,
            can_expand=True,
            children=children,
            children_media_class=(
                children[0].media_class if children else MediaClass.DIRECTORY
            ),
        )
```

(The `len(parts)` placeholder branches in `async_browse_media` are intentional scaffolding — Tasks 3-5 replace them. They must never silently succeed.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_media_source.py -q`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add custom_components/elektronny_gorod/media_source.py tests/test_media_source.py
git commit -m "feat(media_source): register archive source and browse account entries"
```

---

### Task 3: Browse place → cameras, hidden-camera gating, coordinator `place_id` fix

**Files:**
- Modify: `custom_components/elektronny_gorod/media_source.py`
- Modify: `custom_components/elektronny_gorod/coordinator.py:350-368` (add `"place_id"` to place/public camera dicts)
- Test: `tests/test_media_source.py` (extend)

**Interfaces:**
- Consumes: `er.async_get(hass)` registry, camera `unique_id = f"{DOMAIN}_camera_{camera_id}"`, `place_display_name(data, place_id)` from `history.py`
- Produces: `self._place_cameras(coordinator, place_id) -> list[dict]`, `self._camera_visible(camera_id) -> bool`, browse identifiers `f"{entry_id}/{place_id}"` and `f"{entry_id}/{place_id}/{camera_id}"`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_media_source.py`:

```python
def _hide_camera(hass, entry, camera_id: str) -> None:
    registry = er.async_get(hass)
    created = registry.async_get_or_create(
        "camera", DOMAIN, f"{DOMAIN}_camera_{camera_id}", config_entry=entry
    )
    entity_id = getattr(created, "entity_id", created)
    registry.async_update_entity(entity_id, hidden_by=er.RegistryEntryHider.USER)


async def test_place_lists_intercom_and_public_cameras(hass) -> None:
    entry = _entry(hass, _coordinator())

    result = await _source(hass).async_browse_media(
        _item(hass, f"{entry.entry_id}/{_PLACE_ID}")
    )

    assert [child.title for child in result.children] == ["Подъезд", "Двор"]
    assert result.children[0].media_content_id == (
        f"media-source://{DOMAIN}/{entry.entry_id}/{_PLACE_ID}/{_INTERCOM_ID}"
    )
    assert result.title == "ул. Тестовая 1"


async def test_place_omits_personal_and_hidden_cameras(hass) -> None:
    entry = _entry(
        hass,
        _coordinator(
            cameras=[
                {
                    "id": _INTERCOM_ID,
                    "name": "Подъезд",
                    "place_id": _PLACE_ID,
                    "source": "intercom",
                },
                {
                    "id": "333",
                    "name": "Личная",
                    "place_id": _PLACE_ID,
                    "source": "place",
                },
                {
                    "id": _PUBLIC_ID,
                    "name": "Двор",
                    "place_id": _PLACE_ID,
                    "source": "public",
                },
            ]
        ),
    )
    _hide_camera(hass, entry, _PUBLIC_ID)

    result = await _source(hass).async_browse_media(
        _item(hass, f"{entry.entry_id}/{_PLACE_ID}")
    )

    assert [child.title for child in result.children] == ["Подъезд"]


async def test_place_without_cameras_hidden_from_root(hass) -> None:
    entry = _entry(hass, _coordinator(cameras=[]))

    root = await _source(hass).async_browse_media(_item(hass, ""))

    assert root.children == []
    with pytest.raises(BrowseError):
        await _source(hass).async_browse_media(
            _item(hass, f"{entry.entry_id}/{_PLACE_ID}")
        )


async def test_unknown_place_raises_browse_error(hass) -> None:
    entry = _entry(hass, _coordinator())

    with pytest.raises(BrowseError):
        await _source(hass).async_browse_media(
            _item(hass, f"{entry.entry_id}/9999")
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_media_source.py -q`
Expected: new tests FAIL with `BrowseError: Unknown media item` (2-part branch not implemented)

- [ ] **Step 3: Implement browse place in `media_source.py`**

Add imports at the top:

```python
from homeassistant.helpers import entity_registry as er

from .history import place_display_name

_CAMERA_SOURCES = ("intercom", "public")
```

Replace the `len(parts) == 2` branch in `async_browse_media`:

```python
        if len(parts) == 2:
            return self._browse_place(*parts)
```

Add methods to `ElektronnyGorodMediaSource`:

```python
    def _camera_visible(self, camera_id: str) -> bool:
        registry = er.async_get(self._hass)
        entity_id = registry.async_get_entity_id(
            "camera", DOMAIN, f"{DOMAIN}_camera_{camera_id}"
        )
        if entity_id is None:
            return True
        entry = registry.async_get(entity_id)
        return entry is None or entry.hidden_by is None

    def _place_cameras(self, coordinator: Any, place_id: str) -> list[dict]:
        cameras: list[dict] = []
        for camera in (coordinator.data or {}).get("cameras") or []:
            if camera.get("source") not in _CAMERA_SOURCES:
                continue
            if str(camera.get("place_id") or "") != place_id:
                continue
            camera_id = str(camera.get("id") or "")
            if not camera_id or not self._camera_visible(camera_id):
                continue
            cameras.append(camera)
        return cameras

    def _place_ids(self, coordinator: Any) -> list[str]:
        place_ids: list[str] = []
        for subscriber_place in (coordinator.data or {}).get("places") or []:
            place_id = str((subscriber_place.get("place") or {}).get("id") or "")
            if place_id and self._place_cameras(coordinator, place_id):
                place_ids.append(place_id)
        return place_ids

    def _browse_place(self, entry_id: str, place_id: str) -> BrowseMedia:
        coordinator = self._coordinator(entry_id)
        if coordinator is None:
            raise BrowseError("Unknown media item")
        cameras = self._place_cameras(coordinator, place_id)
        if not cameras:
            raise BrowseError("Unknown media item")
        children = [
            self._folder(
                _uri(f"{entry_id}/{place_id}/{camera_id}"),
                str(camera.get("name") or camera_id),
            )
            for camera in cameras
            if (camera_id := str(camera.get("id") or ""))
        ]
        return self._directory(
            _uri(f"{entry_id}/{place_id}"),
            place_display_name(coordinator.data, place_id),
            children,
        )
```

Update `_browse_root` to use `_place_ids` instead of the raw places check:

```python
            if entry is None or not self._place_ids(coordinator):
                continue
```

- [ ] **Step 4: Add the coordinator `place_id` fix**

In `custom_components/elektronny_gorod/coordinator.py`, `_collect_cameras_for_place`: add `"place_id": place_id,` to the dict literals at lines 350-355 (place cameras) and 363-368 (public cameras), matching the intercom dicts at lines 322-330. Intercom device behavior is unaffected (`camera.py`/`event.py` gate intercom device grouping on `source == "intercom"`).

- [ ] **Step 5: Run tests to verify they pass**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_media_source.py -q`
Expected: all PASS. Also run the camera suite for regressions:

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_camera_hidden_skip.py tests/test_camera_auto_recovery.py -q
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add custom_components/elektronny_gorod/media_source.py custom_components/elektronny_gorod/coordinator.py tests/test_media_source.py
git commit -m "feat(media_source): browse places with hidden-camera gating; tag public cameras with place_id"
```

---

### Task 4: Browse camera → retention day folders

**Files:**
- Modify: `custom_components/elektronny_gorod/media_source.py`
- Test: `tests/test_media_source.py` (extend)

**Interfaces:**
- Consumes: identifier `f"{entry_id}/{place_id}/{camera_id}"`, `self._camera(...)` resolver (introduced here, reused by Tasks 5-6)
- Produces: `self._camera(entry_id, place_id, camera_id) -> dict | None` (validates source, place, visibility); day identifiers `f"{entry_id}/{place_id}/{camera_id}/{yyyymmdd}"`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_media_source.py`:

```python
async def test_camera_lists_retention_day_folders(hass) -> None:
    from homeassistant.util import dt as dt_util

    entry = _entry(hass, _coordinator())

    intercom = await _source(hass).async_browse_media(
        _item(hass, f"{entry.entry_id}/{_PLACE_ID}/{_INTERCOM_ID}")
    )
    public = await _source(hass).async_browse_media(
        _item(hass, f"{entry.entry_id}/{_PLACE_ID}/{_PUBLIC_ID}")
    )

    assert len(intercom.children) == 14
    assert len(public.children) == 7
    today = dt_util.now().date().isoformat()
    assert intercom.children[0].title == today
    assert intercom.children[0].media_content_id.endswith(
        dt_util.now().strftime("%Y%m%d")
    )


async def test_unknown_camera_raises_browse_error(hass) -> None:
    entry = _entry(hass, _coordinator())

    with pytest.raises(BrowseError):
        await _source(hass).async_browse_media(
            _item(hass, f"{entry.entry_id}/{_PLACE_ID}/999")
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_media_source.py -q`
Expected: new tests FAIL (`BrowseError` from the 3-part scaffold branch)

- [ ] **Step 3: Implement**

Add imports/constants in `media_source.py`:

```python
from datetime import date, datetime, timedelta

from homeassistant.util import dt as dt_util

_INTERCOM_RETENTION_DAYS = 14
_OTHER_RETENTION_DAYS = 7


def _recent_days(count: int) -> list[date]:
    today = dt_util.now().date()
    return [today - timedelta(days=offset) for offset in range(count)]
```

Replace the `len(parts) == 3` branch in `async_browse_media`:

```python
        if len(parts) == 3:
            return self._browse_camera(*parts)
```

Add methods:

```python
    def _camera(
        self, entry_id: str, place_id: str, camera_id: str
    ) -> dict[str, Any] | None:
        coordinator = self._coordinator(entry_id)
        if coordinator is None:
            return None
        for camera in (coordinator.data or {}).get("cameras") or []:
            if camera.get("source") not in _CAMERA_SOURCES:
                continue
            if str(camera.get("id") or "") != camera_id:
                continue
            if str(camera.get("place_id") or "") != place_id:
                continue
            if not self._camera_visible(camera_id):
                return None
            return camera
        return None

    def _browse_camera(
        self, entry_id: str, place_id: str, camera_id: str
    ) -> BrowseMedia:
        camera = self._camera(entry_id, place_id, camera_id)
        if camera is None:
            raise BrowseError("Unknown media item")
        retention = (
            _INTERCOM_RETENTION_DAYS
            if camera.get("source") == "intercom"
            else _OTHER_RETENTION_DAYS
        )
        base = f"{entry_id}/{place_id}/{camera_id}"
        children = [
            self._folder(
                _uri(f"{base}/{day.strftime('%Y%m%d')}"),
                day.isoformat(),
                children_media_class=MediaClass.VIDEO,
            )
            for day in _recent_days(retention)
        ]
        return self._directory(
            _uri(base), str(camera.get("name") or camera_id), children
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_media_source.py -q`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/elektronny_gorod/media_source.py tests/test_media_source.py
git commit -m "feat(media_source): retention-aware day folders per camera"
```

---

### Task 5: Browse day → motion events

**Files:**
- Modify: `custom_components/elektronny_gorod/media_source.py`
- Test: `tests/test_media_source.py` (extend)

**Interfaces:**
- Consumes: `coordinator.api.query_camera_events(camera_id, lower_date=..., upper_date=...) -> tuple[CameraHistoryEvent, ...]` (api.py:274), `CameraHistoryEvent` fields `id/timestamp/duration/event_subject_id/available/goto_enabled`
- Produces: event identifiers `f"{entry_id}/{place_id}/{camera_id}/{yyyymmdd}/{event_id}"` with `can_play = available and goto_enabled`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_media_source.py`:

```python
def _event(
    event_id: str = "3001",
    timestamp: int = 1770000000,
    duration: int = 12,
    subject: int = 126,
    available: bool = True,
    goto: bool = True,
) -> CameraHistoryEvent:
    return CameraHistoryEvent(
        id=event_id,
        camera_id=_INTERCOM_ID,
        backend_camera_id="4001",
        timestamp=timestamp,
        duration=duration,
        event_subject_id=subject,
        available=available,
        goto_enabled=goto,
    )


async def test_day_lists_motion_events_with_playability(hass) -> None:
    from homeassistant.util import dt as dt_util

    events = (
        _event(event_id="3002", timestamp=1770000060),
        _event(event_id="3001", timestamp=1770000000, goto=False),
        _event(event_id="9999", subject=99),
    )
    coordinator = _coordinator(events=events)
    entry = _entry(hass, coordinator)
    day = dt_util.as_local(dt_util.utc_from_timestamp(1770000000))
    day_str = day.strftime("%Y%m%d")
    day_start = dt_util.start_of_local_day(day)

    result = await _source(hass).async_browse_media(
        _item(hass, f"{entry.entry_id}/{_PLACE_ID}/{_INTERCOM_ID}/{day_str}")
    )

    coordinator.api.query_camera_events.assert_awaited_once_with(
        _INTERCOM_ID,
        lower_date=dt_util.as_utc(day_start).isoformat().replace("+00:00", "Z"),
        upper_date=dt_util.as_utc(day_start + timedelta(days=1))
        .isoformat()
        .replace("+00:00", "Z"),
    )
    assert [child.media_content_id.rsplit("/", 1)[-1] for child in result.children] == [
        "3002",
        "3001",
    ]
    assert result.children[0].can_play is True
    assert result.children[1].can_play is False
    assert result.children[0].title.endswith("· 12s")


async def test_day_api_failure_is_temporarily_unavailable(hass) -> None:
    from homeassistant.util import dt as dt_util

    coordinator = _coordinator()
    coordinator.api.query_camera_events.side_effect = RuntimeError("operator down")
    entry = _entry(hass, coordinator)
    day_str = dt_util.now().strftime("%Y%m%d")

    with pytest.raises(BrowseError, match="temporarily unavailable"):
        await _source(hass).async_browse_media(
            _item(hass, f"{entry.entry_id}/{_PLACE_ID}/{_INTERCOM_ID}/{day_str}")
        )


async def test_day_invalid_or_unknown_path_raises(hass) -> None:
    entry = _entry(hass, _coordinator())

    with pytest.raises(BrowseError, match="Unknown media item"):
        await _source(hass).async_browse_media(
            _item(hass, f"{entry.entry_id}/{_PLACE_ID}/{_INTERCOM_ID}/20261399")
        )
```

Add `from datetime import timedelta` to the test file imports.

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_media_source.py -q`
Expected: new tests FAIL (4-part scaffold branch)

- [ ] **Step 3: Implement**

Add constant:

```python
_MOTION_EVENT_SUBJECT_ID = 126
```

Replace the `len(parts) == 4` branch in `async_browse_media`:

```python
        if len(parts) == 4:
            return await self._browse_day(*parts)
```

Add methods:

```python
    async def _browse_day(
        self, entry_id: str, place_id: str, camera_id: str, day_str: str
    ) -> BrowseMedia:
        camera = self._camera(entry_id, place_id, camera_id)
        if camera is None or len(day_str) != 8 or not day_str.isdigit():
            raise BrowseError("Unknown media item")
        try:
            day = datetime.strptime(day_str, "%Y%m%d").date()
        except ValueError as err:
            raise BrowseError("Unknown media item") from err
        coordinator = self._coordinator(entry_id)
        day_start = dt_util.start_of_local_day(day)
        lower = dt_util.as_utc(day_start).isoformat().replace("+00:00", "Z")
        upper = (
            dt_util.as_utc(day_start + timedelta(days=1))
            .isoformat()
            .replace("+00:00", "Z")
        )
        try:
            events = await coordinator.api.query_camera_events(
                camera_id, lower_date=lower, upper_date=upper
            )
        except Exception:  # noqa: BLE001 - operator boundary
            raise BrowseError("Archive is temporarily unavailable") from None
        base = f"{entry_id}/{place_id}/{camera_id}/{day_str}"
        children = [
            BrowseMedia(
                title=self._event_title(event),
                media_class=MediaClass.VIDEO,
                media_content_type=MediaType.VIDEO,
                media_content_id=_uri(f"{base}/{event.id}"),
                can_play=bool(event.available and event.goto_enabled),
                can_expand=False,
            )
            for event in events
            if event.event_subject_id == _MOTION_EVENT_SUBJECT_ID
        ]
        return self._directory(_uri(base), day.isoformat(), children)

    @staticmethod
    def _event_title(event: Any) -> str:
        local = dt_util.as_local(dt_util.utc_from_timestamp(event.timestamp))
        return f"{local.strftime('%H:%M:%S')} · {event.duration}s"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_media_source.py -q`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/elektronny_gorod/media_source.py tests/test_media_source.py
git commit -m "feat(media_source): list motion events per day with playability flags"
```

---

### Task 6: Resolve + error mapping + log safety

**Files:**
- Modify: `custom_components/elektronny_gorod/media_source.py`
- Test: `tests/test_media_source.py` (extend)

**Interfaces:**
- Consumes: `query_event_download(event_id) -> str`, `ForpostDownloadError(error_code)` from Task 1; `Unresolvable` from `homeassistant.components.media_source.error`
- Produces: `async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia` with `mime_type="video/mp4"`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_media_source.py`:

```python
async def test_resolve_returns_play_media_for_valid_event(hass) -> None:
    from homeassistant.util import dt as dt_util

    coordinator = _coordinator()
    entry = _entry(hass, coordinator)
    day_str = dt_util.now().strftime("%Y%m%d")
    identifier = (
        f"{entry.entry_id}/{_PLACE_ID}/{_INTERCOM_ID}/{day_str}/3001"
    )

    play = await _source(hass).async_resolve_media(_item(hass, identifier))

    coordinator.api.query_event_download.assert_awaited_once_with("3001")
    assert play.url == "https://savevideo.example/signed-clip.mp4"
    assert play.mime_type == "video/mp4"


async def test_resolve_outside_retention(hass) -> None:
    from homeassistant.util import dt as dt_util
    from custom_components.elektronny_gorod.api import ForpostDownloadError

    coordinator = _coordinator()
    coordinator.api.query_event_download = AsyncMock(
        side_effect=ForpostDownloadError("11005")
    )
    entry = _entry(hass, coordinator)
    day_str = dt_util.now().strftime("%Y%m%d")

    with pytest.raises(Unresolvable, match="outside the retention window"):
        await _source(hass).async_resolve_media(
            _item(hass, f"{entry.entry_id}/{_PLACE_ID}/{_INTERCOM_ID}/{day_str}/3001")
        )


async def test_resolve_no_recording_and_transport_error(hass) -> None:
    from homeassistant.util import dt as dt_util
    from custom_components.elektronny_gorod.api import ForpostDownloadError

    day_str = dt_util.now().strftime("%Y%m%d")
    base = f"/{_PLACE_ID}/{_INTERCOM_ID}/{day_str}/3001"

    no_recording = _coordinator()
    no_recording.api.query_event_download = AsyncMock(
        side_effect=ForpostDownloadError(None)
    )
    entry_a = _entry(hass, no_recording)
    with pytest.raises(Unresolvable, match="not available"):
        await _source(hass).async_resolve_media(
            _item(hass, f"{entry_a.entry_id}{base}")
        )

    transport = _coordinator()
    transport.api.query_event_download = AsyncMock(
        side_effect=RuntimeError("operator down")
    )
    entry_b = _entry(hass, transport)
    with pytest.raises(Unresolvable, match="temporarily unavailable"):
        await _source(hass).async_resolve_media(
            _item(hass, f"{entry_b.entry_id}{base}")
        )


async def test_resolve_rejects_unknown_and_hidden_paths(hass) -> None:
    from homeassistant.util import dt as dt_util

    coordinator = _coordinator()
    entry = _entry(hass, coordinator)
    _hide_camera(hass, entry, _PUBLIC_ID)
    day_str = dt_util.now().strftime("%Y%m%d")

    with pytest.raises(Unresolvable, match="Unknown media item"):
        await _source(hass).async_resolve_media(
            _item(hass, f"{entry.entry_id}/{_PLACE_ID}/999/{day_str}/3001")
        )
    with pytest.raises(Unresolvable, match="Unknown media item"):
        await _source(hass).async_resolve_media(
            _item(hass, f"{entry.entry_id}/{_PLACE_ID}/{_PUBLIC_ID}/{day_str}/3001")
        )
    with pytest.raises(Unresolvable, match="Unknown media item"):
        await _source(hass).async_resolve_media(_item(hass, "too/few/parts"))


async def test_resolve_never_logs_signed_url(hass, caplog) -> None:
    import logging
    from homeassistant.util import dt as dt_util

    coordinator = _coordinator()
    entry = _entry(hass, coordinator)
    day_str = dt_util.now().strftime("%Y%m%d")
    caplog.set_level(logging.DEBUG)

    await _source(hass).async_resolve_media(
        _item(
            hass,
            f"{entry.entry_id}/{_PLACE_ID}/{_INTERCOM_ID}/{day_str}/3001",
        )
    )

    assert "savevideo.example" not in caplog.text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_media_source.py -q`
Expected: new tests FAIL with `NotImplementedError` from the `MediaSource` base

- [ ] **Step 3: Implement**

Add imports in `media_source.py`:

```python
from homeassistant.components.media_source.error import Unresolvable
from homeassistant.components.media_source.models import PlayMedia

from .api import ForpostDownloadError

_MIME_MP4 = "video/mp4"
```

Remove the remaining `len(parts) in (3, 4, 5)` scaffold branches, leaving:

```python
        raise BrowseError("Unknown media item")
```

Add method:

```python
    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        parts = (item.identifier or "").split("/")
        if len(parts) != 5:
            raise Unresolvable("Unknown media item")
        entry_id, place_id, camera_id, _day_str, event_id = parts
        coordinator = self._coordinator(entry_id)
        if coordinator is None or self._camera(
            entry_id, place_id, camera_id
        ) is None:
            raise Unresolvable("Unknown media item")
        try:
            url = await coordinator.api.query_event_download(event_id)
        except ForpostDownloadError as err:
            if err.error_code == "11005":
                raise Unresolvable(
                    "Archive is outside the retention window"
                ) from err
            raise Unresolvable("Recording is not available") from err
        except Exception:  # noqa: BLE001 - operator boundary
            raise Unresolvable("Archive is temporarily unavailable") from None
        return PlayMedia(url=url, mime_type=_MIME_MP4)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_media_source.py -q`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/elektronny_gorod/media_source.py tests/test_media_source.py
git commit -m "feat(media_source): resolve event clips via signed urls with retention errors"
```

---

### Task 7: HA registration, coordinator `place_id` end-to-end, multi-entry

**Files:**
- Test: `tests/test_media_source.py` (extend — no production changes expected; if registration fails, escalate per the spec's open-verification item before touching the manifest)

**Interfaces:**
- Consumes: `homeassistant.setup.async_setup_component`, `homeassistant.components.media_source.async_browse_media`, the full-integration mock pattern from `tests/test_camera_hidden_skip.py:78-105`
- Produces: proof that HA auto-discovers `media_source.py` (spec open-verification item 1)

- [ ] **Step 1: Write the tests**

Append to `tests/test_media_source.py`:

```python
def _full_config_entry() -> MockConfigEntry:
    import json

    from custom_components.elektronny_gorod.const import (
        CONF_ACCESS_TOKEN,
        CONF_OPERATOR_ID,
        CONF_REFRESH_TOKEN,
        CONF_USER_AGENT,
    )
    from custom_components.elektronny_gorod.user_agent import UserAgent

    ua = UserAgent()
    ua.operator_id = "1"
    return MockConfigEntry(
        domain=DOMAIN,
        version=3,
        unique_id="test_unique_subscriber_S1",
        title="Test",
        data={
            CONF_ACCESS_TOKEN: "T1",
            CONF_REFRESH_TOKEN: "R1",
            CONF_OPERATOR_ID: "1",
            CONF_USER_AGENT: json.dumps(ua.json()),
            "account_id": "A1",
            "subscriber_id": "S1",
            "use_go2rtc": False,
        },
    )


@pytest.fixture
def mock_full_api():
    from unittest.mock import patch

    from custom_components.elektronny_gorod.api import HistoryPage

    with patch(
        "custom_components.elektronny_gorod.coordinator.ElektronnyGorodAPI"
    ) as mock_cls:
        instance = mock_cls.return_value
        instance.http = AsyncMock()
        instance.http.user_agent = MagicMock()
        instance.query_places = AsyncMock(
            return_value=[
                {
                    "subscriber": {"id": "S1", "accountId": "A1", "name": "Test"},
                    "place": {"id": _PLACE_ID, "address": "ул. Тестовая 1"},
                }
            ]
        )
        instance.query_balance = AsyncMock(return_value={})
        instance.query_access_controls = AsyncMock(
            return_value=[
                {
                    "id": 2001,
                    "name": "Домофон",
                    "entrances": [
                        {
                            "id": 3001,
                            "name": "Подъезд",
                            "externalCameraId": int(_INTERCOM_ID),
                            "allowOpen": True,
                        }
                    ],
                }
            ]
        )
        instance.query_cameras = AsyncMock(return_value=[])
        instance.query_public_cameras = AsyncMock(
            return_value=[{"id": int(_PUBLIC_ID), "name": "Двор"}]
        )
        instance.query_screens_settings = AsyncMock(
            return_value={"screens": []}
        )
        instance.query_dnd_settings = AsyncMock(return_value=[])
        instance.query_events = AsyncMock(
            return_value=HistoryPage(events=(), number=0, last=True)
        )
        yield mock_cls


async def test_media_source_registered_on_integration_setup(
    hass, mock_full_api
) -> None:
    from homeassistant.components.media_source import async_browse_media
    from homeassistant.setup import async_setup_component

    assert await async_setup_component(hass, "media_source", {})
    entry = _full_config_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert DOMAIN in hass.data["media_source"]
    browse = await async_browse_media(hass, f"media-source://{DOMAIN}/")
    assert browse.children[0].title == "Test"


async def test_public_camera_grouped_under_place_end_to_end(
    hass, mock_full_api
) -> None:
    """The coordinator place_id fix routes public cameras into the place."""
    from homeassistant.components.media_source import async_browse_media
    from homeassistant.setup import async_setup_component

    assert await async_setup_component(hass, "media_source", {})
    entry = _full_config_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    place = await async_browse_media(
        hass, f"media-source://{DOMAIN}/{entry.entry_id}/{_PLACE_ID}"
    )
    assert [child.title for child in place.children] == ["Подъезд", "Двор"]


async def test_root_aggregates_multiple_entries(hass) -> None:
    _entry(hass, _coordinator(), title="Account B")
    _entry(hass, _coordinator(), title="Account A")

    result = await _source(hass).async_browse_media(_item(hass, ""))

    assert [child.title for child in result.children] == ["Account A", "Account B"]
```

- [ ] **Step 2: Run the tests**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_media_source.py -q`
Expected: all PASS. If `test_media_source_registered_on_integration_setup` fails because HA did not discover the platform, STOP and escalate: the spec's fallback (manifest `dependencies` addition) is an ask-first change — get user confirmation before editing `manifest.json`.

- [ ] **Step 3: Commit**

```bash
git add tests/test_media_source.py
git commit -m "test(media_source): HA registration, end-to-end place grouping, multi-entry root"
```

---

### Task 8: Docs sync + full verification

**Files:**
- Create: `docs/features/mobile-app-parity/media-source.md`
- Modify: `docs/features/mobile-app-parity/history-card.md:55`, `docs/features/mobile-app-parity/prd.md:41-44`, `docs/architecture/api-reference.md:923`, `AGENTS.md` (structure tree), `docs/testing/strategy.md` (coverage table + module tree)

**Interfaces:**
- Consumes: finished implementation; no code changes in this task

- [ ] **Step 1: Create `docs/features/mobile-app-parity/media-source.md`**

```markdown
# Архив камер через Media Source

Интеграция публикует нативный Home Assistant Media Source: журнал событий
движения камер («Электронный город» в Media Browser) с воспроизведением
mp4-клипов.

## Структура

Аккаунт → Адрес → Камера → День → События. Событие отображается строкой
«ЧЧ:ММ:СС · Ns»; серые строки — записи, недоступные для скачивания
(не сохранилась или истёк retention). Retention: 14 дней для домофонов,
7 дней для остальных камер.

## Воспроизведение

По клику интеграция запрашивает одноразовую подписанную ссылку
`forpost/events/{id}/downloads` и отдаёт её плееру. Ссылка нигде не
сохраняется и не логируется; каждый запуск получает свежую ссылку.
Ошибка «Archive is outside the retention window» означает запрос за
пределами окна хранения, «Recording is not available» — отсутствие записи.

## Доступ

Источник виден всем авторизованным пользователям Home Assistant (так же,
как встроенные media sources). Камеры, скрытые в реестре сущностей HA
(«Показывать на панели» выключен), исключаются из списка и из
воспроизведения. Личные камеры не входят в этот slice.

## Ограничения

- Перемотка/стриминг архива по таймлайну (как в мобильном приложении) не
  реализованы — только клипы по событиям.
- Эскизы событий не передаются; подписанные ссылки работают ограниченное
  время.
```

- [ ] **Step 2: Update the linked docs**

- `docs/features/mobile-app-parity/history-card.md:55` — replace the sentence about unimplemented playback with: «воспроизведение архивных видео реализовано отдельным Media Source — см. [`media-source.md`](media-source.md).»
- `docs/features/mobile-app-parity/prd.md` — mark checklist items 1-4 of "Durable history and archive" (`Camera archive is browseable...` through `IsGotoEnabled=0...`) as `[x]`.
- `docs/architecture/api-reference.md` — at the end of the `downloads` section (~line 923), replace the "potencial" note with: «Реализован в [`api.py:query_event_download`](../../custom_components/elektronny_gorod/api.py); browsing — `media_source.py` (spec: `docs/specs/2026-08-29-media-source-design.md`).»
- `AGENTS.md` — in the project structure tree, add after the `history_ws.py` line: `├── media_source.py        # HA Media Source: archive clips place → camera → day → event`.
- `docs/testing/strategy.md` — add `| Media Source archive | ... |` row to the coverage table following the "Durable history" row (line 43), and add `test_media_source.py` next to `test_history_ws.py` in the module tree (line 59).

- [ ] **Step 3: Full test suite**

```bash
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

Expected: PASS (existing 686+ tests plus the new ones)

- [ ] **Step 4: Commit**

```bash
git add docs/ AGENTS.md
git commit -m "docs: sync media source feature, PRD checklist and structure tree"
```

---

## Post-implementation gates (per repo contract)

1. Independent read-only `code-reviewer` + `ha-expert` + `security-auditor` reviews of the final candidate (signed-URL handling, log surface, registry gating, HA-version compatibility). `qa-engineer` reviews the test additions.
2. Fix Critical/Important findings and re-run the suite before any merge.
3. Fix the final candidate: clean worktree + base/head/tree SHA in the review record.
4. Runtime verification on a real account remains open after merge (spec "Open runtime-verification items" 2-3): browser playback behavior and signed-URL one-time semantics.
