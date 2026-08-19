# flight_tracker

Tracks LAX → ICN (Seoul) round-trip flight prices for April 2027 and emails
you the cheapest fare found, several times a day.

## How it works

- `scripts/track_flight.py` queries [SerpApi's Google Flights engine](https://serpapi.com/google-flights-api)
  for a spread of candidate departure dates across April 2027 (each paired
  with a ~10 day return), finds the cheapest fare among them, and appends
  the results to `data/price_history.json`.
- It then emails a summary: cheapest fare this check, cheapest fare found
  today, and the cheapest fare ever recorded — flagging a new all-time low
  when one is found.
- `.github/workflows/flight_price_tracker.yml` runs this on a schedule
  (every 4 hours) via GitHub Actions, and commits the updated history file
  back to the repo.

## Setup

Add these repository secrets under **Settings → Secrets and variables →
Actions**:

| Secret | Description |
| --- | --- |
| `SERPAPI_KEY` | API key from [serpapi.com](https://serpapi.com) (free tier works for a few checks/month; a paid plan is needed for checking every 4 hours long-term) |
| `EMAIL_ADDRESS` | Gmail address to send the report from |
| `EMAIL_APP_PASSWORD` | A [Gmail App Password](https://myaccount.google.com/apppasswords) for that address (not your normal password) |
| `EMAIL_TO` | (optional) Address to send reports to — defaults to `EMAIL_ADDRESS` |

Optional environment overrides (edit the workflow or script defaults):

- `ORIGIN` (default `LAX`)
- `DESTINATION` (default `ICN`)
- `TRIP_LENGTH_DAYS` (default `10`)

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
