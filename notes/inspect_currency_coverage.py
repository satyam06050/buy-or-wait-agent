"""Throwaway Stage 1 currency-coverage inspection; not final pipeline code.

Usage from the repository root:
    python3 notes/inspect_currency_coverage.py

The participant schema says request amounts are already in each user's
home_currency, so this audit checks event rows whose currency differs from
that home currency. It performs exact-key presence checks only; it does not
convert amounts or invent fallback rates.
"""
from collections import defaultdict
from pathlib import Path
import csv

DATASET = Path(__file__).resolve().parents[1] / "dataset"


def read(name):
    with (DATASET / name).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    profiles = {row["user_id"]: row for row in read("financial_profiles.csv")}
    rates = read("exchange_rates.csv")
    rate_keys = {
        (row["rate_date"], row["from_currency"], row["to_currency"])
        for row in rates
    }

    foreign = []
    for event in read("financial_events.csv"):
        home = profiles[event["user_id"]]["home_currency"]
        if event["currency"] and event["currency"] != home:
            key = (event["settlement_date"], event["currency"], home)
            foreign.append((event, key, key in rate_keys))

    gaps = [(event, key) for event, key, present in foreign if not present]
    print(f"foreign_events={len(foreign)} covered={len(foreign) - len(gaps)} gaps={len(gaps)}")
    for event, key in gaps:
        print(
            f"GAP event_id={event['event_id']} user_id={event['user_id']} "
            f"settlement_date={event['settlement_date']} key={key}"
        )

    seen = set()
    print("first_distinct_covered_keys:")
    for event, key, present in foreign:
        if present and key not in seen:
            seen.add(key)
            print(f"{event['event_id']} key={key}")
            if len(seen) == 20:
                break


if __name__ == "__main__":
    main()
