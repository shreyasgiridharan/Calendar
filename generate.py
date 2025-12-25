#!/usr/bin/env python3
"""
Indian Panchangam ICS generator (Tamil & Telugu support).
Version: 15.1 (Bugfix: Fixed datetime object type mismatch in Lunar Month calculation)
"""

from __future__ import annotations

import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

import json
import os
from dataclasses import dataclass
from datetime import datetime, date, time, timedelta
from bisect import bisect_left, bisect_right
from typing import Dict, List, Tuple, Optional, Set

import numpy as np
import pytz
from ics import Calendar, Event
from ics.alarm import DisplayAlarm
from skyfield.api import load, wgs84
from skyfield import almanac
from skyfield.searchlib import find_discrete

UTC = pytz.UTC

MANUAL_FILE = "manual_events.json"
DAYS_AHEAD = int(os.environ.get("DAYS_AHEAD", "366"))
DISCRETE_STEP_DAYS = float(os.environ.get("DISCRETE_STEP_DAYS", "0.04"))

# --- Localization Data ---

TRANS = {
    "Header": {"TA": "Kurippu", "TE": "Vivaralu"},
    "Year": {"TA": "Varudam", "TE": "Samvatsaram"},
    "Ayanam": {"TA": "Ayanam", "TE": "Ayanam"},
    "Ruthu": {"TA": "Ruthu", "TE": "Ruthuvu"},
    "Month": {"TA": "Masam", "TE": "Masam"},
    "Paksham": {"TA": "Paksham", "TE": "Paksham"},
    "Tithi": {"TA": "Thithi", "TE": "Tithi"},
    "Day": {"TA": "Naal", "TE": "Varam"},
    "Nakshatra": {"TA": "Nakshatthiram", "TE": "Nakshatram"},
    "Yoga": {"TA": "Yogam", "TE": "Yogam"},
    "Karana": {"TA": "Karanam", "TE": "Karanam"},
    "YogaQuality": {"TA": "Yogam Vakai", "TE": "Yogam Type"},
    "Rahu": {"TA": "Raghu Kalam", "TE": "Rahu Kalam"},
    "Yama": {"TA": "Yemakandam", "TE": "Yamagandam"},
    "Kuligai": {"TA": "Kuligai", "TE": "Gulika"},
    "Gowri": {"TA": "Nalla Neram (Gowri)", "TE": "Subha Samayam"},
    "Durmuhurtham": {"TA": "Durmuhurtham", "TE": "Durmuhurtham"},
    "Abhijit": {"TA": "Abhijit", "TE": "Abhijit Muhurtham"},
    "Sunrise": {"TA": "Surya Udhayam", "TE": "Suryodayam"},
    "Sunset": {"TA": "Surya Asthamanam", "TE": "Suryastamayam"},
    "Moonrise": {"TA": "Chandrodayam", "TE": "Chandrodayam"},
    "Chandrashtamam": {"TA": "Chandrashtamam", "TE": "Chandrashtamam"},
    "Soolam": {"TA": "Soolam", "TE": "Soola"},
    "Pariharam": {"TA": "Pariharam", "TE": "Pariharam"},
    "Sradhdha": {"TA": "Sradhdha Thithi", "TE": "Taddinam Tithi"},
    "Location": {"TA": "Idam", "TE": "Pradesham"},
    "Pada": {"TA": "Paadham", "TE": "Padam"},
}

TITHI_NAMES = {
    "TA": [
        "Unknown", "Prathamai", "Dwitiyai", "Tritiyai", "Chathurthi", "Panchami", "Shashti", "Saptami", "Ashtami", "Navami", "Dashami", "Ekadashi", "Dwadashi", "Trayodashi", "Chadhurdasi", "Pournami",
        "Prathamai", "Dwitiyai", "Tritiyai", "Chathurthi", "Panchami", "Shashti", "Saptami", "Ashtami", "Navami", "Dashami", "Ekadashi", "Dwadashi", "Trayodashi", "Chadhurdasi", "Amavasai"
    ],
    "TE": [
        "Unknown", "Padyami", "Vidiya", "Thadiya", "Chavithi", "Panchami", "Shashti", "Saptami", "Ashtami", "Navami", "Dashami", "Ekadashi", "Dwadashi", "Trayodashi", "Chaturdashi", "Pournami",
        "Padyami", "Vidiya", "Thadiya", "Chavithi", "Panchami", "Shashti", "Saptami", "Ashtami", "Navami", "Dashami", "Ekadashi", "Dwadashi", "Trayodashi", "Chaturdashi", "Amavasya"
    ]
}

NAKSHATRA_NAMES = {
    "TA": [
        "Unknown", "Ashwini", "Bharani", "Karthigai", "Rohini", "Mrigashirsham", "Thiruvathirai", "Punarpoosam", "Poosam", "Aayilyam",
        "Magam", "Pooram", "Uthiram", "Hastham", "Chitthirai", "Swathi", "Visakam", "Anusham", "Kettai", "Moolam", "Pooradam",
        "Uthiradam", "Thiruvonam", "Avittam", "Sathayam", "Poorattathi", "Uthirattathi", "Revathi"
    ],
    "TE": [
        "Unknown", "Aswini", "Bharani", "Kruthika", "Rohini", "Mrigashira", "Arudra", "Punarvasu", "Pushyami", "Ashlesha",
        "Makha", "Pubba", "Uttara", "Hasta", "Chitta", "Swathi", "Vishakha", "Anuradha", "Jyeshta", "Moola", "Poorvashada",
        "Uttarashada", "Shravana", "Dhanishta", "Shatabhisham", "Poorvabhadra", "Uttarabhadra", "Revathi"
    ]
}

YOGA_NAMES = {
    "TA": [
        "Unknown", "Vishkambha", "Priti", "Aayushman", "Saubhagya", "Shobhana", "Atiganda", "Sukarman", "Dhriti", "Shoola", "Ganda",
        "Vriddhi", "Dhruva", "Vyaghata", "Harshana", "Vajra", "Siddhi", "Vyatipata", "Variyana", "Parigha", "Shiva", "Siddha",
        "Sadhya", "Shubha", "Shukla", "Brahma", "Indra", "Vaidhriti"
    ],
    "TE": [
        "Unknown", "Vishkambha", "Preethi", "Aayushman", "Saubhagya", "Shobhana", "Atiganda", "Sukarman", "Dhruthi", "Shoola", "Ganda",
        "Vriddhi", "Dhruva", "Vyaghata", "Harshana", "Vajra", "Siddhi", "Vyatipata", "Variyana", "Parigha", "Shiva", "Siddha",
        "Sadhya", "Shubha", "Shukla", "Brahma", "Indra", "Vaidhriti"
    ]
}

RASI_NAMES = {
    "TA": ("Mesham", "Rishabam", "Mithunam", "Katakam", "Simham", "Kanni", "Thulam", "Virutchigam", "Dhanus", "Makaram", "Kumbham", "Meenam"),
    "TE": ("Mesham", "Vrushabham", "Mithunam", "Karkatakam", "Simham", "Kanya", "Thula", "Vrushchikam", "Dhanu", "Makaram", "Kumbham", "Meenam")
}

SOLAR_MONTH_NAMES = {
    "TA": ("Chithirai", "Vaikasi", "Aani", "Aadi", "Aavani", "Purattasi", "Aippasi", "Karthigai", "Margazhi", "Thai", "Maasi", "Panguni"),
    "TE": ("Mesham", "Vrushabham", "Mithunam", "Karkatakam", "Simham", "Kanya", "Thula", "Vrushchikam", "Dhanu", "Makaram", "Kumbham", "Meenam")
}

LUNAR_MONTH_NAMES = {
    "TA": ("Chaitra", "Vaisakha", "Jyeshtha", "Ashada", "Sravana", "Bhadrapada", "Asvayuja", "Kartika", "Margashira", "Pushya", "Magha", "Phalguna"),
    "TE": ("Chaitramu", "Vaishakhamu", "Jyeshthamu", "Ashadhamu", "Sravanamu", "Bhadrapadamu", "Ashwayujamu", "Karthikamu", "Margashiramu", "Pushyamu", "Maghamu", "Phalgunamu")
}

WEEKDAY_NAMES = {
    "TA": ("Thingal", "Sevvai", "Budhan", "Vyazhan", "Velli", "Sani", "Nyayiru"),
    "TE": ("Somavaram", "Mangalavaram", "Budhavaram", "Guruvaram", "Shukravaram", "Shanivaram", "Bhanuvaram")
}

PAKSHA_NAMES = {
    "TA": ("Shukla Paksham", "Krushna Paksham"),
    "TE": ("Shukla Paksham", "Krishna Paksham")
}

RITU_NAMES = {
    "TA": ("Vasantha Ruthu", "Grishma Ruthu", "Varsha Ruthu", "Sarath Ruthu", "Hemantha Ruthu", "Shishira Ruthu"),
    "TE": ("Vasantha Ruthuvu", "Grishma Ruthuvu", "Varsha Ruthuvu", "Sarad Ruthuvu", "Hemantha Ruthuvu", "Shishira Ruthuvu")
}

SAMVATSARA_NAMES = [
    "Prabhava", "Vibhava", "Shukla", "Pramodadhoota", "Prajapati", "Angirasa", "Srimukha", "Bhava", "Yuva", "Dhatu",
    "Eeswara", "Vehudhanya", "Pramathi", "Vikrama", "Vishu", "Chitrabhanu", "Subhanu", "Dharana", "Parthiba", "Viya",
    "Sarvajit", "Sarvadhari", "Virodhi", "Vikruthi", "Kara", "Nandhana", "Vijaya", "Jaya", "Manmatha", "Dhunmuki",
    "Hevilambi", "Vilambi", "Vikari", "Sarvari", "Plava", "Subhakrit", "Shobakrit", "Krodhi", "Vishvavasu", "Parabhava",
    "Plavanga", "Keelaka", "Soumya", "Sadharana", "Virodhakrit", "Paridhabi", "Pramadhicha", "Anandha", "Rakshasa", "Nala",
    "Pingala", "Kalayukti", "Siddharthi", "Raudhri", "Dhunmathi", "Dhundubhi", "Rudhirothgari", "Rakshasi", "Krodhana", "Akshaya",
]
BASE_SAMVATSARA_YEAR = 1987

LAHIRI_AYANAMSA_DEG_AT_J2000 = float(os.environ.get("LAHIRI_AYANAMSA_DEG_AT_J2000", "23.85675"))
LAHIRI_AYANAMSA_RATE_DEG_PER_YEAR = float(os.environ.get("LAHIRI_AYANAMSA_RATE_DEG_PER_YEAR", str(50.290966 / 3600.0)))
J2000_TT = 2451545.0

@dataclass(frozen=True)
class LocationConfig:
    key: str
    display_name: str
    lat: float
    lon: float
    tz: str
    out_ics: str
    style: str  # "TAMIL" or "TELUGU"
    lang: str   # "TA" or "TE"

LOCATIONS = (
    LocationConfig("stuttgart-ta", "Stuttgart (Tamil Style)", 48.7758, 9.1829, "Europe/Berlin", "Calendar-Stuttgart-Tamil.ics", "TAMIL", "TA"),
    LocationConfig("stuttgart-te", "Stuttgart (Telugu Style)", 48.7758, 9.1829, "Europe/Berlin", "Calendar-Stuttgart-Telugu.ics", "TELUGU", "TE"),
    LocationConfig("india-ta", "Hyderabad (Tamil Style)", 17.38504, 78.48667, "Asia/Kolkata", "Calendar-India-Tamil.ics", "TAMIL", "TA"),
    LocationConfig("india-te", "Hyderabad (Telugu Style)", 17.38504, 78.48667, "Asia/Kolkata", "Calendar-India-Telugu.ics", "TELUGU", "TE"),
)

# ------------------------ Rich Festival Data ------------------------

@dataclass
class RichFestival:
    name: str
    deity: str
    food: str
    # Criteria
    lunar_month_idx: int = -1 # 0=Chaitra, etc.
    tithi_idx: int = -1       # 1=Prathama
    paksha_idx: int = -1      # 0=Shukla, 1=Krishna
    # Solar Criteria
    solar_month_name: str = ""
    solar_day: int = -1
    # Nakshatra Criteria
    nakshatra_idx: int = -1
    req_solar_month_for_nak: str = "" # e.g., "Karthigai"
    # Complex
    is_varalakshmi: bool = False

COMMON_FESTIVALS = [
    RichFestival("Deepavali", "Goddess Lakshmi", "Sweets, Murukku", lunar_month_idx=6, paksha_idx=1, tithi_idx=14), # Naraka Chaturdashi/Amavasya
    RichFestival("Vinayaka Chavithi", "Lord Ganesha", "Kozhukattai / Kudumulu", lunar_month_idx=5, paksha_idx=0, tithi_idx=4),
    RichFestival("Vijaya Dasami", "Goddess Durga", "Sweets", lunar_month_idx=6, paksha_idx=0, tithi_idx=10),
]

FESTIVALS_TA = COMMON_FESTIVALS + [
    RichFestival("Thai Pongal", "Sun God", "Sakkarai Pongal", solar_month_name="Thai", solar_day=1),
    RichFestival("Tamil Puthandu", "N/A", "Mango Pachadi, Vadai, Payasam", solar_month_name="Chithirai", solar_day=1),
    # Nakshatra Festivals
    RichFestival("Karthigai Deepam", "Lord Shiva/Murugan", "Pori Urundai, Appam", nakshatra_idx=3, req_solar_month_for_nak="Karthigai"), # 3 = Krithika
    RichFestival("Thai Poosam", "Lord Murugan", "Panjamirtham", nakshatra_idx=8, req_solar_month_for_nak="Thai"), # 8 = Poosam
    RichFestival("Panguni Uthiram", "Divine Couples", "Neer Mor, Panakam", nakshatra_idx=12, req_solar_month_for_nak="Panguni"), # 12 = Uthiram
]

FESTIVALS_TE = COMMON_FESTIVALS + [
    RichFestival("Ugadi", "N/A", "Ugadi Pachadi", lunar_month_idx=0, paksha_idx=0, tithi_idx=1),
    RichFestival("Srirama Navami", "Lord Rama", "Panakam, Vadapappu", lunar_month_idx=0, paksha_idx=0, tithi_idx=9),
    RichFestival("Vaikunta Ekadashi", "Lord Vishnu", "Fasting / Light Food", lunar_month_idx=8, paksha_idx=0, tithi_idx=11),
    RichFestival("Varalakshmi Vratam", "Goddess Lakshmi", "Burelu, Garelu, Pulihora", is_varalakshmi=True),
    RichFestival("Bhogi", "Lord Indra", "Pulagam", solar_month_name="Makaram", solar_day=-1), # Special handling logic needed if strictly solar, usually day before Pongal
]

@dataclass
class VratamEvent:
    name: str
    start: datetime
    end: datetime

@dataclass
class DisplayEvent:
    name: str
    desc: str
    uid_suffix: str

# ------------------------ formatting & lookups ------------------------

def get_name(dictionary, idx, lang):
    lst = dictionary.get(lang, dictionary["TA"])
    if 0 <= idx < len(lst): return lst[idx]
    return "Unknown"

def get_label(key, lang):
    return TRANS.get(key, {}).get(lang, key)

def fmt_date(d: date) -> str:
    return d.strftime("%d.%m.%Y")

def fmt_time(dt: datetime) -> str:
    h, m = dt.hour, dt.minute
    if h == 12 and m == 0: return "12 Noon"
    if h == 0: return f"12.{m:02d} AM"
    if 1 <= h <= 11: return f"{h}.{m:02d} AM"
    if h == 12: return f"12.{m:02d} PM"
    return f"{h-12}.{m:02d} PM"

def fmt_interval(a: datetime, b: datetime) -> str:
    return f"{fmt_time(a)} to {fmt_time(b)}"

def ascii_table(rows):
    lines = []
    for k, v in rows:
        k = str(k).strip()
        v = "" if v is None else str(v).strip()
        if k.lower() == "header":
            if v: lines.extend([v, ""])
            continue
        if k: lines.append(f"{k}: {v}")
        elif v: lines.append(v)
    return "\n".join(lines).strip()

# ------------------------ astronomy helpers ------------------------

def normalize_deg(x): return np.mod(x, 360.0)

def ayanamsa_deg(t):
    years = np.asarray((t.tt - J2000_TT) / 365.2425)
    return LAHIRI_AYANAMSA_DEG_AT_J2000 + LAHIRI_AYANAMSA_RATE_DEG_PER_YEAR * years

def sidereal_lon(lon_deg, t):
    return normalize_deg(np.asarray(lon_deg) - ayanamsa_deg(t))

def sf_to_utc_dt(t) -> datetime:
    dt = t.utc_datetime()
    if dt.tzinfo is None: return UTC.localize(dt)
    return dt.astimezone(UTC)

def precompute_discrete(ts, t0_utc, t1_utc, f):
    times, values = find_discrete(ts.from_datetime(t0_utc), ts.from_datetime(t1_utc), f)
    return [sf_to_utc_dt(t) for t in times], [int(v) for v in values]

def value_at(t_utc, changes, values):
    i = bisect_right(changes, t_utc) - 1
    return values[0] if i < 0 else values[i]

def transitions_between(a_utc, b_utc, changes, values):
    i = bisect_right(changes, a_utc)
    j = bisect_left(changes, b_utc)
    return [(changes[k], values[k]) for k in range(i, j)]

def tithi_idx(t, earth, sun, moon):
    e = earth.at(t)
    _, slon, _ = e.observe(sun).apparent().ecliptic_latlon()
    _, mlon, _ = e.observe(moon).apparent().ecliptic_latlon()
    return (normalize_deg(mlon.degrees - slon.degrees) // 12.0).astype(int) + 1

def nak_idx(t, earth, moon):
    e = earth.at(t)
    _, mlon, _ = e.observe(moon).apparent().ecliptic_latlon()
    return (sidereal_lon(mlon.degrees, t) // (360.0/27.0)).astype(int) + 1

def calculate_pada(t, earth, moon):
    e = earth.at(t)
    _, mlon, _ = e.observe(moon).apparent().ecliptic_latlon()
    s_lon = sidereal_lon(mlon.degrees, t)
    nak_start_deg = (s_lon // (360.0/27.0)) * (360.0/27.0)
    deg_in_nak = s_lon - nak_start_deg
    pada = int(deg_in_nak / (360.0/108.0)) + 1
    if pada > 4: pada = 4
    return pada

def yoga_idx(t, earth, sun, moon):
    e = earth.at(t)
    _, slon, _ = e.observe(sun).apparent().ecliptic_latlon()
    _, mlon, _ = e.observe(moon).apparent().ecliptic_latlon()
    total = normalize_deg(sidereal_lon(slon.degrees, t) + sidereal_lon(mlon.degrees, t))
    return (total // (360.0/27.0)).astype(int) + 1

def solar_rasi_idx(t, earth, sun):
    e = earth.at(t)
    _, slon, _ = e.observe(sun).apparent().ecliptic_latlon()
    return (sidereal_lon(slon.degrees, t) // 30.0).astype(int)

def moon_rasi_idx(t, earth, moon):
    e = earth.at(t)
    _, mlon, _ = e.observe(moon).apparent().ecliptic_latlon()
    return (sidereal_lon(mlon.degrees, t) // 30.0).astype(int)

def karana_num(t, earth, sun, moon):
    e = earth.at(t)
    _, slon, _ = e.observe(sun).apparent().ecliptic_latlon()
    _, mlon, _ = e.observe(moon).apparent().ecliptic_latlon()
    return (normalize_deg(mlon.degrees - slon.degrees) // 6.0).astype(int) + 1

def karana_name(n: int) -> str:
    if n == 1: return "Kimstughna"
    if n == 58: return "Shakuni"
    if n == 59: return "Chatushpada"
    if n == 60: return "Nagava"
    rep = ("Bavai", "Balavai", "Kaulavai", "Thaitilai", "Garajai", "Vanijai", "Vishti")
    return rep[(n - 2) % 7]

def tithi_name(i, lang): return get_name(TITHI_NAMES, i, lang)
def nak_name(i, lang): return get_name(NAKSHATRA_NAMES, i, lang)
def yoga_name(i, lang): return get_name(YOGA_NAMES, i, lang)
def rasi_name(i, lang): return get_name(RASI_NAMES, i, lang)
def solar_month_name(i, lang): return get_name(SOLAR_MONTH_NAMES, i, lang)
def lunar_month_name(i, lang): return get_name(LUNAR_MONTH_NAMES, i, lang)
def weekday_name(d, lang): return get_name(WEEKDAY_NAMES, d.weekday(), lang)
def paksha(i, lang): return get_name(PAKSHA_NAMES, 0 if i <= 15 else 1, lang)
def get_ritu(idx, is_solar, lang): return get_name(RITU_NAMES, (idx // 2) % 6, lang)

def ayanam_name(t, earth, sun, lang) -> str:
    e = earth.at(t)
    _, slon, _ = e.observe(sun).apparent().ecliptic_latlon()
    lon = float(normalize_deg(slon.degrees))
    return "Dakshinayanam" if (90.0 <= lon < 270.0) else "Uttarayanam"

def describe_trans(start, trans, connector):
    if not trans: return start
    if len(trans) == 1:
        t1, v2 = trans[0]
        return f"upto {fmt_time(t1)} {start}, {connector} {v2}"
    t1, v2 = trans[0]
    t2, v3 = trans[1]
    return f"upto {fmt_time(t1)} {start}, upto {fmt_time(t2)} {v2}, {connector} {v3}"

# ------------------------ Special Times ------------------------

def rahu_yama_gulika(d, sunrise, sunset):
    L = (sunset - sunrise).total_seconds()
    if L <= 0: return "N/A", "N/A", "N/A"
    part = L / 8.0
    wd = d.weekday() # 0=Mon
    r_map = {0:1, 1:6, 2:4, 3:5, 4:3, 5:2, 6:7}
    y_map = {0:3, 1:2, 2:1, 3:0, 4:6, 5:5, 6:4}
    g_map = {0:4, 1:3, 2:2, 3:1, 4:0, 5:6, 6:5}
    def seg(idx):
        s = sunrise + timedelta(seconds=part * idx)
        e = sunrise + timedelta(seconds=part * (idx+1))
        if idx >= 7: e = sunset
        return fmt_interval(s, e)
    return seg(r_map[wd]), seg(y_map[wd]), seg(g_map[wd])

DURMUHURTHAM_IDX = {6: [13], 0: [8], 1: [2, 6], 2: [5], 3: [9], 4: [3, 8], 5: [0]}

def durmuhurtham(d, sunrise, sunset):
    L = (sunset - sunrise).total_seconds()
    part = L / 15.0
    indices = DURMUHURTHAM_IDX.get(d.weekday(), [])
    res = []
    for i in indices:
        s = sunrise + timedelta(seconds=part * i)
        e = sunrise + timedelta(seconds=part * (i+1))
        res.append(fmt_interval(s, e))
    return ", ".join(res) if res else "N/A"

def abhijit_muhurtham(sunrise, sunset):
    L = (sunset - sunrise).total_seconds()
    part = L / 15.0
    s = sunrise + timedelta(seconds=part * 7)
    e = sunrise + timedelta(seconds=part * 8)
    return fmt_interval(s, e)

def amirtha_siddha_marana(weekday_idx, nak_idx_now, lang):
    marana = {6:{2,3,10,16}, 0:{14,23,20}, 1:{21,24,26}, 2:{1,9,19,23}, 3:{5,10,16}, 4:{4,18,20}, 5:{27,11,12,13}}
    amirtha = {6:{13,19}, 0:{5}, 1:{1}, 2:{17}, 3:{8}, 4:{27}, 5:{4}}
    qual = "Siddha Yogam"
    if nak_idx_now in marana.get(weekday_idx, set()): qual = "Marana Yogam"
    elif nak_idx_now in amirtha.get(weekday_idx, set()): qual = "Amirtha Yogam"
    if lang == "TE": return qual.replace("Yogam", "Yogamu")
    return qual

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

def gowri_good_time(d, sunrise, sunset):
    L = (sunset - sunrise).total_seconds()
    if L <= 0: return "N/A"
    slot = L / 8.0
    seq = GOWRI_SEQ.get(d.weekday())
    good_slots = []
    for i, q in enumerate(seq):
        if q in GOOD_GOWRI:
            good_slots.append((sunrise + timedelta(seconds=slot*i), sunrise + timedelta(seconds=slot*(i+1))))
    if not good_slots: return "N/A"
    noon = sunrise.replace(hour=12, minute=0, second=0)
    morning = next((ab for ab in good_slots if ab[0] < noon), None)
    evening = next((ab for ab in good_slots if ab[0] >= noon), None)
    if morning and evening and morning != evening: return f"{fmt_interval(*morning)} and {fmt_interval(*evening)}"
    if morning: return fmt_interval(*morning)
    return fmt_interval(*good_slots[0])

SOOLAM_PARIHARAM = {
    6: ("West",  "Jaggery / Vellam"), 0: ("East",  "Curd / Thayir"), 1: ("North", "Milk / Paal"),
    2: ("North", "Milk / Paal"), 3: ("South", "Oil / Thailam"), 4: ("West",  "Jaggery / Vellam"),
    5: ("East",  "Curd / Thayir"),
}
def soolam_and_prayatchittham(d): return SOOLAM_PARIHARAM.get(d.weekday(), ("N/A", "N/A"))

def sradhdha_tithi_aparahna(sunrise, sunset, tithi_changes, tithi_vals, lang):
    L = (sunset - sunrise).total_seconds()
    if L <= 0: return "N/A"
    part = L / 5.0
    a_start = sunrise + timedelta(seconds=3 * part)
    a_end = sunrise + timedelta(seconds=4 * part)
    a0, a1 = a_start.astimezone(UTC), a_end.astimezone(UTC)
    cur = value_at(a0, tithi_changes, tithi_vals)
    trans = transitions_between(a0, a1, tithi_changes, tithi_vals)
    segments = []
    prev = a0
    for t, v in trans:
        segments.append((prev, t, cur))
        prev, cur = t, v
    segments.append((prev, a1, cur))
    best_v, best_len = None, -1.0
    for x0, x1, v in segments:
        ln = (x1 - x0).total_seconds()
        if ln > best_len: best_len, best_v = ln, v
    return tithi_name(int(best_v), lang) if best_v else "N/A"

def chandhirashtamam_target(moon_rasi_idx_now, lang):
    return rasi_name((moon_rasi_idx_now - 7) % 12, lang)

# ------------------------ Moonrise & Vratam Logic ------------------------

def calculate_moonrise(d, loc, ts, planets):
    # Calculate moonrise for the given civil date
    tz = pytz.timezone(loc.tz)
    location = wgs84.latlon(loc.lat, loc.lon)
    t0 = tz.localize(datetime.combine(d, time(0,0))).astimezone(UTC)
    t1 = tz.localize(datetime.combine(d+timedelta(days=1), time(0,0))).astimezone(UTC)
    
    f = almanac.risings_and_settings(planets, planets['moon'], location)
    times, values = find_discrete(ts.from_datetime(t0), ts.from_datetime(t1), f)
    
    # values: true=rise, false=set
    for t, is_rise in zip(times, values):
        if is_rise:
            return sf_to_utc_dt(t).astimezone(tz)
    return None

def get_tithi_span(target_tithi: int, search_center: datetime, changes: List[datetime], values: List[int]) -> Optional[Tuple[datetime, datetime]]:
    """
    Finds the exact start and end times of the target_tithi that is active around search_center.
    """
    idx = bisect_right(changes, search_center) - 1
    if idx < 0 or idx >= len(values):
        return None
        
    current_val = values[idx]
    if current_val != target_tithi:
        # If the tithi at center is not the target (e.g. edge case), check immediate neighbors
        if idx + 1 < len(values) and values[idx+1] == target_tithi:
            idx = idx + 1
        elif idx - 1 >= 0 and values[idx-1] == target_tithi:
            idx = idx - 1
        else:
            return None
            
    # Now changes[idx] is start, changes[idx+1] is end
    start_time = changes[idx]
    end_time = changes[idx+1] if (idx + 1) < len(changes) else search_center + timedelta(hours=24)
    return start_time, end_time

def check_rich_festivals(loc, d, s_data, l_data, t_now, n_now) -> List[DisplayEvent]:
    hits = []
    rules = FESTIVALS_TE if loc.style == "TELUGU" else FESTIVALS_TA
    s_mname, s_day, _, _ = s_data or ("", 0, "", 0)
    l_mname, l_midx = l_data or ("", -1)
    
    # Simple Tithi/Solar checks
    curr_paksha_idx = 0 if t_now <= 15 else 1
    curr_tithi_norm = t_now if t_now <= 15 else (t_now - 15)

    for r in rules:
        matched = False
        
        # 1. Simple Solar Date Match (Pongal)
        if r.solar_month_name and s_mname == r.solar_month_name and s_day == r.solar_day:
            matched = True
            
        # 2. Simple Lunar Date Match (Diwali, Ugadi)
        elif r.lunar_month_idx != -1:
            if l_midx == r.lunar_month_idx and curr_paksha_idx == r.paksha_idx and curr_tithi_norm == r.tithi_idx:
                matched = True

        # 3. Nakshatra Match (Karthigai Deepam, Thai Poosam)
        # Note: Usually requires nakshatra to be active at a specific time (like evening). 
        # For simplicity, we check if nakshatra is active at Sunrise (n_now).
        elif r.nakshatra_idx != -1:
            if n_now == r.nakshatra_idx and s_mname == r.req_solar_month_for_nak:
                matched = True
        
        # 4. Varalakshmi Vratam (Friday before Sravana Purnima)
        # Sravana = month 4. Purnima = Tithi 15, Paksha 0.
        elif r.is_varalakshmi:
            if l_midx == 4 and curr_paksha_idx == 0:
                # We are in Shukla paksha of Sravana
                # Check if today is Friday (4)
                if d.weekday() == 4:
                    # Is it the last Friday before Purnima?
                    # If Purnima (15) is within next 7 days
                    days_to_purnima = 15 - curr_tithi_norm
                    if 0 <= days_to_purnima < 7:
                        matched = True

        if matched:
            desc = f"Deity: {r.deity}\nFood: {r.food}\nRules: {loc.display_name} Calendar"
            hits.append(DisplayEvent(name=f"🎉 {r.name}", desc=desc, uid_suffix=r.name.replace(" ","")))

    return hits

def check_special_vratams_timed(d, sunrise, sunset, tithi_changes, tithi_vals) -> List[VratamEvent]:
    vratams = []
    
    # 1. Ekadashi Check (Sunrise Rule)
    # Tithi 11 (Shukla) or 26 (Krishna)
    t_sunrise = value_at(sunrise.astimezone(UTC), tithi_changes, tithi_vals)
    if t_sunrise == 11 or t_sunrise == 26:
        name = "Ekadashi (Shukla)" if t_sunrise == 11 else "Ekadashi (Krishna)"
        span = get_tithi_span(t_sunrise, sunrise.astimezone(UTC), tithi_changes, tithi_vals)
        if span:
            vratams.append(VratamEvent(name, span[0], span[1]))

    # 2. Sashti (Shukla) Check
    # Tithi 6 (Shukla Sashti)
    if t_sunrise == 6:
        span = get_tithi_span(6, sunrise.astimezone(UTC), tithi_changes, tithi_vals)
        if span:
            vratams.append(VratamEvent("Sashti (Shukla)", span[0], span[1]))

    # 3. Pradosham Check
    # Check Tithi at Sunset - 45 mins (Center of Pradosha Kalam)
    check_time = sunset - timedelta(minutes=45)
    t_pradosham = value_at(check_time.astimezone(UTC), tithi_changes, tithi_vals)
    if t_pradosham in [13, 28]:
        suffix = " (Shukla)" if t_pradosham == 13 else " (Krishna)"
        span = get_tithi_span(t_pradosham, check_time.astimezone(UTC), tithi_changes, tithi_vals)
        if span:
            vratams.append(VratamEvent("Pradosham" + suffix, span[0], span[1]))

    # 4. Sankatahara Chathurthi Check
    # Krishna Paksha Chathurthi = 19
    # Check if Tithi 19 prevails at 9:00 PM local time
    check_time_night = sunset.replace(hour=21, minute=0)
    t_night = value_at(check_time_night.astimezone(UTC), tithi_changes, tithi_vals)
    if t_night == 19:
        span = get_tithi_span(19, check_time_night.astimezone(UTC), tithi_changes, tithi_vals)
        if span:
            vratams.append(VratamEvent("Sankatahara Chathurthi", span[0], span[1]))
        
    return vratams

# ------------------------ Render ------------------------

def daily_panchangam(loc, d, s_data, l_data, sr, ss, mr, nsr, t_ch, t_v, n_ch, n_v, ny_dates, earth, sun, moon, ts):
    tz = pytz.timezone(loc.tz)
    sr_utc = sr.astimezone(UTC)
    nsr_utc = nsr.astimezone(UTC)
    t_sr = ts.from_datetime(sr_utc)
    lang = loc.lang

    t_now = value_at(sr_utc, t_ch, t_v)
    t_trans = [(t.astimezone(tz), tithi_name(v, lang)) for t,v in transitions_between(sr_utc, nsr_utc, t_ch, t_v)]
    t_str = describe_trans(tithi_name(t_now, lang), t_trans, "thereafter")
    
    n_now = value_at(sr_utc, n_ch, n_v)
    curr_pada = calculate_pada(t_sr, earth, moon)
    curr_nak_str = f"{nak_name(n_now, lang)} ({curr_pada} {get_label('Pada', lang)})"
    n_trans = [(t.astimezone(tz), nak_name(v, lang)) for t,v in transitions_between(sr_utc, nsr_utc, n_ch, n_v)]
    n_str = describe_trans(curr_nak_str, n_trans, "and then")
    
    yog = int(yoga_idx(t_sr, earth, sun, moon))
    kar = int(karana_num(t_sr, earth, sun, moon))
    mr_rasi = int(moon_rasi_idx(t_sr, earth, moon))
    rahu, yama, guli = rahu_yama_gulika(d, sr, ss)
    yr_name = samvatsara_for_date(d, ny_dates)
    wk_name = weekday_name(d, lang)
    
    festivals = check_rich_festivals(loc, d, s_data, l_data, t_now, n_now)
    vratam_events = check_special_vratams_timed(d, sr, ss, t_ch, t_v)
    
    # Combine names for ASCII table
    special_names = [f.name.replace("🎉 ", "") for f in festivals] + [v.name for v in vratam_events]
    event_str = ", ".join(special_names) if special_names else ""
    tithi_emoji = "🌕" if t_now == 15 else ("🌑" if t_now == 30 else "")
    
    rows = []
    
    if loc.style == "TAMIL":
        mname, mday, rasi, midx = s_data
        header = f"{mname} {mday:02d} {tithi_emoji} {wk_name}"
        rows.append(("Header", header))
        if event_str: rows.append(("🎉 SPECIAL", event_str))
        rows.append((get_label("Year", lang), f"{yr_name} {get_label('Year', lang)}"))
        rows.append((get_label("Ayanam", lang), ayanam_name(t_sr, earth, sun, lang)))
        rows.append((get_label("Ruthu", lang), get_ritu(midx, True, lang)))
        rows.append((get_label("Month", lang), f"{mname} ({rasi})"))
        rows.append((get_label("Paksham", lang), paksha(t_now, lang)))
        rows.append((get_label("Tithi", lang), t_str))
        rows.append((get_label("Day", lang), wk_name))
        rows.append((get_label("Nakshatra", lang), n_str))
        rows.append((get_label("Yoga", lang), yoga_name(yog, lang)))
        rows.append((get_label("Karana", lang), karana_name(kar)))
        rows.append((get_label("YogaQuality", lang), amirtha_siddha_marana(d.weekday(), int(n_now), lang)))
        rows.append((get_label("Rahu", lang), rahu))
        rows.append((get_label("Yama", lang), yama))
        rows.append((get_label("Kuligai", lang), guli))
        rows.append((get_label("Gowri", lang), gowri_good_time(d, sr, ss)))
        rows.append((get_label("Soolam", lang), soolam_and_prayatchittham(d)[0]))
        rows.append((get_label("Pariharam", lang), soolam_and_prayatchittham(d)[1]))
    else:
        mname, midx = l_data
        curr_tithi = tithi_name(t_now, lang)
        pk = paksha(t_now, lang)
        header = f"{mname} {pk} {curr_tithi} {tithi_emoji} ({fmt_date(d)})"
        rows.append(("Header", header))
        if event_str: rows.append(("🎉 SPECIAL", event_str))
        rows.append((get_label("Year", lang), f"{yr_name} {get_label('Year', lang)}"))
        rows.append((get_label("Ayanam", lang), ayanam_name(t_sr, earth, sun, lang)))
        rows.append((get_label("Ruthu", lang), get_ritu(midx, False, lang)))
        rows.append((get_label("Month", lang), mname))
        rows.append((get_label("Paksham", lang), pk))
        rows.append((get_label("Tithi", lang), t_str))
        rows.append((get_label("Day", lang), wk_name))
        rows.append((get_label("Nakshatra", lang), n_str))
        rows.append((get_label("Yoga", lang), yoga_name(yog, lang)))
        rows.append((get_label("Karana", lang), karana_name(kar)))
        rows.append((get_label("Rahu", lang), rahu))
        rows.append((get_label("Yama", lang), yama))
        rows.append((get_label("Durmuhurtham", lang), durmuhurtham(d, sr, ss)))
        rows.append((get_label("Abhijit", lang), abhijit_muhurtham(sr, ss)))

    rows.append((get_label("Sunrise", lang), fmt_time(sr)))
    rows.append((get_label("Sunset", lang), fmt_time(ss)))
    rows.append((get_label("Moonrise", lang), fmt_time(mr) if mr else "N/A"))
    rows.append((get_label("Chandrashtamam", lang), chandhirashtamam_target(mr_rasi, lang)))
    rows.append((get_label("Sradhdha", lang), sradhdha_tithi_aparahna(sr, ss, t_ch, t_v, lang)))
    rows.append((get_label("Location", lang), loc.display_name))
    
    return ascii_table(rows), header, festivals, vratam_events

# ------------------------ Calculation & I/O ------------------------

def sun_events_range(ts, planets, loc, start_d, end_d):
    tz = pytz.timezone(loc.tz)
    location = wgs84.latlon(loc.lat, loc.lon)
    t0 = tz.localize(datetime.combine(start_d-timedelta(days=2), time(0,0))).astimezone(UTC)
    t1 = tz.localize(datetime.combine(end_d+timedelta(days=2), time(0,0))).astimezone(UTC)
    f = almanac.sunrise_sunset(planets, location)
    times, states = almanac.find_discrete(ts.from_datetime(t0), ts.from_datetime(t1), f)
    sunr, suns = {}, {}
    for t, st in zip(times, states):
        dt = sf_to_utc_dt(t).astimezone(tz)
        if int(st) == 1: sunr[dt.date()] = dt
        else: suns[dt.date()] = dt
    return sunr, suns

def sunrise_sunset_for_local_date(ts, planets, loc, d):
    tz = pytz.timezone(loc.tz)
    location = wgs84.latlon(loc.lat, loc.lon)
    start_local = tz.localize(datetime.combine(d, time(0, 0)))
    t0 = (start_local - timedelta(hours=6)).astimezone(UTC)
    t1 = (start_local + timedelta(days=1, hours=6)).astimezone(UTC)
    f = almanac.sunrise_sunset(planets, location)
    times, states = almanac.find_discrete(ts.from_datetime(t0), ts.from_datetime(t1), f)
    sunrise, sunset = None, None
    for t, st in zip(times, states):
        dt_loc = sf_to_utc_dt(t).astimezone(tz)
        if dt_loc.date() != d: continue
        if int(st) == 1: sunrise = dt_loc
        else: sunset = dt_loc
    return sunrise, sunset

def wrap180(x): return ((x + 180.0) % 360.0) - 180.0
def sun_sidereal_lon_deg(sf_t, earth, sun):
    e = earth.at(sf_t)
    _, slon, _ = e.observe(sun).apparent().ecliptic_latlon()
    return float(sidereal_lon(slon.degrees, sf_t))

def mesha_sankranti_utc(year, ts, earth, sun):
    t0 = UTC.localize(datetime(year, 4, 10))
    t1 = UTC.localize(datetime(year, 4, 18))
    step = timedelta(hours=2)
    prev_dt, cur = t0, t0 + step
    bracket = None
    while cur <= t1:
        prev_f = wrap180(sun_sidereal_lon_deg(ts.from_datetime(prev_dt), earth, sun))
        cur_f = wrap180(sun_sidereal_lon_deg(ts.from_datetime(cur), earth, sun))
        if prev_f < 0.0 and cur_f > 0.0:
            bracket = (prev_dt, cur)
            break
        prev_dt = cur
        cur += step
    if not bracket: return t0
    lo, hi = bracket
    for _ in range(50):
        mid = lo + (hi - lo)/2
        if wrap180(sun_sidereal_lon_deg(ts.from_datetime(mid), earth, sun)) > 0: hi = mid
        else: lo = mid
    return lo

def puthandu_civil_date(year, ts, planets, earth, sun, loc):
    tz = pytz.timezone(loc.tz)
    ingress = mesha_sankranti_utc(year, ts, earth, sun).astimezone(tz)
    d = ingress.date()
    sr, ss = sunrise_sunset_for_local_date(ts, planets, loc, d)
    if sr and ss and ingress > ss: return d + timedelta(days=1)
    return d

def ugadi_civil_date(year, ts, planets, earth, sun, moon, loc):
    t_start = UTC.localize(datetime(year, 3, 10))
    t_end = UTC.localize(datetime(year, 4, 20))
    f = almanac.moon_phases(planets)
    times, phases = find_discrete(ts.from_datetime(t_start), ts.from_datetime(t_end), f)
    for t, phase in zip(times, phases):
        if phase == 0:
            s_lon = sun_sidereal_lon_deg(t, earth, sun)
            if 320 <= s_lon < 360:
                check_dt = sf_to_utc_dt(t).astimezone(pytz.timezone(loc.tz)).date()
                for d_off in range(3):
                    d_candidate = check_dt + timedelta(days=d_off)
                    sr, _ = sunrise_sunset_for_local_date(ts, planets, loc, d_candidate)
                    if sr:
                        tid = tithi_idx(ts.from_datetime(sr.astimezone(UTC)), earth, sun, moon)
                        if tid == 1: return d_candidate
    return date(year, 4, 1)

def samvatsara_for_date(d: date, new_year_dates: Dict[int, date]) -> str:
    y = d.year
    ny = new_year_dates.get(y)
    sy = y if ny and d >= ny else (y - 1)
    return SAMVATSARA_NAMES[(sy - BASE_SAMVATSARA_YEAR) % 60]

def month_day_numbers_solar(earth, sun, ts, planets, loc, start_d, end_d, lang):
    back_days = 45
    t0 = UTC.localize(datetime.combine(start_d - timedelta(days=back_days), time(0,0)))
    t1 = UTC.localize(datetime.combine(end_d + timedelta(days=15), time(0,0)))
    
    def f_rasi(t): return solar_rasi_idx(t, earth, sun)
    f_rasi.step_days = DISCRETE_STEP_DAYS
    
    ingress_times, rasi_values = precompute_discrete(ts, t0, t1, f_rasi)
    month_starts = {} 
    
    for t_ing, r_val in zip(ingress_times, rasi_values):
        tz = pytz.timezone(loc.tz)
        dt_local = t_ing.astimezone(tz)
        d_civil = dt_local.date()
        sr, ss = sunrise_sunset_for_local_date(ts, planets, loc, d_civil)
        if ss and dt_local < ss: month_starts[d_civil] = r_val
        else: month_starts[d_civil + timedelta(days=1)] = r_val

    current_mi = -1
    last_start_date = start_d - timedelta(days=back_days)
    sorted_starts = sorted(month_starts.keys())
    found_start = False
    for s_date in sorted_starts:
        if s_date <= start_d:
            current_mi = month_starts[s_date]
            last_start_date = s_date
            found_start = True
        else: break
            
    if not found_start:
        t_check = UTC.localize(datetime.combine(start_d, time(6,0)))
        current_mi = int(solar_rasi_idx(ts.from_datetime(t_check), earth, sun))
        last_start_date = start_d
    
    day_count = (start_d - last_start_date).days + 1
    res = {}
    d = start_d
    while d <= end_d:
        if d in month_starts:
            current_mi = month_starts[d]
            day_count = 1
        res[d] = (solar_month_name(current_mi, lang), day_count, rasi_name(current_mi, lang), current_mi)
        d += timedelta(days=1)
        day_count += 1
    return res

def get_lunar_month_map(earth, sun, moon, ts, planets, loc, start_d, end_d, lang):
    # Search range for lunar months
    back_days = 60
    t0 = UTC.localize(datetime.combine(start_d - timedelta(days=back_days), time(0,0)))
    t1 = UTC.localize(datetime.combine(end_d + timedelta(days=30), time(0,0)))
    
    # 1. Find all Tithi 1 Starts (New Moon Ends)
    def f_tithi(t): return tithi_idx(t, earth, sun, moon)
    f_tithi.step_days = DISCRETE_STEP_DAYS
    changes, values = precompute_discrete(ts, t0, t1, f_tithi)
    
    # Store (timestamp, new_month_index)
    month_transitions = []
    
    for i, t in enumerate(changes):
        if values[i] == 1: # Tithi became 1 (Prathama)
            # Determine Month Name based on Solar Rasi at this moment + 1
            # FIX: t is already datetime, so use it directly
            s_idx = solar_rasi_idx(ts.from_datetime(t), earth, sun)
            lunar_month_idx = (s_idx + 1) % 12
            month_transitions.append((t, lunar_month_idx))
    
    month_transitions.sort(key=lambda x: x[0])
    
    res = {}
    d = start_d
    tz = pytz.timezone(loc.tz)
    
    # Pre-calculate state for the first day
    # Find the latest transition that happened BEFORE the sunrise of start_d
    first_sr, _ = sunrise_sunset_for_local_date(ts, planets, loc, start_d)
    
    # Fallback if no transition found (rare)
    cur_mi = 0 
    
    while d <= end_d:
        sr, _ = sunrise_sunset_for_local_date(ts, planets, loc, d)
        
        # If we have sunrise, check which month applies
        if sr:
            # Find the latest transition strictly before sunrise
            best_idx = -1
            for i, (t_trans, m_idx) in enumerate(month_transitions):
                # FIX: t_trans is already datetime (UTC aware)
                if t_trans < sr.astimezone(UTC):
                    best_idx = i
                else:
                    break
            
            if best_idx != -1:
                cur_mi = month_transitions[best_idx][1]
        
        res[d] = (lunar_month_name(cur_mi, lang), cur_mi)
        d += timedelta(days=1)
        
    return res

def build_calendar(loc, ts, planets, earth, sun, moon, t_ch, t_v, n_ch, n_v):
    tz = pytz.timezone(loc.tz)
    start_d = datetime.now(tz).date()
    end_d = start_d + timedelta(days=DAYS_AHEAD)
    
    years = range(start_d.year-1, end_d.year+2)
    ny_dates = {}
    for y in years:
        if loc.style == "TAMIL": ny_dates[y] = puthandu_civil_date(y, ts, planets, earth, sun, loc)
        else: ny_dates[y] = ugadi_civil_date(y, ts, planets, earth, sun, moon, loc)
        
    sunr, suns = sun_events_range(ts, planets, loc, start_d, end_d)
    
    s_info = {}
    l_info = {}
    if loc.style == "TAMIL": 
        s_info = month_day_numbers_solar(earth, sun, ts, planets, loc, start_d, end_d, loc.lang)
    else: 
        # UPDATED: Pass planets/loc to new lunar logic
        l_info = get_lunar_month_map(earth, sun, moon, ts, planets, loc, start_d, end_d, loc.lang)
        
    cal = Calendar()
    
    seen_uids: Set[str] = set()

    d = start_d
    while d < end_d:
        sr = sunr.get(d)
        ss = suns.get(d)
        nsr = sunr.get(d+timedelta(days=1))
        
        if sr and ss and nsr:
            mr = calculate_moonrise(d, loc, ts, planets)
            s_d = s_info.get(d)
            l_d = l_info.get(d)
            desc, title, festivals, vratam_events = daily_panchangam(loc, d, s_d, l_d, sr, ss, mr, nsr, t_ch, t_v, n_ch, n_v, ny_dates, earth, sun, moon, ts)
            
            # 1. Daily Panchangam (All Day)
            uid_daily = f"{loc.key}-{d.isoformat()}@panchangam"
            if uid_daily not in seen_uids:
                e = Event()
                e.name = title
                e.description = desc
                e.begin = d.isoformat()
                e.make_all_day()
                e.categories = {"PANCHANGAM"}
                e.uid = uid_daily
                cal.events.add(e)
                seen_uids.add(uid_daily)
            
            # 2. Add Full-Day Festivals (Rich Metadata)
            for item in festivals:
                uid_fest = f"{loc.key}-{d.isoformat()}-{item.uid_suffix}@festival"
                if uid_fest not in seen_uids:
                    fe = Event()
                    fe.name = item.name
                    fe.begin = d.isoformat()
                    fe.make_all_day()
                    fe.categories = {"FESTIVAL"}
                    fe.description = item.desc
                    fe.uid = uid_fest
                    
                    alarm = DisplayAlarm(trigger=timedelta(days=-1))
                    alarm.description = f"Reminder: {item.name.replace('🎉 ', '')} is tomorrow!"
                    fe.alarms.append(alarm)
                    cal.events.add(fe)
                    seen_uids.add(uid_fest)

            # 3. Add Timed Vratam Events (Deduplicated)
            for v_event in vratam_events:
                v_start_str = v_event.start.astimezone(tz).strftime("%Y%m%d%H%M")
                uid_vrat = f"{loc.key}-{v_start_str}-{v_event.name.replace(' ','')}@vratam"
                
                if uid_vrat not in seen_uids:
                    fe = Event()
                    fe.name = f"⏳ {v_event.name}"
                    fe.begin = v_event.start.astimezone(tz)
                    fe.end = v_event.end.astimezone(tz)
                    fe.categories = {"VRATAM"}
                    fe.description = f"Astronomical duration of {v_event.name}."
                    fe.uid = uid_vrat
                    
                    alarm = DisplayAlarm(trigger=timedelta(days=-1))
                    alarm.description = f"Reminder: {v_event.name} is tomorrow!"
                    fe.alarms.append(alarm)
                    cal.events.add(fe)
                    seen_uids.add(uid_vrat)

        d += timedelta(days=1)
        
    if os.path.exists(MANUAL_FILE):
        try:
            with open(MANUAL_FILE, "r") as f:
                data = json.loads(f.read())
                for item in data:
                    uid_manual = f"{loc.key}-{item.get('date', 'nodate')}-{item['name']}@manual"
                    if uid_manual not in seen_uids:
                        e = Event()
                        e.name = f"🔹 {item['name']}"
                        if "date" in item:
                            e.begin = item['date']
                            e.make_all_day()
                            e.uid = uid_manual
                        cal.events.add(e)
                        seen_uids.add(uid_manual)
        except: pass
        
    return cal

def main():
    ts = load.timescale()
    planets = load("de421.bsp")
    earth, moon, sun = planets["earth"], planets["moon"], planets["sun"]
    
    now = datetime.now(UTC)
    t0 = now - timedelta(days=3)
    t1 = now + timedelta(days=DAYS_AHEAD+50)
    
    def ft(t): return tithi_idx(t, earth, sun, moon)
    ft.step_days = DISCRETE_STEP_DAYS
    tch, tv = precompute_discrete(ts, t0, t1, ft)
    
    def fn(t): return nak_idx(t, earth, moon)
    fn.step_days = DISCRETE_STEP_DAYS
    nch, nv = precompute_discrete(ts, t0, t1, fn)
    
    for loc in LOCATIONS:
        print(f"Generating {loc.out_ics} ({loc.style}, {loc.lang})...")
        cal = build_calendar(loc, ts, planets, earth, sun, moon, tch, tv, nch, nv)
        with open(loc.out_ics, "w", encoding="utf-8") as f:
            f.write(cal.serialize())
            
if __name__ == "__main__":
    main()