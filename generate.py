import json
import os
from datetime import datetime, timedelta
import pytz
from ics import Calendar, Event
from skyfield.api import load
from skyfield.searchlib import find_discrete

# --- CONFIGURATION ---
# Stuttgart Coordinates (used for general locality, though Tithis are geocentric)
CITY_LAT = 48.7758
CITY_LON = 9.1829
TIMEZONE = 'Europe/Berlin'
ICS_FILENAME = 'stuttgart_calendar.ics'
MANUAL_FILE = 'manual_events.json'

# Target Tithis (Keys are 1-30)
# 1-15: Shukla Paksha (Waxing)
# 16-30: Krishna Paksha (Waning)
TARGET_TITHIS = {
    4: "Chaturthi (Shukla)",
    6: "Shashti (Shukla)",
    11: "Ekadasi (Shukla)",
    19: "Sankata Hara Chaturthi", # Krishna Chaturthi (15+4)
    26: "Ekadasi (Krishna)"       # Krishna Ekadasi (15+11)
}

def get_tithi_index(t, earth, moon, sun):
    """Returns Tithi index (1-30) for a given time."""
    e = earth.at(t)
    _, slon, _ = e.observe(sun).apparent().ecliptic_latlon()
    _, mlon, _ = e.observe(moon).apparent().ecliptic_latlon()
    phase = (mlon.degrees - slon.degrees) % 360
    return int(phase / 12) + 1

def add_manual_events(cal, tz):
    if not os.path.exists(MANUAL_FILE):
        return
    try:
        with open(MANUAL_FILE, 'r') as f:
            data = json.load(f)
        for item in data:
            e = Event()
            e.name = f"🔹 {item['name']}" # Visual marker for manual events
            e.description = item.get('description', '')
            
            if 'date' in item: # All-day
                e.begin = item['date']
                e.make_all_day()
                e.uid = f"{item['date']}-{item['name'].replace(' ', '')}@manual"
            elif 'start' in item and 'end' in item: # Timed
                s = datetime.strptime(item['start'], '%Y-%m-%d %H:%M')
                en = datetime.strptime(item['end'], '%Y-%m-%d %H:%M')
                e.begin = tz.localize(s)
                e.end = tz.localize(en)
                e.uid = f"{item['start']}-{item['name'].replace(' ', '')}@manual"
            cal.events.add(e)
    except Exception as err:
        print(f"Manual event error: {err}")

def main():
    # 1. Setup Astronomy
    print("Loading Ephemeris...")
    ts = load.timescale()
    planets = load('de421.bsp') # Downloads NASA data
    earth, moon, sun = planets['earth'], planets['moon'], planets['sun']

    # Define the search function for Skyfield
    def tithi_at_time(t):
        e = earth.at(t)
        _, slon, _ = e.observe(sun).apparent().ecliptic_latlon()
        _, mlon, _ = e.observe(moon).apparent().ecliptic_latlon()
        return (mlon.degrees - slon.degrees) % 360 // 12

    tithi_at_time.step_days = 0.04 # Step size for solver

    # 2. Time Range (Now to +2 Years)
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    t0 = ts.from_datetime(now)
    t1 = ts.from_datetime(now + timedelta(days=730))

    # 3. Solve for Transitions
    print("Calculating exact Tithi timings...")
    # find_discrete returns times when the value changes
    times, values = find_discrete(t0, t1, tithi_at_time)

    cal = Calendar()
    
    # 4. Process Astro Events
    # values[i] is the Tithi index starting at times[i]
    # times[i+1] is when that Tithi ends
    for i in range(len(times) - 1):
        tithi_idx = int(values[i]) + 1 # Convert 0-29 to 1-30
        
        if tithi_idx in TARGET_TITHIS:
            start_dt = times[i].astimezone(tz)
            end_dt = times[i+1].astimezone(tz)
            
            e = Event()
            e.name = TARGET_TITHIS[tithi_idx]
            e.begin = start_dt
            e.end = end_dt
            e.description = "Exact Astronomical Duration (Stuttgart)"
            e.uid = f"{start_dt.strftime('%Y%m%d%H%M')}-{tithi_idx}@astro"
            cal.events.add(e)

    # 5. Merge Manual
    add_manual_events(cal, tz)

    # 6. Save
    with open(ICS_FILENAME, 'w') as f:
        f.writelines(cal.serialize_iter())
    print(f"Calendar generated with {len(cal.events)} events.")

if __name__ == "__main__":
    main()
