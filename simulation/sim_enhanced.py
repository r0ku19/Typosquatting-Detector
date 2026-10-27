"""Trace the backend enhanced-Levenshtein scorer by hostname segment."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

try:
    from backend import app
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from backend import app


def trace_segment(
    source: str, target: str, segment_name: str
) -> tuple[float, list[tuple[str, str, str, float, float]]]:
    """Reproduce the backend DP path for one weighted hostname segment."""
    multiplier = app.SEGMENT_MULTIPLIERS[segment_name]
    matrix = [
        [0.0 for _ in range(len(target) + 1)]
        for _ in range(len(source) + 1)
    ]
    operations: list[list[Optional[tuple[str, str, str, float]]]] = [
        [None for _ in range(len(target) + 1)]
        for _ in range(len(source) + 1)
    ]

    for row in range(1, len(source) + 1):
        matrix[row][0] = matrix[row - 1][0] + app.DELETION_COST * multiplier
        operations[row][0] = ("DELETE", source[row - 1], "-", app.DELETION_COST)
    for column in range(1, len(target) + 1):
        matrix[0][column] = matrix[0][column - 1] + app.INSERT_COST * multiplier
        operations[0][column] = ("INSERT", "-", target[column - 1], app.INSERT_COST)

    for row in range(1, len(source) + 1):
        for column in range(1, len(target) + 1):
            replacement_cost = app.substitution_cost(
                source[row - 1], target[column - 1]
            )
            choices = [
                (
                    matrix[row - 1][column - 1]
                    + replacement_cost * multiplier,
                    "MATCH" if replacement_cost == 0.0 else "SUBST",
                    source[row - 1],
                    target[column - 1],
                    replacement_cost,
                ),
                (
                    matrix[row - 1][column] + app.DELETION_COST * multiplier,
                    "DELETE",
                    source[row - 1],
                    "-",
                    app.DELETION_COST,
                ),
                (
                    matrix[row][column - 1] + app.INSERT_COST * multiplier,
                    "INSERT",
                    "-",
                    target[column - 1],
                    app.INSERT_COST,
                ),
            ]
            best = min(choices, key=lambda choice: choice[0])
            matrix[row][column] = best[0]
            operations[row][column] = best[1:]

            if (
                row > 1
                and column > 1
                and source[row - 1] == target[column - 2]
                and source[row - 2] == target[column - 1]
            ):
                transposition = (
                    matrix[row - 2][column - 2]
                    + app.TRANSPOSITION_COST * multiplier
                )
                if transposition < matrix[row][column]:
                    matrix[row][column] = transposition
                    operations[row][column] = (
                        "TRANSPOSE",
                        source[row - 2 : row],
                        target[column - 2 : column],
                        app.TRANSPOSITION_COST,
                    )

    path: list[tuple[str, str, str, float, float]] = []
    row, column = len(source), len(target)
    while row or column:
        operation = operations[row][column]
        if operation is None:
            raise RuntimeError("Unable to reconstruct the optimal edit path.")
        name, source_chars, target_chars, cost = operation
        step = 2 if name == "TRANSPOSE" else 1
        path.append(
            (
                target_chars,
                source_chars,
                name,
                cost * multiplier,
                matrix[row][column],
            )
        )
        row -= 0 if name == "INSERT" else step
        column -= 0 if name == "DELETE" else step

    path.reverse()
    return matrix[-1][-1], path


def print_trace(target: str, candidate: str) -> None:
    target_host = app.normalize_url_or_host(target)
    candidate_host = app.normalize_url_or_host(candidate)
    target_segments = app.split_host_segments(target_host)
    candidate_segments = app.split_host_segments(candidate_host)

    print(f"[Target: {target_host} | Candidate: {candidate_host}]")
    for source, reference, segment_name in (
        (candidate_segments.subdomain, target_segments.subdomain, "subdomain"),
        (candidate_segments.primary, target_segments.primary, "primary"),
        (candidate_segments.tld, target_segments.tld, "tld"),
    ):
        if not source and not reference:
            continue
        distance, path = trace_segment(source, reference, segment_name)
        print(
            f"SEGMENT={segment_name} SOURCE={source!r} TARGET={reference!r} "
            f"DISTANCE={distance:.2f}"
        )
        for iteration, (target_char, source_char, operation, cost, current_dist) in enumerate(
            path, start=1
        ):
            print(
                f"Iter {iteration:03d} | segment={segment_name} "
                f"| char_t={target_char} | char_s={source_char} "
                f"| op={operation} | cost={cost:.2f} "
                f"| current_dist={current_dist:.2f}"
            )

    similarity, total_distance = app.score_host_pair(candidate_host, target_host)
    verdict = (
        "HIGH_RISK_TYPOSQUAT"
        if similarity >= app.TYPOQUAT_THRESHOLD and candidate_host != target_host
        else "SAFE"
    )
    print(
        f"TOTAL Raw_Dist={total_distance:.2f} Similarity={similarity:.4f} "
        f"VERDICT={verdict}"
    )


def main() -> None:
    pairs = [
        ("dfa.gov.ph", "dfa.fov.ph"),
        ("dfa.gov.ph", "dfa.g0v.ph"),
        ("dfa.gov.ph", "dffa.gov.ph"),
        ("dfa.gov.ph", "df.gov.ph"),
        ("dfa.gov.ph", "dff.gov.ph"),
    ]
    if len(sys.argv) >= 3:
        pairs = [(sys.argv[1], sys.argv[2])]

    for index, (target, candidate) in enumerate(pairs):
        if index:
            print()
        print_trace(target, candidate)


if __name__ == "__main__":
    main()
