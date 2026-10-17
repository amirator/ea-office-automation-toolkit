# Sample data (fictional)

**Every file in this folder is SAMPLE / DEMO DATA.** "Demo Holding Co.", its people, trips,
expenses, calendars and KPIs are invented to show what the toolkit does. They are not taken
from, and do not describe, any real company or person. Email addresses use the reserved
`.example` domain. FX rates are fixed illustrative values, not live rates.

| File | Used by | What it contains |
|---|---|---|
| `attendees.csv` | slots / agenda | 5 attendees in Jeddah, Riyadh, Dubai, London and Bengaluru with local hours and work weeks |
| `busy.csv` | slots / agenda | Busy calendar blocks (ISO 8601 with UTC offsets) |
| `claire_bennett.ics` | slots / agenda | An iCalendar export, showing `.ics` input (TZID and UTC times) |
| `meeting_brief.json` | agenda | Title, chair, purpose and timed agenda items with owners and pre-reads |
| `expenses.csv` | expenses | 21 expense lines over 3 trips in SAR, AED, GBP and USD |
| `trips.csv` | expenses | Trip register with budgets in SAR |
| `fx_rates.csv` | expenses | SAR per unit of each currency (illustrative) |
| `policy_limits.csv` | expenses | Per-category limits (per night / day / ticket / item) |
| `kpis.csv` | kpi | 8 KPIs x 6 months (Apr-Sep 2026) with targets, direction and tolerance |

Lines starting with `#` are comments and are skipped by the loaders, so each file can carry its own
sample-data label.
