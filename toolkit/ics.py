"""Minimal, dependency-free reader for busy times in .ics (iCalendar) exports.

Handles what Outlook / Google / Apple exports typically contain: folded lines,
UTC times (Z), TZID-qualified local times, floating times and all-day events.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


def _unfold(text: str) -> list[str]:
    out: list[str] = []
    for raw in text.splitlines():
        if raw[:1] in (" ", "\t") and out:
            out[-1] += raw[1:]
        else:
            out.append(raw)
    return out


def _parse_dt(prop: str, value: str, default_tz: str) -> tuple[datetime, bool]:
    params = dict(p.split("=", 1) for p in prop.split(";")[1:] if "=" in p)
    if params.get("VALUE") == "DATE" or (len(value) == 8 and value.isdigit()):
        d = datetime.strptime(value, "%Y%m%d")
        return d.replace(tzinfo=ZoneInfo(params.get("TZID", default_tz))), True
    if value.endswith("Z"):
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=ZoneInfo("UTC")), False
    tz = ZoneInfo(params.get("TZID", default_tz))
    return datetime.strptime(value, "%Y%m%dT%H%M%S").replace(tzinfo=tz), False


def read_ics_busy(path: str | Path, default_tz: str = "UTC") -> list[tuple[datetime, datetime, str]]:
    """Return (start, end, summary) for every VEVENT that is not marked free/cancelled."""
    events, current = [], None
    for line in _unfold(Path(path).read_text(encoding="utf-8")):
        if line == "BEGIN:VEVENT":
            current = {}
        elif line == "END:VEVENT" and current is not None:
            if current.get("start") and current.get("status") != "CANCELLED" and current.get("transp") != "TRANSPARENT":
                start, all_day = current["start"]
                if current.get("end"):
                    end = current["end"][0]
                else:
                    end = start + (timedelta(days=1) if all_day else timedelta(hours=1))
                events.append((start, end, current.get("summary", "Busy")))
            current = None
        elif current is not None and ":" in line:
            prop, value = line.split(":", 1)
            name = prop.split(";")[0].upper()
            if name == "DTSTART":
                current["start"] = _parse_dt(prop, value, default_tz)
            elif name == "DTEND":
                current["end"] = _parse_dt(prop, value, default_tz)
            elif name == "SUMMARY":
                current["summary"] = value.replace("\\,", ",")
            elif name == "STATUS":
                current["status"] = value.upper()
            elif name == "TRANSP":
                current["transp"] = value.upper()
    return events


def write_invite(path: str | Path, title: str, start: datetime, end: datetime, location: str,
                 description: str, organiser_email: str, attendees: list[tuple[str, str]]) -> Path:
    """Write a single-event .ics invite that Outlook / Google Calendar can import."""
    fmt = "%Y%m%dT%H%M%SZ"
    utc = ZoneInfo("UTC")
    esc = lambda s: s.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//EA Office Automation Toolkit//EN", "METHOD:REQUEST",
        "BEGIN:VEVENT",
        f"UID:{start.astimezone(utc).strftime(fmt)}-{hashlib.md5(title.encode()).hexdigest()[:10]}@ea-toolkit.example",
        f"DTSTAMP:{datetime.now(utc).strftime(fmt)}",
        f"DTSTART:{start.astimezone(utc).strftime(fmt)}",
        f"DTEND:{end.astimezone(utc).strftime(fmt)}",
        f"SUMMARY:{esc(title)}",
        f"LOCATION:{esc(location)}",
        f"DESCRIPTION:{esc(description)}",
        f"ORGANIZER:mailto:{organiser_email}",
    ]
    lines += [f"ATTENDEE;CN={esc(n)};ROLE=REQ-PARTICIPANT:mailto:{e}" for n, e in attendees]
    lines += ["END:VEVENT", "END:VCALENDAR"]
    p = Path(path)
    p.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")
    return p
