"""Event log parsing and attribution, using XML recorded from EvtRender."""

from __future__ import annotations

from datetime import UTC, datetime

from compatsentinel.collectors import eventlog

# Recorded on Windows 11 (provider and computer names trimmed). Application
# Error 1000 lists the faulting app and module as positional Data elements.
APP_ERROR_XML = """<Event xmlns='http://schemas.microsoft.com/win/2004/08/events/event'>
<System><Provider Name='Application Error'/><EventID Qualifiers='0'>1000</EventID>
<Version>0</Version><Level>2</Level><Task>100</Task><Opcode>0</Opcode>
<Keywords>0x80000000000000</Keywords>
<TimeCreated SystemTime='2026-09-18T10:38:09.1664650Z'/><EventRecordID>78379</EventRecordID>
<Correlation/><Execution ProcessID='4152' ThreadID='0'/><Channel>Application</Channel>
<Computer>host</Computer><Security/></System>
<EventData><Data>Contoso.App.exe</Data><Data>3.2.1.0</Data><Data>0x66f2a1b3</Data>
<Data>KERNELBASE.dll</Data><Data>10.0.26100.4351</Data><Data>0xe06d7363</Data>
<Data>0x000000000002b45c</Data><Data>C:\\Program Files\\Contoso\\Contoso.App.exe</Data>
</EventData></Event>"""

OTHER_XML = """<Event xmlns='http://schemas.microsoft.com/win/2004/08/events/event'>
<System><Provider Name='THXUpdSvc'/><EventID Qualifiers='0'>2</EventID><Level>2</Level>
<TimeCreated SystemTime='2026-09-18T10:38:08.2793369Z'/><Channel>Application</Channel>
</System><EventData><Data>ERROR: getManifest: attempting fallback</Data></EventData></Event>"""


def test_query_filters_level_and_time_window() -> None:
    start = datetime(2026, 9, 18, 10, 0, tzinfo=UTC)
    end = datetime(2026, 9, 18, 10, 5, 30, 250000, tzinfo=UTC)
    query = eventlog.build_query(start, end)
    assert "(Level=1 or Level=2)" in query
    assert "@SystemTime>='2026-09-18T10:00:00.000000000Z'" in query
    assert "@SystemTime<='2026-09-18T10:05:30.250000000Z'" in query


def test_parse_application_error_event() -> None:
    entry = eventlog.parse_event(APP_ERROR_XML)
    assert entry.source == "Application Error"
    assert entry.event_id == 1000
    assert entry.level == "error"
    assert entry.log == "Application"
    assert entry.timestamp == datetime(2026, 9, 18, 10, 38, 9, 166465, tzinfo=UTC)
    assert entry.message.startswith("Contoso.App.exe | 3.2.1.0 | ")
    assert "KERNELBASE.dll" in entry.message


def test_parse_minimal_event() -> None:
    entry = eventlog.parse_event(OTHER_XML)
    assert entry.source == "THXUpdSvc"
    assert entry.event_id == 2
    assert entry.message == "ERROR: getManifest: attempting fallback"


def test_mentions_app_is_case_insensitive() -> None:
    entry = eventlog.parse_event(APP_ERROR_XML)
    assert eventlog.mentions_app(entry.message, {"contoso.app.exe"})
    assert not eventlog.mentions_app(entry.message, {"notepad.exe"})
    assert not eventlog.mentions_app(entry.message, {""})


def test_message_is_truncated() -> None:
    long = APP_ERROR_XML.replace("Contoso.App.exe", "x" * 5000, 1)
    assert len(eventlog.parse_event(long).message) == eventlog.MAX_MESSAGE_CHARS
