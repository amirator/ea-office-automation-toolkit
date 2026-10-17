from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pytest

from conftest import SAMPLE
from toolkit.ics import read_ics_busy
from toolkit.prayer import CITIES, prayer_times
from toolkit.scheduler import Attendee, find_slots, load_attendees, parse_work_days

RIYADH = ZoneInfo("Asia/Riyadh")


def person(name, tz, start="09:00", end="17:00", days="Mon-Fri", city="X"):
    return Attendee(name, "", f"{name}@x.example", tz, city, time.fromisoformat(start), time.fromisoformat(end),
                    parse_work_days(days))


def test_parse_work_days_wraps_week():
    assert parse_work_days("Sun-Thu") == {6, 0, 1, 2, 3}
    assert parse_work_days("Mon-Fri") == {0, 1, 2, 3, 4}
    assert parse_work_days("Mon,Wed") == {0, 2}


def test_gulf_weekend_and_work_week_respected():
    people = [person("a", "Asia/Riyadh", "08:00", "17:00", "Sun-Thu")]
    # Fri 6 Nov - Sun 8 Nov 2026: only Sunday is allowed.
    slots = find_slots(people, date(2026, 11, 6), date(2026, 11, 8), 60, max_results=10, max_per_day=10)
    assert slots and {s.start.astimezone(RIYADH).strftime("%a") for s in slots} == {"Sun"}


def test_slots_inside_everyones_hours_across_time_zones():
    people = [person("ksa", "Asia/Riyadh", "08:00", "17:00", "Sun-Thu"),
              person("uk", "Europe/London", "09:00", "17:30", "Mon-Fri")]
    slots = find_slots(people, date(2026, 11, 2), date(2026, 11, 2), 60, max_results=10, max_per_day=10)
    assert slots
    for s in slots:
        # London 09:00 GMT = 12:00 Riyadh, KSA day ends 17:00
        assert s.start.astimezone(RIYADH).time() >= time(12, 0)
        assert s.end.astimezone(RIYADH).time() <= time(17, 0)


def test_busy_blocks_and_prayer_buffers_are_avoided():
    people = load_attendees(SAMPLE / "attendees.csv", SAMPLE / "busy.csv",
                            {"Claire Bennett": SAMPLE / "claire_bennett.ics"})
    slots = find_slots(people, date(2026, 11, 1), date(2026, 11, 5), 60, prayer_city="jeddah",
                       prayer_buffer_min=20, max_results=5)
    assert slots
    for s in slots:
        for p in people:
            assert all(not (s.start < b1 and b0 < s.end) for b0, b1, _ in p.busy)
        pt = prayer_times(s.start.date(), *CITIES["jeddah"])
        for name in ("Dhuhr", "Asr", "Maghrib"):
            t = pt.times[name]
            assert not (s.start <= t < s.end), f"{name} inside slot"


def test_no_slot_when_calendars_never_overlap():
    people = [person("ksa", "Asia/Riyadh", "08:00", "12:00", "Sun-Thu"),
              person("ny", "America/New_York", "09:00", "17:00", "Mon-Fri")]
    assert find_slots(people, date(2026, 11, 1), date(2026, 11, 5), 60) == []


def test_prayer_times_are_plausible_for_jeddah():
    pt = prayer_times(date(2026, 11, 2), *CITIES["jeddah"]).times
    assert time(11, 55) <= pt["Dhuhr"].time() <= time(12, 20)
    assert time(15, 5) <= pt["Asr"].time() <= time(15, 35)
    assert time(17, 35) <= pt["Maghrib"].time() <= time(18, 0)
    assert pt["Fajr"] < pt["Sunrise"] < pt["Dhuhr"] < pt["Asr"] < pt["Maghrib"] < pt["Isha"]


def test_ics_reader_handles_tzid_and_utc(tmp_path):
    events = read_ics_busy(SAMPLE / "claire_bennett.ics", default_tz="Europe/London")
    assert len(events) == 3
    first = events[0][0]
    assert first == datetime(2026, 11, 2, 9, 0, tzinfo=ZoneInfo("Europe/London"))
    assert events[1][0].utcoffset().total_seconds() == 0


def test_unknown_attendee_in_busy_file_is_an_error(tmp_path):
    bad = tmp_path / "busy.csv"
    bad.write_text("attendee,start,end,title\nNobody,2026-11-02T09:00:00+03:00,2026-11-02T10:00:00+03:00,x\n")
    with pytest.raises(ValueError, match="unknown attendee"):
        load_attendees(SAMPLE / "attendees.csv", bad)
