# flight_tracker

Tracks LAX → ICN (Seoul) round-trip flight prices for April 2027 and emails
you the cheapest fare found, several times a day.

## How it works

- `scripts/track_flight.py` builds every (departure date, return date) pair
  in April 2027 where the trip is 14-16 days long and the return lands on a
  Saturday or Sunday (27 combinations for April 2027) — no fixed departure
  weekday, so it covers the whole "leave whenever, ~2 weeks, back on a
  weekend" space and finds whichever combination is actually cheapest.
- Each run only checks a rotating slice of 4 of those combinations (to stay
  within API budget — see below), appends results to
  `data/price_history.json`, and emails a summary: cheapest fare this
  check, cheapest fare found today, and the cheapest fare ever recorded —
  flagging a new all-time low when one is found. Because the "ever
  recorded" figure is tracked across every combination as the rotation
  cycles through, it converges on the true cheapest option over time
  (roughly once every ~7 runs, or ~3.5 days at the default schedule).
- `.github/workflows/flight_price_tracker.yml` runs this on a schedule
  (twice a day, 12 hours apart) via GitHub Actions, and commits the updated
  history file back to the repo.
- That's 4 dates × 2 runs/day = 8 searches/day (~240/month), comfortably
  within SerpApi's free tier (250 searches/month).
- Only itineraries Google Flights lists as including a free checked bag are
  considered — this is a best-effort match on the airline-supplied
  `extensions` text (e.g. "1st checked bag included"), not a guarantee, so
  always double-check baggage allowance at checkout before booking.

## Setup

Add these repository secrets under **Settings → Secrets and variables →
Actions**:

| Secret | Description |
| --- | --- |
| `SERPAPI_KEY` | API key from [serpapi.com](https://serpapi.com) (free tier: 250 searches/month, which the default schedule/rotation is tuned to fit) |
| `EMAIL_ADDRESS` | Gmail address to send the report from |
| `EMAIL_APP_PASSWORD` | A [Gmail App Password](https://myaccount.google.com/apppasswords) for that address (not your normal password) |
| `EMAIL_TO` | (optional) Address to send reports to — defaults to `EMAIL_ADDRESS` |

Optional environment overrides (edit the workflow or script defaults):

- `ORIGIN` (default `LAX`)
- `DESTINATION` (default `ICN`)
- `MIN_TRIP_DAYS` / `MAX_TRIP_DAYS` (default `14` / `16`)

## Running manually

```bash
pip install -r requirements.txt
export SERPAPI_KEY=...
export EMAIL_ADDRESS=...
export EMAIL_APP_PASSWORD=...
python scripts/track_flight.py
```

You can also trigger a run on demand from the **Actions** tab via
"Run workflow" (workflow_dispatch).
