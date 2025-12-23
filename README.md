# Calendar

A high-precision Python tool that generates an `.ics` calendar file for **Tamil Hindu festivals and Tithis** specifically localized for **Stuttgart, Germany**. 

Unlike standard calendars, this tool calculates the **exact astronomical windows** (start and end times) for lunar phases (Tithis) using NASA-grade planetary data, ensuring your fasting and puja timings are accurate to the minute for your specific location.

---

## ✨ Features

### 1. Astronomical Precision
* **NASA Ephemerides:** Uses the `skyfield` library and `de421.bsp` (NASA JPL planetary data) for high-accuracy Sun and Moon tracking.
* **Geocentric Tithi Calculation:** Calculates the exact moment of Tithi transitions based on the 12° angular separation between the Sun and Moon.

### 2. Comprehensive Tamil Festival Support
The script tracks three distinct types of events:
* **Lunar Tithis:** Automatically identifies recurring days like **Ekadashi** (Shukla/Krishna), **Pradosham**, **Sankata Hara Chaturthi**, and **Shashti**.
* **Solar Events:** Detects Solar Sankrantis (Sun entering a new Rashi), specifically for **Pongal (Makara Sankranti)** and **Puthandu (Tamil New Year)**.
* **Calculated Festivals:** Includes a pre-mapped dictionary of 2026 major festivals from the Tamil calendar, such as **Deepavali**, **Thai Pusam**, **Soora Samharam**, and **Maha Shivaratri**.

### 3. Localized for Stuttgart
* **Timezone Awareness:** All astronomical UTC timestamps are automatically converted to **Europe/Berlin** time.
* **DST Handling:** Correctly handles the shift between Central European Time (CET) and Daylight Saving Time (CEST).
* **Location Based:** While Tithis are geocentric, the display times and specific festival dates are optimized for the Stuttgart geographic coordinates.

### 4. Smart ICS Output
* **Universal Compatibility:** Generates a standard `.ics` file compatible with **Google Calendar, Apple Calendar, and Outlook**.
* **Precise Durations:** Provides specific start/end times for fasting windows rather than just "all-day" blocks.
* **Automatic Categorization:** Differentiates between astronomical durations and cultural festivals in event descriptions.

---

## 🛠️ Installation & Setup

### Prerequisites
* Python 3.8+
* [Skyfield](https://rhodesmill.org/skyfield/)
* [ics.py](https://ics-py.readthedocs.io/)
* [pytz](https://pythonhosted.org/pytz/)

---

## Usage
Subscription : https://shreyasgiridharan.github.io/Calendar/stuttgart_calendar.ics

---

## Manual Events 
```bash
[
  {
    "name": "Kumbhabhishekam (All Day Example)",
    "date": "2026-05-20",
    "description": "Full day festival. Remember fruits."
  },
  {
    "name": "Special Puja (Timed Example)",
    "start": "2026-08-15 10:30",
    "end": "2026-08-15 12:00",
    "description": "Specific timings for the ritual."
  }
]

---
