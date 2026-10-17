"""Find meeting slots that work for every attendee across time zones and work weeks.

Rules applied to every candidate slot:
* inside each attendee's local working hours, on one of their working days
  (e.g. Sun-Thu in KSA, Mon-Fri in the UAE/UK/India);
* no overlap with anyone's busy blocks (CSV and/or .ics exports);
* optional Gulf weekend guard: never propose Friday/Saturday in the organiser's zone;
* optional prayer-friendly buffers around Dhuhr, Asr and Maghrib in the organiser's city.
Slots are ranked so the most comfortable times (furthest from anyone's start or
end of day) come first, spread across different days.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from toolkit.common import read_csv
from toolkit.ics import read_ics_busy
from toolkit.prayer import prayer_blocks

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def parse_work_days(spec: str) -> set[int]:
    """'Sun-Thu' -> {6,0,1,2,3}; 'Mon,Wed' -> {0,2}. Monday is 0."""
    result: set[int] = set()
    for part in spec.replace(" ", "").split(","):
        if "-" in part:
            a, b = (DAYS.index(x[:3].title()) for x in part.split("-"))
            i = a
            while True:
                result.add(i)
                if i == b:
                    break
                i = (i + 1) % 7
        elif part:
            result.add(DAYS.index(part[:3].title()))
    return result


@dataclass
class Attendee:
    name: str
    role: str
    email: str
    timezone: str
    city: str
    work_start: time
    work_end: time
    work_days: set[int]
    busy: list[tuple[datetime, datetime, str]] = field(default_factory=list)

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


@dataclass
class Slot:
    start: datetime
    end: datetime
    score: float
    local_times: dict[str, str]
    notes: list[str] = field(default_factory=list)


def load_attendees(attendees_csv: str | Path, busy_csv: str | Path | None = None,
                   ics_files: dict[str, str | Path] | None = None) -> list[Attendee]:
    people = []
    for r in read_csv(attendees_csv):
        people.append(Attendee(
            name=r["name"], role=r.get("role", ""), email=r.get("email", ""), timezone=r["timezone"],
            city=r.get("city", ""), work_start=time.fromisoformat(r["work_start"]),
            work_end=time.fromisoformat(r["work_end"]), work_days=parse_work_days(r["work_days"]),
        ))
    by_name = {p.name: p for p in people}
    if busy_csv:
        for r in read_csv(busy_csv):
            if r["attendee"] not in by_name:
                raise ValueError(f"Busy block for unknown attendee: {r['attendee']}")
            p = by_name[r["attendee"]]
            start, end = datetime.fromisoformat(r["start"]), datetime.fromisoformat(r["end"])
            if start.tzinfo is None:
                start, end = start.replace(tzinfo=p.tz), end.replace(tzinfo=p.tz)
            p.busy.append((start, end, r.get("title", "Busy")))
    for name, path in (ics_files or {}).items():
        if name not in by_name:
            raise ValueError(f".ics file given for unknown attendee: {name}")
        by_name[name].busy.extend(read_ics_busy(path, default_tz=by_name[name].timezone))
    return people


def _overlaps(a0, a1, b0, b1) -> bool:
    return a0 < b1 and b0 < a1


def find_slots(attendees: list[Attendee], start_date: date, end_date: date, duration_min: int = 60,
               organiser_tz: str = "Asia/Riyadh", step_min: int = 15, gulf_weekend: bool = True,
               prayer_city: str | None = None, prayer_buffer_min: int = 20, max_results: int = 5,
               max_per_day: int = 2) -> list[Slot]:
    org = ZoneInfo(organiser_tz)
    dur, step = timedelta(minutes=duration_min), timedelta(minutes=step_min)
    candidates: list[Slot] = []
    day = start_date
    while day <= end_date:
        if gulf_weekend and day.weekday() in (4, 5):  # Fri, Sat
            day += timedelta(days=1)
            continue
        blocks = prayer_blocks(day, prayer_city, prayer_buffer_min) if prayer_city else []
        t = datetime.combine(day, time(0), org)
        day_end = t + timedelta(days=1)
        while t + dur <= day_end:
            s = _evaluate(t, t + dur, attendees, blocks)
            if s:
                candidates.append(s)
            t += step
        day += timedelta(days=1)

    candidates.sort(key=lambda s: (-s.score, s.start))
    chosen: list[Slot] = []
    per_day: dict[date, int] = {}
    for s in candidates:
        d = s.start.date()
        if per_day.get(d, 0) >= max_per_day:
            continue
        if any(_overlaps(s.start, s.end, c.start, c.end) for c in chosen):
            continue
        chosen.append(s)
        per_day[d] = per_day.get(d, 0) + 1
        if len(chosen) == max_results:
            break
    return sorted(chosen, key=lambda s: s.start)


def _evaluate(start: datetime, end: datetime, attendees: list[Attendee], blocks) -> Slot | None:
    margins, local = [], {}
    for p in attendees:
        ls, le = start.astimezone(p.tz), end.astimezone(p.tz)
        if ls.weekday() not in p.work_days or ls.date() != le.date():
            return None
        ws = datetime.combine(ls.date(), p.work_start, p.tz)
        we = datetime.combine(ls.date(), p.work_end, p.tz)
        if ls < ws or le > we:
            return None
        if any(_overlaps(start, end, b0, b1) for b0, b1, _ in p.busy):
            return None
        margins.append(min((ls - ws).total_seconds(), (we - le).total_seconds()) / 60)
        local[p.name] = f"{ls:%a %H:%M}-{le:%H:%M} ({p.city})"
    if any(_overlaps(start, end, b0, b1) for b0, b1, _ in blocks):
        return None
    notes = []
    if blocks:
        nxt = [b for b in blocks if b[0] >= end]
        if nxt:
            gap = int((nxt[0][0] - end).total_seconds() // 60)
            prayer = nxt[0][2].split(" prayer")[0]
            notes.append(f"ends {gap} min before the {prayer} prayer buffer ({nxt[0][0]:%H:%M})")
    # Score: comfort (smallest margin to anyone's day edge), lightly preferring earlier days.
    score = min(margins) - 0.01 * start.timetuple().tm_yday
    return Slot(start, end, round(score, 2), local, notes)
