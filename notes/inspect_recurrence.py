"""Throwaway Stage 1 inspection; not imported by the final pipeline.

Usage from the repository root:
    python3 notes/inspect_recurrence.py

It only reports observations from financial_events.csv: repeated
(user_id, category, description) groups, date deltas, and linked lifecycles.
It intentionally does not forecast or classify events.
"""
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
import csv

DATASET = Path(__file__).resolve().parents[1] / "dataset"


def read_events():
    with (DATASET / "financial_events.csv").open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    events = read_events()
    groups = defaultdict(list)
    for event in events:
        key = (event["user_id"], event["category"], event["description"])
        groups[key].append(event)

    deltas = Counter()
    examples = defaultdict(list)
    repeated = 0
    for key, rows in groups.items():
        ordered = sorted(rows, key=lambda row: (row["event_date"], row["event_id"]))
        if len(ordered) < 2:
            continue
        repeated += 1
        for earlier, later in zip(ordered, ordered[1:]):
            interval = (date.fromisoformat(later["event_date"]) - date.fromisoformat(earlier["event_date"])).days
            deltas[interval] += 1
            if len(examples[interval]) < 4:
                examples[interval].append(
                    (earlier["event_id"], later["event_id"], key[0], key[2])
                )

    print(f"events={len(events)} groups={len(groups)} repeated_groups={repeated}")
    print("date_delta_days=count")
    for interval, count in deltas.most_common():
        print(f"{interval}={count} examples={examples[interval]}")

    linked = [event for event in events if event["linked_event_id"]]
    targets = sorted({event["linked_event_id"] for event in linked})
    print(f"linked_rows={len(linked)} unique_link_targets={len(targets)}")
    for target in targets:
        chain = [event for event in events if event["event_id"] == target or event["linked_event_id"] == target]
        compact = "; ".join(
            f"{event['event_id']}:{event['event_type']}:{event['status']}:{event['direction']}"
            for event in sorted(chain, key=lambda row: row["event_id"])
        )
        print(f"{target}: {compact}")


if __name__ == "__main__":
    main()
