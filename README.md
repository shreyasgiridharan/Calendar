# Tamil Panchangam for Stuttgart

Hi! This is a project I built to solve a specific problem: keeping track of Tamil festivals and Tithi timings accurately while living in **Stuttgart, Germany**.

Most calendars we get from home are calculated for India time (IST). Simply subtracting 3.5 or 4.5 hours doesn't always work because Tithis (lunar days) are based on the angle between the Sun and Moon, not just the clock.

This tool does the heavy lifting to calculate the **exact astronomical windows** for fasting and rituals, customized specifically for Stuttgart’s location and time zone.

---

## Why use this?

### 1. It’s actually accurate for Germany
Instead of using approximations, this tool connects to NASA's planetary data (using a library called `skyfield`). It calculates the exact minute a Tithi begins and ends based on where we are. It handles the switch between Winter time (CET) and Summer time (CEST) automatically, so you don't have to do the math in your head.

### 2. It tracks the important stuff
I designed this to track three main types of events:
* **Fasting/Recurring Days:** It automatically finds the start and end times for **Ekadashi, Pradosham, Sankatahara Chaturthi, and Shashti**.
* **Solar Events:** It knows exactly when the Sun enters a new Rashi (Zodiac), which is crucial for dates like **Pongal** and **Tamil New Year (Puthandu)**.
* **Major Festivals:** I've included a list of major festivals for 2026, like **Deepavali, Thai Pusam, and Maha Shivaratri**.

### 3. It works with your phone
The output is a standard `.ics` file. This means you can subscribe to it using Google Calendar, Apple Calendar (on iPhone/Mac), or Outlook, and the events will just show up alongside your work meetings and personal appointments.

---

## How to use it

### The Easy Way (Subscribe)
You don't need to run any code if you just want the calendar. You can subscribe to the live calendar link below. This will keep your phone updated automatically.

**📅 Subscription Link for Germany:**
`https://shreyasgiridharan.github.io/Calendar/Calendar-Stuttgart.ics`

**📅 Subscription Link for India:**
`https://shreyasgiridharan.github.io/Calendar/Calendar-India.ics`

### The "Do It Yourself" Way
If you prefer to run the script yourself or want to modify the code, here is how you get it running.

**Prerequisites**
You'll need Python 3.8 or higher, plus a few libraries to handle the astronomy and timezone math:
* `skyfield` (for the planetary data)
* `ics` (to make the calendar file)
* `pytz` (for timezone handling)

**Running the generator**
Just run the script, and it will generate the `.ics` files locally on your machine.

---

## Adding Custom Events
If you run the code yourself, you can add your own personal events (like family pujas or birthdays) by creating a `manual_events.json` file. The script will weave these into the final calendar.

Here is an example of how to format that file:

```json
[
  {
    "name": "House Warming Puja",
    "start": "2026-08-15 10:30",
    "end": "2026-08-15 12:00",
    "timezone": "Europe/Berlin",
    "description": "Don't forget the flowers!"
  }
]

---

## Support the Project
If you find this calendar useful or like what I'm doing here, please consider starring this repo! ⭐ It helps others find the project and motivates me to keep improving it.