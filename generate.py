#!/usr/bin/env python3
"""
Tamil Panchangam ICS generator.

Outputs:
- Calendar-Stuttgart.ics  (Europe/Berlin)
- Calendar-India.ics      (Asia/Kolkata, Hyderabad coordinates)

Per calendar:
1) All-day event per date with Daily Panchangam (DESCRIPTION contains ASCII table).
2) Timed event for Shukla Ekadasi only (Tithi 11).

Tamil New Year date assignment:
- Mesha Sankranti = Sun sidereal longitude crosses 0° (Mesha)
- Sunset Rule:
  - If ingress occurs before local sunset (including before sunrise), New Year civil date = same local date.
  - If ingress occurs after local sunset, New Year civil date = next local date.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, date, time, timedelta
from bisect import bisect_left, bisect_right
from typing import Dict, List, Tuple, Optional

import numpy as np
import pytz
from ics import Calendar, Event
from skyfield.api import load, wgs84
from skyfield import almanac
from skyfield.searchlib import find_discrete

UTC = pytz.UTC

MANUAL_FILE = "manual_events.json"
DAYS_AHEAD = int(os.environ.get("DAYS_AHEAD", "366"))
DISCRETE_STEP_DAYS = float(os.environ.get("DISCRETE_STEP_DAYS", "0.04"))

# Only Shukla Ekadasi (Tithi 11)
SPECIAL_TITHIS: Dict[int, str] = {
    11: "Shukla Ekadasi",
    6: "Shukla Shashti",
    19: "Sankatahara Chathurthi",
    }

# --- Naming tables (Harmonized to Title Case) ---

TITHI_NAMES_SHUKLA = (
    "Prathamai", "Dwitiyai", "Tritiyai", "Chathurthi", "Panchami", "Shashti", "Saptami", "Ashtami", "Navami", "Dashami",
    "Ekadashi", "Dwadashi", "Trayodashi", "Chadhurdasi", "Pournami"
)
TITHI_NAMES_KRISHNA = (
    "Prathamai", "Dwitiyai", "Tritiyai", "Chathurthi", "Panchami", "Shashti", "Saptami", "Ashtami", "Navami", "Dashami",
    "Ekadashi", "Dwadashi", "Trayodashi", "Chadhurdasi", "Amavasai"
)

NAKSHATRA_NAMES = (
    "Ashwini", "Bharani", "Karthigai", "Rohini", "Mrigashirsham", "Thiruvathirai", "Punarpoosam", "Poosam", "Aayilyam",
    "Magam", "Pooram", "Uthiram", "Hastham", "Chitthirai", "Swathi", "Visakam", "Anusham", "Kettai", "Moolam", "Pooradam",
    "Uthiradam", "Thiruvonam", "Avittam", "Sathayam", "Poorattathi", "Uthirattathi", "Revathi"
)

YOGA_NAMES = (
    "Vishkambha", "Priti", "Aayushman", "Saubhagya", "Shobhana", "Atiganda", "Sukarman", "Dhriti", "Shoola", "Ganda",
    "Vriddhi", "Dhruva", "Vyaghata", "Harshana", "Vajra", "Siddhi", "Vyatipata", "Variyana", "Parigha", "Shiva", "Siddha",
    "Sadhya", "Shubha", "Shukla", "Brahma", "Indra", "Vaidhriti"
)

RASI_NAMES = ("Mesham", "Rishabam", "Mithunam", "Katakam", "Simham", "Kanni", "Thulam", "Virutchigam", "Dhanus", "Makaram", "Kumbham", "Meenam")
TAMIL_SOLAR_MONTH_NAMES = ("Chithirai", "Vaikasi", "Aani", "Aadi", "Aavani", "Purattasi", "Aippasi", "Karthigai", "Margazhi", "Thai", "Maasi", "Panguni")

RITU_BY_SOLAR_MONTH = {
    "Chithirai": "Vasantha Ruthu", "Vaikasi": "Vasantha Ruthu",
    "Aani": "Grishma Ruthu", "Aadi": "Grishma Ruthu",
    "Aavani": "Varsha Ruthu", "Purattasi": "Varsha Ruthu",
    "Aippasi": "Sarath Ruthu", "Karthigai": "Sarath Ruthu",
    "Margazhi": "Hemantha Ruthu", "Thai": "Hemantha Ruthu",
    "Maasi": "Shishira Ruthu", "Panguni": "Shishira Ruthu",
}
WEEKDAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")

# 60-year cycle, base: 1987–1988 = PRABHAVA (conventional mapping used in many tables)
SAMVATSARA_NAMES = [
    "Prabhava", "Vibhava", "Shukla", "Pramodadhoota", "Prajapati", "Angirasa", "Srimukha", "Bhava", "Yuva", "Dhatu",
    "Eeswara", "Vehudhanya", "Pramathi", "Vikrama", "Vishu", "Chitrabhanu", "Subhanu", "Dharana", "Parthiba", "Viya",
    "Sarvajit", "Sarvadhari", "Virodhi", "Vikruthi", "Kara", "Nandhana", "Vijaya", "Jaya", "Manmatha", "Dhunmuki",
    "Hevilambi", "Vilambi", "Vikari", "Sarvari", "Plava", "Subhakrit", "Shobakrit", "Krodhi", "Vishvavasu", "Parabhava",
    "Plavanga", "Keelaka", "Soumya", "Sadharana", "Virodhakrit", "Paridhabi", "Pramadhicha", "Anandha", "Rakshasa", "Nala",
    "Pingala", "Kalayukti", "Siddharthi", "Raudhri", "Dhunmathi", "Dhundubhi", "Rudhirothgari", "Rakshasi", "Krodhana", "Akshaya",
]
BASE_SAMVATSARA_YEAR = 1987  # year in which PRABHAVA starts at Puthandu

# Lahiri ayanamsa approximation (configurable).
# If you want a star-anchored Lahiri, you need an external star catalog.
LAHIRI_AYANAMSA_DEG_AT_J2000 = float(os.environ.get("LAHIRI_AYANAMSA_DEG_AT_J2000", "23.85675"))
LAHIRI_AYANAMSA_RATE_DEG_PER_YEAR = float(os.environ.get("LAHIRI_AYANAMSA_RATE_DEG_PER_YEAR", str(50.290966 / 3600.0)))
J2000_TT = 2451545.0  # TT Julian day

@dataclass(frozen=True)
class LocationConfig:
    key: str
    display_name: str
    lat: float
    lon: float
    tz: str
    out_ics: str

LOCATIONS = (
    LocationConfig("stuttgart", "Stuttgart, Germany", 48.7758, 9.1829, "Europe/Berlin", "Calendar-Stuttgart.ics"),
    LocationConfig("india", "Hyderabad, India", 17.38504, 78.48667, "Asia/Kolkata", "Calendar-India.ics"),
)

# ------------------------ small formatting helpers ------------------------

def fmt_date(d: date) -> str:
    return d.strftime("%d.%m.%Y")

def fmt_time(dt: datetime) -> str:
    h, m = dt.hour, dt.minute
    if h == 12 and m == 0:
        return "12 Noon"
    if h == 0:
        return f"12.{m:02d} AM"
    if 1 <= h <= 11:
        return f"{h}.{m:02d} AM"
    if h == 12:
        return f"12.{m:02d} PM"
    return f"{h-12}.{m:02d} PM"

def fmt_interval(a: datetime, b: datetime) -> str:
    return f"{fmt_time(a)} to {fmt_time(b)}"


def weekday_name(d: date) -> str:
    return WEEKDAY_NAMES[d.weekday()]

def wrap_text(s: str, width: int) -> List[str]:
    words = s.split()
    if not words:
        return [""]
    lines: List[str] = []
    cur = words[0]
    for w in words[1:]:
        if len(cur) + 1 + len(w) <= width:
            cur += " " + w
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines

def ascii_table(rows, *args, **kwargs):
    """
    Backwards-compatible replacement: outputs plain text lines instead of an ASCII table.
    Keeps existing callers unchanged.
    """
    lines = []
    header_seen = False

    for k, v in rows:
        k = str(k).strip()
        v = "" if v is None else str(v).strip()

        if k.lower() == "header":
            if v:
                lines.append(v)
                lines.append("")
            header_seen = True
            continue

        if k:
            lines.append(f"{k}: {v}")
        elif v:
            lines.append(v)

    if not header_seen and lines:
        pass

    return "\n".join(lines).strip()

# ------------------------ astronomy helpers ------------------------

def normalize_deg(x):
    return np.mod(x, 360.0)

def ayanamsa_deg(t):
    years = np.asarray((t.tt - J2000_TT) / 365.2425)
    return LAHIRI_AYANAMSA_DEG_AT_J2000 + LAHIRI_AYANAMSA_RATE_DEG_PER_YEAR * years

def sidereal_lon(lon_deg, t):
    return normalize_deg(np.asarray(lon_deg) - ayanamsa_deg(t))

def sf_to_utc_dt(t) -> datetime:
    dt = t.utc_datetime()
    if dt.tzinfo is None:
        return UTC.localize(dt)
    return dt.astimezone(UTC)

def precompute_discrete(ts, t0_utc: datetime, t1_utc: datetime, f) -> Tuple[List[datetime], List[int]]:
    times, values = find_discrete(ts.from_datetime(t0_utc), ts.from_datetime(t1_utc), f)
    return [sf_to_utc_dt(t) for t in times], [int(v) for v in values]

def value_at(t_utc: datetime, changes: List[datetime], values: List[int]) -> int:
    i = bisect_right(changes, t_utc) - 1
    return values[0] if i < 0 else values[i]

def transitions_between(a_utc: datetime, b_utc: datetime, changes: List[datetime], values: List[int]) -> List[Tuple[datetime, int]]:
    i = bisect_right(changes, a_utc)
    j = bisect_left(changes, b_utc)
    return [(changes[k], values[k]) for k in range(i, j)]

def tithi_idx(t, earth, sun, moon):
    e = earth.at(t)
    _, slon, _ = e.observe(sun).apparent().ecliptic_latlon()
    _, mlon, _ = e.observe(moon).apparent().ecliptic_latlon()
    phase = normalize_deg(np.asarray(mlon.degrees) - np.asarray(slon.degrees))
    return (phase // 12.0).astype(int) + 1  # 1..30

def nak_idx(t, earth, moon):
    e = earth.at(t)
    _, mlon, _ = e.observe(moon).apparent().ecliptic_latlon()
    mlon_sid = sidereal_lon(mlon.degrees, t)
    return (mlon_sid // (360.0/27.0)).astype(int) + 1  # 1..27

def yoga_idx(t, earth, sun, moon):
    e = earth.at(t)
    _, slon, _ = e.observe(sun).apparent().ecliptic_latlon()
    _, mlon, _ = e.observe(moon).apparent().ecliptic_latlon()
    total = normalize_deg(sidereal_lon(slon.degrees, t) + sidereal_lon(mlon.degrees, t))
    return (total // (360.0/27.0)).astype(int) + 1  # 1..27

def solar_rasi_idx(t, earth, sun):
    e = earth.at(t)
    _, slon, _ = e.observe(sun).apparent().ecliptic_latlon()
    return (sidereal_lon(slon.degrees, t) // 30.0).astype(int)  # 0..11

def moon_rasi_idx(t, earth, moon):
    e = earth.at(t)
    _, mlon, _ = e.observe(moon).apparent().ecliptic_latlon()
    return (sidereal_lon(mlon.degrees, t) // 30.0).astype(int)  # 0..11

def karana_num(t, earth, sun, moon):
    e = earth.at(t)
    _, slon, _ = e.observe(sun).apparent().ecliptic_latlon()
    _, mlon, _ = e.observe(moon).apparent().ecliptic_latlon()
    phase = normalize_deg(np.asarray(mlon.degrees) - np.asarray(slon.degrees))
    return (phase // 6.0).astype(int) + 1  # 1..60

def karana_name(n: int) -> str:
    if n == 1:  return "Kimstughna"
    if n == 58: return "Shakuni"
    if n == 59: return "Chatushpada"
    if n == 60: return "Nagava"
    rep = ("Bavai", "Balavai", "Kaulavai", "Thaitilai", "Garajai", "Vanijai", "Vishti")
    return rep[(n - 2) % 7]

def tithi_name(i: int) -> str:
    if 1 <= i <= 15:  return TITHI_NAMES_SHUKLA[i-1]
    if 16 <= i <= 30: return TITHI_NAMES_KRISHNA[i-16]
    return "Unknown"

def nak_name(i: int) -> str:
    return NAKSHATRA_NAMES[i-1] if 1 <= i <= 27 else "Unknown"

def yoga_name(i: int) -> str:
    return YOGA_NAMES[i-1] if 1 <= i <= 27 else "Unknown"

def paksha(i: int) -> str:
    return "Shukla Paksham" if i <= 15 else "Krushna Paksham"

def ayanam_name(t, earth, sun) -> str:
    # Based on tropical ecliptic longitude (seasonal half-year).
    e = earth.at(t)
    _, slon, _ = e.observe(sun).apparent().ecliptic_latlon()
    lon = float(normalize_deg(slon.degrees))
    return "Dhatchinayanam" if (90.0 <= lon < 270.0) else "Utharayanam"

def describe_trans(start_name: str, trans: List[Tuple[datetime, str]], connector: str) -> str:
    if not trans:
        return start_name
    if len(trans) == 1:
        t1, v2 = trans[0]
        return f"upto {fmt_time(t1)} {start_name}, {connector} {v2}"
    t1, v2 = trans[0]
    t2, v3 = trans[1]
    return f"upto {fmt_time(t1)} {start_name}, upto {fmt_time(t2)} {v2}, {connector} {v3}"


def rahu_yama_gulika(d: date, sunrise: datetime, sunset: datetime) -> Tuple[str, str, str]:
    L = (sunset - sunrise).total_seconds()
    if L <= 0:
        return "N/A", "N/A", "N/A"
    part = L / 8.0
    # Monday=0..Sunday=6
    rahu = {0:1,1:6,2:4,3:5,4:3,5:2,6:7}[d.weekday()]
    yama = {0:3,1:2,2:1,3:0,4:6,5:5,6:4}[d.weekday()]
    guli = {0:4,1:3,2:2,3:1,4:0,5:6,6:5}[d.weekday()]
    def seg(i: int) -> Tuple[datetime, datetime]:
        return (sunrise + timedelta(seconds=part*i), sunrise + timedelta(seconds=part*(i+1)))
    r1, r2 = seg(rahu)
    y1, y2 = seg(yama)
    g1, g2 = seg(guli)
    return fmt_interval(r1, r2), fmt_interval(y1, y2), fmt_interval(g1, g2)



# ------------------------ traditional lookups and derived quantities ------------------------

VASARAM_NAMES = {
    0: "Soma Vasaram",    # Monday
    1: "Bhauma Vasaram",  # Tuesday
    2: "Budha Vasaram",   # Wednesday
    3: "Guru Vasaram",    # Thursday
    4: "Sukra Vasaram",   # Friday
    5: "Sani Vasaram",    # Saturday
    6: "Ravi Vasaram",    # Sunday
}

# Amirtha / Siddha / Marana Yogam lookup by (weekday, nakshatra)
# Nakshatra indices are 1..27 following NAKSHATRA_NAMES.
MARANA_YOGAM = {
    6: {2, 3, 10, 16},          # Sunday: Bharani, Krittika, Magha, Vishakha
    0: {14, 23, 20},            # Monday: Chitra, Dhanishta, Purvashadha
    1: {21, 24, 26},            # Tuesday: Uttarashadha, Satabhisha, Uttarabhadra
    2: {1, 9, 19, 23},          # Wednesday: Ashwini, Ashlesha, Mula, Dhanishta
    3: {5, 10, 16},             # Thursday: Mrigasira, Magha, Vishakha
    4: {4, 18, 20},             # Friday: Rohini, Jyeshtha, Purvashadha
    5: {27, 11, 12, 13},        # Saturday: Revati, Purvaphalguni, Uttaraphalguni, Hasta
}

AMIRTHA_YOGAM = {
    6: {13, 19},                # Sunday: Hasta, Mula
    0: {5},                     # Monday: Mrigasira
    1: {1},                     # Tuesday: Ashwini
    2: {17},                    # Wednesday: Anuradha
    3: {8},                     # Thursday: Pushya
    4: {27},                    # Friday: Revati
    5: {4},                     # Saturday: Rohini
}

def amirtha_siddha_marana(weekday_idx: int, nak_idx_now: int) -> str:
    if nak_idx_now in MARANA_YOGAM.get(weekday_idx, set()):
        return "Marana Yogam"
    if nak_idx_now in AMIRTHA_YOGAM.get(weekday_idx, set()):
        return "Amirtha Yogam"
    return "Siddha Yogam"

# Gowri Nalla Neram sequences (8 equal slots from sunrise to sunset)
GOWRI_SEQ = {
    6: ["Uthi", "Amirtha", "Rogam", "Laabam", "Dhanam", "Sugam", "Soram", "Visham"],
    0: ["Amirtha", "Rogam", "Laabam", "Dhanam", "Sugam", "Soram", "Visham", "Uthi"],
    1: ["Rogam", "Laabam", "Dhanam", "Sugam", "Soram", "Visham", "Uthi", "Amirtha"],
    2: ["Laabam", "Dhanam", "Sugam", "Soram", "Visham", "Uthi", "Amirtha", "Rogam"],
    3: ["Dhanam", "Sugam", "Soram", "Visham", "Uthi", "Amirtha", "Rogam", "Laabam"],
    4: ["Sugam", "Soram", "Visham", "Uthi", "Amirtha", "Rogam", "Laabam", "Dhanam"],
    5: ["Soram", "Visham", "Uthi", "Amirtha", "Rogam", "Laabam", "Dhanam", "Sugam"],
}

GOOD_GOWRI = {"Uthi", "Amirtha", "Laabam", "Dhanam", "Sugam"}

def gowri_good_time(d: date, sunrise: datetime, sunset: datetime) -> str:
    # Returns one or two preferred good-time windows.
    L = (sunset - sunrise).total_seconds()
    if L <= 0:
        return "N/A"
    slot = L / 8.0
    seq = GOWRI_SEQ.get(d.weekday())
    if not seq:
        return "N/A"

    noon = sunrise.replace(hour=12, minute=0, second=0, microsecond=0)

    good_slots = []
    for i, q in enumerate(seq):
        if q not in GOOD_GOWRI:
            continue
        a = sunrise + timedelta(seconds=slot*i)
        b = sunrise + timedelta(seconds=slot*(i+1))
        good_slots.append((a, b))

    if not good_slots:
        return "N/A"

    morning = next((ab for ab in good_slots if ab[0] < noon), None)
    evening = next((ab for ab in good_slots if ab[0] >= noon), None)

    if morning and evening and morning != evening:
        return f"{fmt_interval(*morning)} and {fmt_interval(*evening)}"
    if morning:
        return fmt_interval(*morning)
    return fmt_interval(*good_slots[0])

# Soolam direction and Pariharam (remedy) by weekday
SOOLAM_PARIHARAM = {
    6: ("West",  "Jaggery / Vellam"),
    0: ("East",  "Curd / Thayir"),
    1: ("North", "Milk / Paal"),
    2: ("North", "Milk / Paal"),
    3: ("South", "Oil / Thailam"),
    4: ("West",  "Jaggery / Vellam"),
    5: ("East",  "Curd / Thayir"),
}

def soolam_and_prayatchittham(d: date) -> tuple[str, str]:
    return SOOLAM_PARIHARAM.get(d.weekday(), ("N/A", "N/A"))


def sradhdha_tithi_aparahna(
    sunrise: datetime,
    sunset: datetime,
    tithi_changes: List[datetime],
    tithi_vals: List[int],
) -> str:
    # Aparahna Kala = 4th part of 5 equal daytime parts.
    L = (sunset - sunrise).total_seconds()
    if L <= 0:
        return "N/A"
    part = L / 5.0
    a_start = sunrise + timedelta(seconds=3 * part)
    a_end = sunrise + timedelta(seconds=4 * part)

    a0 = a_start.astimezone(UTC)
    a1 = a_end.astimezone(UTC)

    # Gather boundaries inside the window
    cur = value_at(a0, tithi_changes, tithi_vals)
    trans = transitions_between(a0, a1, tithi_changes, tithi_vals)

    # Build segments and pick tithi with maximum coverage
    segments = []
    prev = a0
    for t, v in trans:
        segments.append((prev, t, cur))
        prev = t
        cur = v
    segments.append((prev, a1, cur))

    best_v = None
    best_len = -1.0
    for x0, x1, v in segments:
        ln = (x1 - x0).total_seconds()
        if ln > best_len:
            best_len = ln
            best_v = v

    return tithi_name(int(best_v)) if best_v is not None else "N/A"


def chandhirashtamam_target(moon_rasi_idx_now: int) -> str:
    # Target rasi for which today is Chandrashtama.
    target = (moon_rasi_idx_now - 7) % 12
    return RASI_NAMES[target]

# ------------------------ sunrise/sunset utilities ------------------------

def sun_events_range(ts, planets, loc: LocationConfig, start_d: date, end_d: date) -> Tuple[Dict[date, datetime], Dict[date, datetime]]:
    tz = pytz.timezone(loc.tz)
    location = wgs84.latlon(loc.lat, loc.lon)
    t0 = tz.localize(datetime.combine(start_d - timedelta(days=2), time(0, 0))).astimezone(UTC)
    t1 = tz.localize(datetime.combine(end_d + timedelta(days=2), time(0, 0))).astimezone(UTC)
    f = almanac.sunrise_sunset(planets, location)
    times, states = almanac.find_discrete(ts.from_datetime(t0), ts.from_datetime(t1), f)

    sunr: Dict[date, datetime] = {}
    suns: Dict[date, datetime] = {}
    for t, st in zip(times, states):
        dt_loc = sf_to_utc_dt(t).astimezone(tz)
        if int(st) == 1:
            sunr[dt_loc.date()] = dt_loc
        else:
            suns[dt_loc.date()] = dt_loc
    return sunr, suns

def sunrise_sunset_for_local_date(ts, planets, loc: LocationConfig, d: date) -> Tuple[datetime, datetime]:
    """
    Returns (sunrise_local, sunset_local) for the given local civil date d.
    Uses a buffered UTC window to survive DST changes.
    """
    tz = pytz.timezone(loc.tz)
    location = wgs84.latlon(loc.lat, loc.lon)

    start_local = tz.localize(datetime.combine(d, time(0, 0)))
    t0 = (start_local - timedelta(hours=6)).astimezone(UTC)
    t1 = (start_local + timedelta(days=1, hours=6)).astimezone(UTC)

    f = almanac.sunrise_sunset(planets, location)
    times, states = almanac.find_discrete(ts.from_datetime(t0), ts.from_datetime(t1), f)

    sunrise = None
    sunset = None
    for t, st in zip(times, states):
        dt_loc = sf_to_utc_dt(t).astimezone(tz)
        if dt_loc.date() != d:
            continue
        if int(st) == 1:
            sunrise = dt_loc
        else:
            sunset = dt_loc

    if sunrise is None or sunset is None:
        raise RuntimeError(f"Could not find sunrise/sunset for {loc.display_name} on {d.isoformat()}")
    return sunrise, sunset

# ------------------------ Tamil New Year (Sunset Rule) ------------------------

def wrap180(x: float) -> float:
    return ((x + 180.0) % 360.0) - 180.0

def sun_sidereal_lon_deg(sf_t, earth, sun) -> float:
    e = earth.at(sf_t)
    _, slon, _ = e.observe(sun).apparent().ecliptic_latlon()
    return float(sidereal_lon(slon.degrees, sf_t))

def mesha_sankranti_utc(year: int, ts, earth, sun) -> datetime:
    """
    Find the UTC instant when Sun sidereal longitude crosses 0° (Mesha Sankranti).
    Bracket in Apr 10–18 and bisection refine.
    """
    t0 = UTC.localize(datetime(year, 4, 10, 0, 0))
    t1 = UTC.localize(datetime(year, 4, 18, 0, 0))

    step = timedelta(hours=2)
    prev_dt = t0
    prev_sf = ts.from_datetime(prev_dt)
    prev_f = wrap180(sun_sidereal_lon_deg(prev_sf, earth, sun))

    bracket = None
    cur = t0 + step
    while cur <= t1:
        cur_sf = ts.from_datetime(cur)
        cur_f = wrap180(sun_sidereal_lon_deg(cur_sf, earth, sun))
        if prev_f == 0.0:
            return prev_dt
        if (prev_f < 0.0 and cur_f > 0.0) or (prev_f > 0.0 and cur_f < 0.0):
            bracket = (prev_dt, cur)
            break
        prev_dt, prev_f = cur, cur_f
        cur += step

    if bracket is None:
        raise RuntimeError(f"Could not bracket Mesha Sankranti for {year} in Apr 10–18 window")

    lo, hi = bracket
    for _ in range(50):  # enough for sub-second
        mid = lo + (hi - lo) / 2
        f_lo = wrap180(sun_sidereal_lon_deg(ts.from_datetime(lo), earth, sun))
        f_mid = wrap180(sun_sidereal_lon_deg(ts.from_datetime(mid), earth, sun))
        if f_mid == 0.0:
            return mid
        if (f_lo < 0.0 and f_mid > 0.0) or (f_lo > 0.0 and f_mid < 0.0):
            hi = mid
        else:
            lo = mid
    return lo

def puthandu_civil_date(year: int, ts, planets, earth, sun, loc: LocationConfig) -> date:
    """
    Compute Puthandu civil date for a Gregorian year using Sunset Rule.
    """
    tz = pytz.timezone(loc.tz)

    ingress_utc = mesha_sankranti_utc(year, ts, earth, sun)
    ingress_local = ingress_utc.astimezone(tz)
    ingress_day = ingress_local.date()

    sunrise, sunset = sunrise_sunset_for_local_date(ts, planets, loc, ingress_day)

    # Sunset Rule:
    # - ingress before sunrise: same day
    # - ingress between sunrise and sunset: same day
    # - ingress after sunset: next day
    if ingress_local > sunset:
        return ingress_day + timedelta(days=1)
    return ingress_day

def samvatsara_for_date(d: date, puthandu_by_year: Dict[int, date]) -> str:
    """
    Determine the Samvatsara name for civil date d based on puthandu dates.
    """
    y = d.year
    p_y = puthandu_by_year.get(y)
    if p_y is None:
        raise RuntimeError(f"Missing puthandu date for year {y}")
    sank_year = y if d >= p_y else (y - 1)
    return SAMVATSARA_NAMES[(sank_year - BASE_SAMVATSARA_YEAR) % 60]

# ------------------------ solar month/day numbering ------------------------

def month_day_numbers(earth, sun, ts, sunr: Dict[date, datetime], start_d: date, end_d: date) -> Dict[date, Tuple[str, int, str]]:
    back = start_d - timedelta(days=40)
    idx_by_day: Dict[date, int] = {}
    d = back
    while d <= end_d:
        if d in sunr:
            mi = int(solar_rasi_idx(ts.from_datetime(sunr[d].astimezone(UTC)), earth, sun))
            idx_by_day[d] = mi
        d += timedelta(days=1)

    res: Dict[date, Tuple[str, int, str]] = {}
    cur: Optional[int] = None
    cnt = 0
    for d in sorted(idx_by_day):
        mi = idx_by_day[d]
        if cur is None or mi != cur:
            cur = mi
            cnt = 1
        else:
            cnt += 1
        res[d] = (TAMIL_SOLAR_MONTH_NAMES[mi], cnt, RASI_NAMES[mi])

    return {d: res[d] for d in res if start_d <= d <= end_d}

# ------------------------ Daily Panchangam rendering ------------------------

def daily_panchangam_description(
    loc: LocationConfig,
    d: date,
    month_name: str,
    day_in_month: int,
    rasi_name: str,
    sunrise: datetime,
    sunset: datetime,
    next_sunrise: datetime,
    tithi_changes: List[datetime], tithi_vals: List[int],
    nak_changes: List[datetime], nak_vals: List[int],
    puthandu_by_year: Dict[int, date],
    earth, sun, moon, ts,
) -> str:
    tz = pytz.timezone(loc.tz)

    sr_utc = sunrise.astimezone(UTC)
    nsr_utc = next_sunrise.astimezone(UTC)
    t_sr = ts.from_datetime(sr_utc)

    # Tithi over sunrise->next sunrise
    t_now = value_at(sr_utc, tithi_changes, tithi_vals)
    t_trans = [(t.astimezone(tz), tithi_name(v)) for (t, v) in transitions_between(sr_utc, nsr_utc, tithi_changes, tithi_vals)]
    tithi_str = describe_trans(tithi_name(t_now), t_trans, connector="thereafter")

    # Nakshatra over sunrise->next sunrise
    n_now = value_at(sr_utc, nak_changes, nak_vals)
    n_trans = [(t.astimezone(tz), nak_name(v)) for (t, v) in transitions_between(sr_utc, nsr_utc, nak_changes, nak_vals)]
    nak_str = describe_trans(nak_name(n_now), n_trans, connector="and then")

    yog = int(yoga_idx(t_sr, earth, sun, moon))
    kar = int(karana_num(t_sr, earth, sun, moon))
    mr = int(moon_rasi_idx(t_sr, earth, moon))
    rahu, yama, guli = rahu_yama_gulika(d, sunrise, sunset)


    year_name = samvatsara_for_date(d, puthandu_by_year)
    ritu = RITU_BY_SOLAR_MONTH.get(month_name, "N/A")

    weekday = d.weekday()
    vasaram = VASARAM_NAMES.get(weekday, "Vasaram")

    yoga_quality = amirtha_siddha_marana(weekday, int(n_now))
    amirtha_disp = yoga_quality
    subayogam = "Subayogam" if yoga_quality != "Marana Yogam" else ""

    good_time = gowri_good_time(d, sunrise, sunset)
    soolam, prayatchittham = soolam_and_prayatchittham(d)
    sradhdha = sradhdha_tithi_aparahna(sunrise, sunset, tithi_changes, tithi_vals)

    chandhirashtamam = chandhirashtamam_target(mr)

    header = f"{month_name} - {day_in_month:02d} ({fmt_date(d)}) {weekday_name(d)}"

    rows = [
        ("Header", header),
        ("Year", f"{year_name} Varudam ({year_name} Nama Samvathsaram)"),
        ("Ayanam", ayanam_name(t_sr, earth, sun)),
        ("Ruthu", ritu),
        ("Month", f"{month_name} Masam ({rasi_name} Masam)"),
        ("Paksham", paksha(t_now)),
        ("Thithi", tithi_str),
        ("Day", f"{{{vasaram}}} {weekday_name(d)}"),
        ("Nakshatthiram", nak_str),
        ("Yogam", yoga_name(yog)),
        ("Karanam", karana_name(kar)),
        ("Amirthathiyogam", amirtha_disp),
        ("Subayogam", subayogam),
        ("Raghu Kalam", rahu),
        ("Yemakandam", yama),
        ("Kuligai", guli),
        ("Good time", good_time),
        ("Sun Rise", fmt_time(sunrise)),
        ("Sun Set", fmt_time(sunset)),
        ("Chandhirashtamam", chandhirashtamam),
        ("Soolam", soolam),
        ("Prayatchittham", prayatchittham),
        ("Sradhdhathithi", sradhdha),
        ("Location", loc.display_name),
    ]

    return ascii_table(rows)


# ------------------------ Manual events ------------------------

def add_manual_events(cal: Calendar, tz, uid_prefix: str) -> None:
    if not os.path.exists(MANUAL_FILE):
        return

    try:
        with open(MANUAL_FILE, "r", encoding="utf-8") as f:
            raw = f.read().strip()
        if not raw:
            return
        data = json.loads(raw)
        if not isinstance(data, list):
            raise ValueError("manual_events.json must be a JSON list")

        for item in data:
            e = Event()
            e.name = f"🔹 {item['name']}"
            e.description = item.get("description", "")

            if "date" in item:
                e.begin = item["date"]
                e.make_all_day()
                e.uid = f"{uid_prefix}-{item['date']}-{item['name'].replace(' ','')}@manual"
            elif "start" in item and "end" in item:
                tz_item = pytz.timezone(item.get("timezone", tz.zone))
                s = tz_item.localize(datetime.strptime(item["start"], "%Y-%m-%d %H:%M"))
                en = tz_item.localize(datetime.strptime(item["end"], "%Y-%m-%d %H:%M"))
                e.begin = s.astimezone(tz)
                e.end = en.astimezone(tz)
                e.uid = f"{uid_prefix}-{item['start']}-{item['name'].replace(' ','')}@manual"
            else:
                continue

            cal.events.add(e)

    except Exception as err:
        print(f"Manual event error: {err}")

# ------------------------ calendar build ------------------------

def build_calendar(
    loc: LocationConfig,
    ts, planets, earth, sun, moon,
    tithi_changes: List[datetime], tithi_vals: List[int],
    nak_changes: List[datetime], nak_vals: List[int],
) -> Calendar:
    tz = pytz.timezone(loc.tz)

    start_d = datetime.now(tz).date()
    end_d = start_d + timedelta(days=DAYS_AHEAD)

    # Precompute Puthandu dates needed for year labelling
    years_needed = range(start_d.year - 1, end_d.year + 2)
    puthandu_by_year: Dict[int, date] = {}
    for y in years_needed:
        puthandu_by_year[y] = puthandu_civil_date(y, ts, planets, earth, sun, loc)

    # Sunrise/sunset for daily panchangam range
    sunr, suns = sun_events_range(ts, planets, loc, start_d, end_d)
    month_info = month_day_numbers(earth, sun, ts, sunr, start_d, end_d)

    cal = Calendar()

    # Daily Panchangam all-day events
    d = start_d
    while d < end_d:
        sr = sunr.get(d)
        ss = suns.get(d)
        nsr = sunr.get(d + timedelta(days=1))

        if sr and ss and nsr:
            mname, mday, rname = month_info.get(d, ("N/A", 0, "N/A"))
            desc = daily_panchangam_description(
                loc, d, mname, mday, rname, sr, ss, nsr,
                tithi_changes, tithi_vals,
                nak_changes, nak_vals,
                puthandu_by_year,
                earth, sun, moon, ts
            )
            ev = Event()
            ev.name = f"{mname} - {mday:02d} ({fmt_date(d)}) {weekday_name(d)}"
            ev.description = desc
            ev.begin = d.isoformat()
            ev.make_all_day()
            ev.uid = f"{loc.key}-{d.isoformat()}@panchangam"
            cal.events.add(ev)

        d += timedelta(days=1)

    # Shukla Ekadasi timed events only
    t0_utc = tz.localize(datetime.combine(start_d, time(0, 0))).astimezone(UTC)
    t1_utc = tz.localize(datetime.combine(end_d, time(0, 0))).astimezone(UTC)

    i0 = max(0, bisect_right(tithi_changes, t0_utc) - 1)
    i1 = min(len(tithi_changes) - 1, bisect_left(tithi_changes, t1_utc))

    for i in range(i0, i1):
        tv = tithi_vals[i]
        if tv not in SPECIAL_TITHIS:
            continue

        a = tithi_changes[i]
        b = tithi_changes[i + 1] if i + 1 < len(tithi_changes) else t1_utc

        if b <= t0_utc or a >= t1_utc:
            continue

        ev = Event()
        ev.name = SPECIAL_TITHIS[tv]
        ev.begin = a.astimezone(tz)
        ev.end = b.astimezone(tz)
        ev.description = f"Exact Astronomical Duration ({loc.display_name})"
        ev.uid = f"{loc.key}-{a.strftime('%Y%m%d%H%M')}-{tv}@tithi"
        cal.events.add(ev)

    add_manual_events(cal, tz, loc.key)
    return cal

def main() -> None:
    ts = load.timescale()
    planets = load("de421.bsp")
    earth, moon, sun = planets["earth"], planets["moon"], planets["sun"]

    # Precompute tithi and nakshatra transitions globally over rolling horizon
    utc_now = datetime.now(UTC)
    global_start = utc_now - timedelta(days=3)
    global_end = utc_now + timedelta(days=DAYS_AHEAD + 10)

    def f_tithi(t): return tithi_idx(t, earth, sun, moon)
    f_tithi.step_days = DISCRETE_STEP_DAYS
    tithi_changes, tithi_vals = precompute_discrete(ts, global_start, global_end, f_tithi)

    def f_nak(t): return nak_idx(t, earth, moon)
    f_nak.step_days = DISCRETE_STEP_DAYS
    nak_changes, nak_vals = precompute_discrete(ts, global_start, global_end, f_nak)

    for loc in LOCATIONS:
        cal = build_calendar(loc, ts, planets, earth, sun, moon, tithi_changes, tithi_vals, nak_changes, nak_vals)
        with open(loc.out_ics, "w", encoding="utf-8") as f:
            f.writelines(cal.serialize_iter())
        print(f"Wrote {loc.out_ics} ({len(cal.events)} events)")

if __name__ == "__main__":
    main()