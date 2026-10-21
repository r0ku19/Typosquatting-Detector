"""Generate synthetic typosquats and evaluate both thesis classifiers.

Run from the project root:
    .venv/bin/python generate_and_evaluate.py

The script uses the production host scorer from ``backend.app`` and the
baseline/proposed scorer helpers from ``backend.experiment``. It accepts
plain TXT domain lists and CSV files containing URLs or domains.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence

from backend import app
from backend.experiment import baseline_score, enhanced_score

SEED = 42
DEFAULT_ENHANCED_PARAMS = {
    "deletion": app.DELETION_COST,
    "substitution": app.SUBSTITUTION_COST,
    "visual": app.VISUAL_SUBSTITUTION_COST,
    "primary": app.SEGMENT_MULTIPLIERS["primary"],
    "tld": app.SEGMENT_MULTIPLIERS["tld"],
    "transposition": app.TRANSPOSITION_COST,
}
VISUAL_REPLACEMENTS = {
    "a": "4",
    "e": "3",
    "g": "9",
    "i": "1",
    "l": "1",
    "o": "0",
    "s": "5",
    "t": "7",
}


@dataclass(frozen=True)
class DatasetItem:
    host: str
    label: int
    source_domain: str
    variant_type: str


def load_domains(path: Path) -> list[str]:
    """Load and normalize hosts from a TXT or CSV input file."""
    if path.suffix.lower() == ".csv":
        with path.open(newline="", encoding="utf-8-sig") as file:
            values = [cell for row in csv.reader(file) for cell in row]
    else:
        values = path.read_text(encoding="utf-8").splitlines()

    domains = set()
    for value in values:
        normalized = app.normalize_url_or_host(value)
        if normalized and normalized not in {"domain", "url", "host"}:
            domains.add(normalized)
    return sorted(domains)


def _replace_primary(host: str, primary: str) -> str:
    segments = app.split_host_segments(host)
    labels = host.split(".")
    primary_index = len(labels) - len(segments.tld.split(".")) - 1
    if primary_index < 0 or not segments.primary:
        return host
    labels[primary_index] = primary
    return ".".join(labels)


def generate_variants(domain: str) -> list[tuple[str, str]]:
    """Return deterministic visual, transposition, omission, and insertion variants."""
    primary = app.split_host_segments(domain).primary
    if not primary:
        return []

    candidates: list[tuple[str, str]] = []
    visual_index = next(
        (index for index, char in enumerate(primary) if char in VISUAL_REPLACEMENTS),
        None,
    )
    if visual_index is not None:
        replacement = VISUAL_REPLACEMENTS[primary[visual_index]]
        candidates.append((
            _replace_primary(domain, primary[:visual_index] + replacement + primary[visual_index + 1:]),
            "visual_homoglyph",
        ))
    if len(primary) > 1:
        candidates.append((
            _replace_primary(domain, primary[1] + primary[0] + primary[2:]),
            "transposition",
        ))
        candidates.append((
            _replace_primary(domain, primary[:1] + primary[2:]),
            "omission",
        ))
    insertion_index = min(1, len(primary))
    candidates.append((
        _replace_primary(domain, primary[:insertion_index] + primary[insertion_index] + primary[insertion_index:]),
        "insertion",
    ))

    seen = {domain}
    variants = []
    for variant, variant_type in candidates:
        if variant not in seen:
            seen.add(variant)
            variants.append((variant, variant_type))
    return variants


def build_dataset(domains: Sequence[str]) -> list[DatasetItem]:
    items = [DatasetItem(domain, 0, domain, "legitimate") for domain in domains]
    for domain in domains:
        items.extend(
            DatasetItem(variant, 1, domain, variant_type)
            for variant, variant_type in generate_variants(domain)
        )
    return items


def _score_items(
    items: Iterable[DatasetItem],
    references: Sequence[str],
    scorer: Callable,
    scorer_params: dict,
) -> list[dict]:
    results = []
    for item in items:
        if scorer is baseline_score:
            score = scorer(item.host, references, scorer_params["transposition"])
        else:
            score = scorer(item.host, references, scorer_params)
        predicted = int(score >= app.TYPOQUAT_THRESHOLD)
        results.append({
            "algorithm": scorer_params["algorithm"],
            "host": item.host,
            "source_domain": item.source_domain,
            "variant_type": item.variant_type,
            "actual_label": item.label,
            "score": round(score, 6),
            "predicted_label": predicted,
            "classification": "HIGH_RISK" if predicted else "SAFE",
        })
    return results


def evaluate(items: Sequence[DatasetItem], references: Sequence[str]) -> list[dict]:
    """Score every item with the proposed and traditional algorithms."""
    proposed_params = {**DEFAULT_ENHANCED_PARAMS, "algorithm": "Enhanced Levenshtein"}
    traditional_params = {"transposition": False, "algorithm": "Traditional Levenshtein"}
    return (
        _score_items(items, references, enhanced_score, proposed_params)
        + _score_items(items, references, baseline_score, traditional_params)
    )


def calculate_metrics(results: Sequence[dict]) -> dict[str, float | int]:
    actual = [row["actual_label"] for row in results]
    predicted = [row["predicted_label"] for row in results]
    tp = sum(a == 1 and p == 1 for a, p in zip(actual, predicted))
    tn = sum(a == 0 and p == 0 for a, p in zip(actual, predicted))
    fp = sum(a == 0 and p == 1 for a, p in zip(actual, predicted))
    fn = sum(a == 1 and p == 0 for a, p in zip(actual, predicted))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "TP": tp,
        "TN": tn,
        "FP": fp,
        "FN": fn,
        "Precision": precision,
        "Recall": recall,
        "F1-Score": f1,
    }


def write_results(results: Sequence[dict], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "algorithm", "host", "source_domain", "variant_type",
        "actual_label", "score", "predicted_label", "classification",
    ]
    with output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)


def default_input(project_root: Path, stem: str, fallback: str) -> Path:
    requested = project_root / "research" / "data" / f"{stem}.txt"
    return requested if requested.exists() else project_root / "research" / "data" / fallback


def main() -> None:
    project_root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ph-input",
        type=Path,
        default=default_input(project_root, "ph_gov_domains", "ph_gov_domains.txt"),
    )
    parser.add_argument(
        "--us-input",
        type=Path,
        default=default_input(project_root, "us_gov_domains", "us_gov_domains.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=project_root / "research" / "results" / "updated_results.csv",
    )
    args = parser.parse_args()

    domains = sorted(set(load_domains(args.ph_input) + load_domains(args.us_input)))
    if not domains:
        raise ValueError("No legitimate domains were loaded from the input files.")

    items = build_dataset(domains)
    results = evaluate(items, domains)
    write_results(results, args.output)

    print(f"Loaded legitimate domains: {len(domains)}")
    print(f"Generated malicious variants: {sum(item.label for item in items)}")
    print(f"Evaluation threshold: similarity >= {app.TYPOQUAT_THRESHOLD:.2f}")
    print(f"\n{'Algorithm':<25} {'TP':>6} {'TN':>6} {'FP':>6} {'FN':>6} "
          f"{'Precision':>11} {'Recall':>9} {'F1-Score':>10}")
    for algorithm in ("Traditional Levenshtein", "Enhanced Levenshtein"):
        metrics = calculate_metrics([row for row in results if row["algorithm"] == algorithm])
        print(f"{algorithm:<25} {metrics['TP']:>6} {metrics['TN']:>6} "
              f"{metrics['FP']:>6} {metrics['FN']:>6} {metrics['Precision']:>11.4f} "
              f"{metrics['Recall']:>9.4f} {metrics['F1-Score']:>10.4f}")
    print(f"\nSaved raw results to {args.output}")


if __name__ == "__main__":
    main()
