#!/usr/bin/env python3
"""Evaluate overall and per-mutation classification metrics from a results CSV."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from typing import Iterable


REQUIRED_COLUMNS = {
    "actual_label",
    "predicted_label",
    "variant_type",
}


def as_label(value: str, column: str, row_number: int) -> int:
    try:
        label = int(value)
    except ValueError as exc:
        raise ValueError(
            f"Row {row_number}: {column} must be 0 or 1, got {value!r}"
        ) from exc

    if label not in {0, 1}:
        raise ValueError(
            f"Row {row_number}: {column} must be 0 or 1, got {label!r}"
        )

    return label


def calculate_metrics(rows: Iterable[dict[str, int]]) -> dict[str, int | float]:
    tp = tn = fp = fn = 0

    for row in rows:
        actual = row["actual_label"]
        predicted = row["predicted_label"]

        if actual == 1 and predicted == 1:
            tp += 1
        elif actual == 0 and predicted == 0:
            tn += 1
        elif actual == 0 and predicted == 1:
            fp += 1
        elif actual == 1 and predicted == 0:
            fn += 1

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )

    return {
        "TP": tp,
        "TN": tn,
        "FP": fp,
        "FN": fn,
        "Precision": precision,
        "Recall": recall,
        "F1-Score": f1,
    }


def load_rows(path: Path) -> dict[str, list[dict[str, int]]]:
    with path.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)

        if reader.fieldnames is None:
            raise ValueError("CSV has no header row.")

        missing = REQUIRED_COLUMNS - set(reader.fieldnames)
        if missing:
            raise ValueError(
                f"CSV is missing required columns: {', '.join(sorted(missing))}"
            )

        grouped: dict[str, list[dict[str, int]]] = defaultdict(list)

        for row_number, row in enumerate(reader, start=2):
            variant = (row["variant_type"] or "").strip() or "unknown"
            grouped[variant].append(
                {
                    "actual_label": as_label(
                        row["actual_label"], "actual_label", row_number
                    ),
                    "predicted_label": as_label(
                        row["predicted_label"], "predicted_label", row_number
                    ),
                }
            )

    return grouped


def print_metrics(scope: str, metrics: dict[str, int | float]) -> None:
    print(
        f"{scope:<28}"
        f"{metrics['TP']:>6}"
        f"{metrics['TN']:>6}"
        f"{metrics['FP']:>6}"
        f"{metrics['FN']:>6}"
        f"{metrics['Precision']:>11.4f}"
        f"{metrics['Recall']:>9.4f}"
        f"{metrics['F1-Score']:>10.4f}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Calculate overall and per-mutation metrics from a result CSV."
    )
    parser.add_argument("csv_path", type=Path)
    args = parser.parse_args()

    grouped = load_rows(args.csv_path)
    all_rows = [
        row
        for variant_rows in grouped.values()
        for row in variant_rows
    ]

    print(f"Input: {args.csv_path}")
    print(
        f"\n{'Scope':<28}"
        f"{'TP':>6}"
        f"{'TN':>6}"
        f"{'FP':>6}"
        f"{'FN':>6}"
        f"{'Precision':>11}"
        f"{'Recall':>9}"
        f"{'F1-Score':>10}"
    )
    print("-" * 100)

    print_metrics("OVERALL", calculate_metrics(all_rows))

    for variant in sorted(grouped):
        print_metrics(
            variant,
            calculate_metrics(grouped[variant]),
        )


if __name__ == "__main__":
    main()