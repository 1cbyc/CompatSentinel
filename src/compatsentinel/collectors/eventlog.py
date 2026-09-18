"""Application event log errors raised during the run window, tied to the app.

Uses the modern ``EvtQuery`` API through pywin32 with an XPath filter, so only
Error and Critical events inside the window are read. Attribution is textual:
an event counts when its data mentions one of the app's image names. That is
how the usual sources report crashes: ``Application Error`` (1000) names the
faulting application, ``.NET Runtime`` (1026) prints ``Application: x.exe``,
``SideBySide`` names the manifest path and ``Windows Error Reporting`` (1001)
lists the app as P1.

Only the raw event data is stored, not the localized formatted message. It is
stable across languages and enough to attribute and diff.
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime

from compatsentinel.collectors.base import CollectorSkipped, RunContext
from compatsentinel.models import EventLogEntry

CHANNEL = "Application"
BATCH_SIZE = 64
MAX_MESSAGE_CHARS = 2000
NS = {"e": "http://schemas.microsoft.com/win/2004/08/events/event"}
LEVEL_NAMES = {1: "critical", 2: "error", 3: "warning", 4: "information", 5: "verbose"}


class EventLogCollector:
    name = "eventlog"
    requires_elevation = False

    def collect(self, ctx: RunContext) -> list[EventLogEntry]:
        if sys.platform != "win32":
            raise CollectorSkipped("Windows event log is only available on Windows")
        else:
            query = build_query(ctx.started_at, ctx.finished_at)
            entries = (parse_event(xml) for xml in query_events(CHANNEL, query))
            return [e for e in entries if mentions_app(e.message, ctx.image_names)]


# --- Pure helpers (unit tested on any OS) -----------------------------------------


def build_query(start: datetime, end: datetime) -> str:
    """XPath selecting Error/Critical events created inside ``[start, end]``."""
    return (
        "*[System[(Level=1 or Level=2) and "
        f"TimeCreated[@SystemTime>='{_xml_time(start)}' and @SystemTime<='{_xml_time(end)}']]]"
    )


def parse_event(xml_text: str) -> EventLogEntry:
    """Build an entry from the XML that ``EvtRender`` returns for one event."""
    root = ET.fromstring(xml_text)
    system = root.find("e:System", NS)
    if system is None:
        raise ValueError("event XML has no System element")

    provider = system.find("e:Provider", NS)
    time_created = system.find("e:TimeCreated", NS)
    level = int(_text(system.find("e:Level", NS)) or 0)
    data = [_text(node) for node in root.iterfind("e:EventData/e:Data", NS) if _text(node).strip()]
    message = " | ".join(data)[:MAX_MESSAGE_CHARS]

    return EventLogEntry(
        log=_text(system.find("e:Channel", NS)) or CHANNEL,
        source=provider.get("Name", "") if provider is not None else "",
        event_id=int(_text(system.find("e:EventID", NS)) or 0),
        level=LEVEL_NAMES.get(level, str(level)),
        timestamp=_parse_time(
            time_created.get("SystemTime", "") if time_created is not None else ""
        ),
        message=message,
    )


def mentions_app(text: str, image_names: Iterable[str]) -> bool:
    """True when any image name (e.g. ``notepad.exe``) appears in ``text``, ignoring case."""
    haystack = text.lower()
    return any(name and name.lower() in haystack for name in image_names)


def _xml_time(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f000Z")


def _parse_time(value: str) -> datetime:
    # Event times carry 7 fractional digits; fromisoformat accepts at most 6.
    cleaned = value.rstrip("Z")
    if "." in cleaned:
        head, fraction = cleaned.split(".", 1)
        cleaned = f"{head}.{fraction[:6]}"
    try:
        return datetime.fromisoformat(cleaned).replace(tzinfo=UTC)
    except ValueError:
        return datetime.fromtimestamp(0, tz=UTC)


def _text(node: ET.Element | None) -> str:
    return (node.text or "") if node is not None else ""


# --- Windows-only query ----------------------------------------------------------------


def query_events(channel: str, query: str) -> Iterator[str]:
    """Yield rendered XML for every event matching ``query``."""
    import pywintypes
    import win32evtlog

    handle = win32evtlog.EvtQuery(channel, win32evtlog.EvtQueryChannelPath, query)
    while True:
        try:
            batch = win32evtlog.EvtNext(handle, BATCH_SIZE)
        except pywintypes.error:
            return  # ERROR_NO_MORE_ITEMS
        if not batch:
            return
        for event in batch:
            yield win32evtlog.EvtRender(event, win32evtlog.EvtRenderEventXml)
