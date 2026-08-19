# flight_tracker

Tracks LAX → ICN (Seoul) round-trip flight prices for April 2027 and emails
you the cheapest fare found, several times a day.

## How it works

- `scripts/track_flight.py` queries [SerpApi's Google Flights engine](https://serpapi.com/google-flights-api)
  for a rotating slice of candidate departure dates across April 2027 (each
  paired with a ~10 day return), finds the cheapest fare among them, and
  appends the results to `data/price_history.json`.
- It then emails a summary: cheapest fare this check, cheapest fare found
  today, and the cheapest fare ever recorded — flagging a new all-time low
  when one is found.
- `.github/workflows/flight_price_tracker.yml` runs this on a schedule
  (twice a day, 12 hours apart) via GitHub Actions, and commits the updated
  history file back to the repo.
- To stay within SerpApi's free tier (250 searches/month), each run only
  checks `DATES_PER_RUN` (4) of the 7 candidate dates, rotating by time of
  day — so all 7 dates still get checked daily, at 2 runs/day × 4 dates =
  8 searches/day (~240/month).

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
