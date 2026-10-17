"""Approximate daily prayer times (Umm al-Qura convention) for meeting buffers.

Uses the standard solar-position formulas (as in the open PrayTimes method):
Fajr at 18.5 degrees, Asr with shadow factor 1 (Shafi'i/standard), Maghrib at
sunset and Isha 90 minutes after Maghrib (Umm al-Qura). Results are typically
within 1-2 minutes of published timetables, which is ample for *scheduling
buffers*. For the actual call to prayer, follow the official local timetable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

# City presets (latitude, longitude, IANA zone).
CITIES = {
    "jeddah": (21.5433, 39.1728, "Asia/Riyadh"),
    "riyadh": (24.7136, 46.6753, "Asia/Riyadh"),
    "dammam": (26.4207, 50.0888, "Asia/Riyadh"),
    "makkah": (21.3891, 39.8579, "Asia/Riyadh"),
    "dubai": (25.2048, 55.2708, "Asia/Dubai"),
    "doha": (25.2854, 51.5310, "Asia/Qatar"),
}

PRAYERS_IN_WORKDAY = ("Dhuhr", "Asr", "Maghrib")


def _sin(d): return math.sin(math.radians(d))
def _cos(d): return math.cos(math.radians(d))
def _tan(d): return math.tan(math.radians(d))
def _asin(x): return math.degrees(math.asin(x))
def _acos(x): return math.degrees(math.acos(max(-1.0, min(1.0, x))))
def _atan2(y, x): return math.degrees(math.atan2(y, x))
def _acot(x): return math.degrees(math.atan(1.0 / x))


def _sun_position(jd: float) -> tuple[float, float]:
    """Return (declination degrees, equation of time hours) for a Julian date."""
    d = jd - 2451545.0
    g = (357.529 + 0.98560028 * d) % 360
    q = (280.459 + 0.98564736 * d) % 360
    lam = (q + 1.915 * _sin(g) + 0.020 * _sin(2 * g)) % 360
    e = 23.439 - 0.00000036 * d
    ra = (_atan2(_cos(e) * _sin(lam), _cos(lam)) / 15.0) % 24
    decl = _asin(_sin(e) * _sin(lam))
    eqt = q / 15.0 - ra
    eqt = (eqt + 12) % 24 - 12
    return decl, eqt


def _julian(d: date) -> float:
    y, m = d.year, d.month
    if m <= 2:
        y, m = y - 1, m + 12
    a = y // 100
    b = 2 - a + a // 4
    return math.floor(365.25 * (y + 4716)) + math.floor(30.6001 * (m + 1)) + d.day + b - 1524.5


@dataclass(frozen=True)
class PrayerTimes:
    day: date
    times: dict[str, datetime]  # tz-aware, in the city's zone


def prayer_times(day: date, lat: float, lon: float, tz: str) -> PrayerTimes:
    zone = ZoneInfo(tz)
    offset = datetime.combine(day, time(12), zone).utcoffset().total_seconds() / 3600
    decl, eqt = _sun_position(_julian(day) - lon / 360.0 + 0.5)
    dhuhr = 12 + offset - lon / 15.0 - eqt

    def hour_angle(angle: float) -> float:
        return _acos((-_sin(angle) - _sin(decl) * _sin(lat)) / (_cos(decl) * _cos(lat))) / 15.0

    asr_angle = -_acot(1 + _tan(abs(lat - decl)))  # shadow factor 1
    hours = {
        "Fajr": dhuhr - hour_angle(18.5),
        "Sunrise": dhuhr - hour_angle(0.833),
        "Dhuhr": dhuhr + 2 / 60,  # small safety margin after zenith
        "Asr": dhuhr + hour_angle(asr_angle),
        "Maghrib": dhuhr + hour_angle(0.833),
    }
    hours["Isha"] = hours["Maghrib"] + 1.5
    midnight = datetime.combine(day, time(0), zone)
    times = {k: (midnight + timedelta(minutes=round(v * 60))) for k, v in hours.items()}
    return PrayerTimes(day, times)


def prayer_blocks(day: date, city: str, buffer_minutes: int, lead_minutes: int = 5,
                  prayers=PRAYERS_IN_WORKDAY) -> list[tuple[datetime, datetime, str]]:
    """Busy blocks around each workday prayer: [time - lead, time + buffer]."""
    lat, lon, tz = CITIES[city.lower()]
    pt = prayer_times(day, lat, lon, tz)
    return [
        (pt.times[p] - timedelta(minutes=lead_minutes), pt.times[p] + timedelta(minutes=buffer_minutes),
         f"{p} prayer buffer ({city.title()})")
        for p in prayers
    ]
