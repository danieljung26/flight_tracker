#!/usr/bin/env python3
"""Check LAX -> ICN round-trip flight prices for April 2027 via SerpApi
(Google Flights engine), record them, and email the cheapest fare found.

Required environment variables:
    SERPAPI_KEY        API key from https://serpapi.com
    EMAIL_ADDRESS       Gmail address to send from
    EMAIL_APP_PASSWORD  Gmail app password (not your normal password)
    EMAIL_TO            Address to send the report to (defaults to EMAIL_ADDRESS)

Optional:
    ORIGIN              IATA code, default "LAX"
    DESTINATION         IATA code, default "ICN"
    MIN_TRIP_DAYS       Shortest trip length to consider, default 14
    MAX_TRIP_DAYS       Longest trip length to consider, default 16

Every April departure date is paired with every trip length in
[MIN_TRIP_DAYS, MAX_TRIP_DAYS] whose return date lands on a Saturday or
Sunday, and each run checks a rotating slice of that full candidate list —
so over time the "cheapest ever recorded" figure converges on the actual
cheapest weekend-returning ~2 week trip, not just one fixed weekday.
"""
import json
import os
import smtplib
import sys
import time
from datetime import date, datetime, timedelta, timezone
from email.mime.text import MIMEText
from pathlib import Path

import requests

SERPAPI_URL = "https://serpapi.com/search"
HISTORY_PATH = Path(__file__).resolve().parent.parent / "data" / "price_history.json"

ORIGIN = os.environ.get("ORIGIN", "LAX")
DESTINATION = os.environ.get("DESTINATION", "ICN")
MIN_TRIP_DAYS = int(os.environ.get("MIN_TRIP_DAYS", "14"))
MAX_TRIP_DAYS = int(os.environ.get("MAX_TRIP_DAYS", "16"))
YEAR = 2027

# SerpApi's free tier is capped at 250 searches/month. Checking every
# candidate every run would blow through that fast, so each run only checks
# a rotating slice — over enough runs, every candidate still gets checked.
DATES_PER_RUN = 4


def candidate_date_pairs():
    pairs = []
    for day in range(1, 31):
        depart = date(YEAR, 4, day)
        for length in range(MIN_TRIP_DAYS, MAX_TRIP_DAYS + 1):
            ret = depart + timedelta(days=length)
            if ret.weekday() in (5, 6):  # Saturday or Sunday
                pairs.append((depart.isoformat(), ret.isoformat()))
    return pairs


def dates_for_this_run(pairs, runs_so_far):
    offset = (runs_so_far * DATES_PER_RUN) % len(pairs)
    return [pairs[(offset + i) % len(pairs)] for i in range(DATES_PER_RUN)]


def fetch_price(api_key, depart_date, return_date):
    params = {
        "engine": "google_flights",
        "departure_id": ORIGIN,
        "arrival_id": DESTINATION,
        "outbound_date": depart_date,
        "return_date": return_date,
        "currency": "USD",
        "hl": "en",
        "type": "1",  # round trip
        "api_key": api_key,
    }
    resp = requests.get(SERPAPI_URL, params=params, timeout=60)
    resp.raise_for_status()
    payload = resp.json()

    prices = []
    for key in ("best_flights", "other_flights"):
        for flight in payload.get(key, []):
            if isinstance(flight.get("price"), (int, float)):
                prices.append(flight["price"])

    insights = payload.get("price_insights") or {}
    lowest_from_insights = insights.get("lowest_price")
    if isinstance(lowest_from_insights, (int, float)):
        prices.append(lowest_from_insights)

    if not prices:
        return None
    return min(prices)


def load_history():
    if HISTORY_PATH.exists():
        return json.loads(HISTORY_PATH.read_text())
    return {"runs": []}


def save_history(history):
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(history, indent=2))


def send_email(subject, body):
    email_address = os.environ["EMAIL_ADDRESS"]
    email_password = os.environ["EMAIL_APP_PASSWORD"]
    email_to = os.environ.get("EMAIL_TO") or email_address

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = email_address
    msg["To"] = email_to

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(email_address, email_password)
        server.send_message(msg)


def main():
    api_key = os.environ.get("SERPAPI_KEY")
    if not api_key:
        print("SERPAPI_KEY is not set", file=sys.stderr)
        sys.exit(1)

    history = load_history()
    all_pairs = candidate_date_pairs()
    this_run_pairs = dates_for_this_run(all_pairs, len(history["runs"]))

    results = []
    for depart_date, return_date in this_run_pairs:
        try:
            price = fetch_price(api_key, depart_date, return_date)
        except requests.RequestException as exc:
            print(f"Error fetching {depart_date}/{return_date}: {exc}", file=sys.stderr)
            price = None
        results.append(
            {"depart": depart_date, "return": return_date, "price": price}
        )
        time.sleep(1)  # be gentle on the API rate limit

    valid_results = [r for r in results if r["price"] is not None]
    cheapest_this_run = (
        min(valid_results, key=lambda r: r["price"]) if valid_results else None
    )

    run_timestamp = datetime.now(timezone.utc).isoformat()
    history["runs"].append(
        {
            "timestamp": run_timestamp,
            "origin": ORIGIN,
            "destination": DESTINATION,
            "results": results,
            "cheapest": cheapest_this_run,
        }
    )
    save_history(history)

    # All-time cheapest across every run ever recorded.
    past_cheapest = [run["cheapest"] for run in history["runs"] if run.get("cheapest")]
    all_time_cheapest = min(past_cheapest, key=lambda c: c["price"]) if past_cheapest else None

    # Cheapest seen so far today (UTC).
    today = date.today().isoformat()
    todays_prices = [
        run["cheapest"]
        for run in history["runs"]
        if run.get("cheapest") and run["timestamp"].startswith(today)
    ]
    todays_cheapest = min(todays_prices, key=lambda c: c["price"]) if todays_prices else None

    is_new_record = bool(
        cheapest_this_run
        and all_time_cheapest
        and all_time_cheapest["price"] == cheapest_this_run["price"]
    )

    lines = [
        f"{ORIGIN} -> {DESTINATION} round-trip, April {YEAR}",
        "",
    ]
    if cheapest_this_run:
        lines.append(
            f"Cheapest fare found THIS check: ${cheapest_this_run['price']:.0f}"
            f" (depart {cheapest_this_run['depart']}, return {cheapest_this_run['return']})"
        )
    else:
        lines.append("No prices could be fetched for this run's checked dates.")
    if todays_cheapest:
        lines.append(
            f"Cheapest fare found TODAY so far: ${todays_cheapest['price']:.0f}"
            f" (depart {todays_cheapest['depart']}, return {todays_cheapest['return']})"
        )
    if all_time_cheapest:
        lines.append(
            f"Cheapest fare ever recorded: ${all_time_cheapest['price']:.0f}"
            f" (depart {all_time_cheapest['depart']}, return {all_time_cheapest['return']})"
        )
    lines.append("")
    lines.append("All dates checked this run:")
    for r in sorted(results, key=lambda r: (r["price"] is None, r["price"])):
        price_str = f"${r['price']:.0f}" if r["price"] is not None else "N/A"
        lines.append(f"  depart {r['depart']} / return {r['return']}: {price_str}")

    if is_new_record:
        lines.insert(0, "*** NEW ALL-TIME LOW PRICE ***")
        lines.insert(1, "")

    body = "\n".join(lines)
    subject_prefix = "[NEW LOW] " if is_new_record else ""
    if cheapest_this_run:
        subject = (
            f"{subject_prefix}{ORIGIN}->{DESTINATION} April {YEAR}: "
            f"${cheapest_this_run['price']:.0f} cheapest right now"
        )
    else:
        subject = f"{ORIGIN}->{DESTINATION} April {YEAR}: no prices found this check"

    if os.environ.get("EMAIL_ADDRESS") and os.environ.get("EMAIL_APP_PASSWORD"):
        send_email(subject, body)
        print("Email sent.")
    else:
        print("EMAIL_ADDRESS/EMAIL_APP_PASSWORD not set; skipping email.")

    print(body)


if __name__ == "__main__":
    main()
