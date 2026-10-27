import argparse
import csv
import os
import random
import re
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

import requests
from sklearn.metrics import average_precision_score, f1_score, precision_score, recall_score

try:
    from backend import app
except ModuleNotFoundError:
    import app

SEED = 42
WEB_CONFUSABLES_URL = "https://www.unicode.org/Public/security/latest/confusables.txt"
VISUAL_FALLBACK_PAIRS = [
    ("a", "4"), ("b", "6"), ("c", "("), ("e", "3"), ("g", "9"),
    ("h", "#"), ("i", "1"), ("l", "1"), ("o", "0"), ("q", "9"),
    ("s", "5"), ("t", "7"), ("z", "2"), ("A", "4"), ("B", "8"),
    ("E", "3"), ("G", "6"), ("I", "1"), ("O", "0"), ("S", "5"),
    ("T", "7"), ("Z", "2"), ("m", "rn"), ("n", "r"),
]
UNRELATED_DOMAINS = [
    "google.com", "microsoft.com", "apple.com", "amazon.com", "facebook.com",
    "youtube.com", "wikipedia.org", "github.com", "stackoverflow.com", "reddit.com",
    "cnn.com", "bbc.com", "nytimes.com", "adobe.com", "zoom.us", "paypal.com",
    "stripe.com", "cloudflare.com", "openai.com", "mozilla.org", "python.org",
    "w3.org", "linkedin.com", "instagram.com", "tiktok.com", "netflix.com",
    "spotify.com", "dropbox.com", "salesforce.com", "oracle.com",
]
PARAMETER_RANGES = {
    "deletion": [0.8, 1.0, 1.15, 1.3, 1.5],
    "substitution": [1.0, 1.25, 1.5, 2.0],
    "visual": [0.05, 0.1, 0.2, 0.35, 0.5],
    "primary": [1.0, 1.5, 1.8, 2.5, 3.0],
    "tld": [0.25, 0.5, 0.7, 1.0],
}
VARIANT_TYPES = ["insertion", "deletion", "ordinary_substitution", "visual_substitution",
                 "transposition", "tld_alteration", "subdomain_manipulation"]
CALIBRATION_ITEMS = []
CALIBRATION_REFERENCES = []


def load_domains(path):
    return sorted({line.strip().lower() for line in Path(path).read_text().splitlines() if line.strip()})


def visual_pairs():
    try:
        text = requests.get(WEB_CONFUSABLES_URL, timeout=20).text
        pairs = set()
        for line in text.splitlines():
            fields = line.split("#", 1)[0].split(";")
            if len(fields) < 2:
                continue
            left = fields[0].strip().split()
            right = fields[1].strip().split()
            if len(left) == len(right) == 1:
                first, second = chr(int(left[0], 16)), chr(int(right[0], 16))
                if first.isascii() and second.isascii() and first != second:
                    pairs.add((first.lower(), second.lower()))
        if pairs:
            return sorted(pairs)
        print("Warning: Unicode confusables had no ASCII-to-ASCII pairs; using fallback pairs.")
    except requests.RequestException as error:
        print(f"Warning: could not download Unicode confusables ({error}); using fallback pairs.")
    return VISUAL_FALLBACK_PAIRS


def split_host(host):
    return app.split_host_segments(host)


def replace_primary(host, replacement):
    parts = host.split(".")
    if len(parts) >= 2 and parts[-2:] == ["gov", "ph"]:
        primary_index = -3
        if len(parts) >= 3:
            parts[primary_index] = replacement
            return ".".join(parts)
    return host


def mutate_primary(host, variant_type, pairs, rng):
    segments = split_host(host)
    primary = segments.primary
    if not primary:
        return None
    if variant_type == "insertion":
        index = rng.randrange(len(primary) + 1)
        return replace_primary(host, primary[:index] + rng.choice("abcdefghijklmnopqrstuvwxyz") + primary[index:])
    if variant_type == "deletion" and primary:
        return replace_primary(host, primary[:rng.randrange(len(primary))] + primary[rng.randrange(len(primary)) + 1:])
    if variant_type == "ordinary_substitution" and primary:
        index = rng.randrange(len(primary))
        replacement = rng.choice([char for char in "abcdefghijklmnopqrstuvwxyz" if char != primary[index]])
        return replace_primary(host, primary[:index] + replacement + primary[index + 1:])
    if variant_type == "visual_substitution":
        choices = [(index, pair[1]) for index, char in enumerate(primary) for pair in pairs if pair[0] == char]
        if choices:
            index, replacement = rng.choice(choices)
            return replace_primary(host, primary[:index] + replacement + primary[index + 1:])
    if variant_type == "transposition" and len(primary) > 1:
        index = rng.randrange(len(primary) - 1)
        chars = list(primary)
        chars[index], chars[index + 1] = chars[index + 1], chars[index]
        return replace_primary(host, "".join(chars))
    return None


def make_variants(domain, pairs, rng):
    variants = []
    for variant_type in VARIANT_TYPES[:5]:
        variant = mutate_primary(domain, variant_type, pairs, rng)
        if variant:
            variants.append((variant, variant_type))
    variants.extend([
        (re.sub(r"\.gov\.ph$", ".gov.ps", domain), "tld_alteration"),
        (re.sub(r"\.gov\.ph$", ".gob.ph", domain), "tld_alteration"),
        (re.sub(r"\.gov\.ph$", ".com.ph", domain), "tld_alteration"),
        ("www." + domain, "subdomain_manipulation"),
        (domain.replace(".gov.ph", ".service.gov.ph"), "subdomain_manipulation"),
    ])
    return [(host, kind) for host, kind in variants if host != domain]


def build_items(domains, rng):
    shuffled = list(domains)
    rng.shuffle(shuffled)
    split = int(len(shuffled) * 0.70)
    references, withheld = [d for d in shuffled[:split] if d != "gov.ph"], shuffled[split:]
    pairs = visual_pairs()
    items = []
    for domain in references:
        for host, variant_type in make_variants(domain, pairs, rng):
            if host not in references:
                items.append({"host": host, "label": 1, "group": domain, "variant": variant_type})
    for domain in withheld:
        items.append({"host": domain, "label": 0, "group": domain, "variant": "withheld"})
    for domain in references:
        items.append({"host": "www." + domain, "label": 0, "group": domain, "variant": "www_legitimate"})
    for domain in UNRELATED_DOMAINS:
        items.append({"host": domain, "label": 0, "group": domain, "variant": "unrelated"})
    return references, items


def grouped_split(items, rng):
    # Group splitting prevents variants of one source domain leaking across splits.
    groups = sorted({item["group"] for item in items})
    rng.shuffle(groups)
    first = int(len(groups) * 0.60)
    second = first + int(len(groups) * 0.20)
    names = {"calibration": set(groups[:first]), "validation": set(groups[first:second]), "test": set(groups[second:])}
    return {name: [item for item in items if item["group"] in selected] for name, selected in names.items()}


def apply_params(params):
    app.INSERT_COST = 1.0
    app.DELETION_COST = params["deletion"]
    app.SUBSTITUTION_COST = params["substitution"]
    app.VISUAL_SUBSTITUTION_COST = params["visual"]
    app.TRANSPOSITION_COST = params["transposition"]
    app.SEGMENT_MULTIPLIERS = {"subdomain": 1.0, "primary": params["primary"], "tld": params["tld"]}


def enhanced_score(host, references, params):
    apply_params(params)
    if app.is_legitimate_host(host, references):
        return 0.0
    return max((app.score_host_pair(host, reference)[0] for reference in references), default=0.0)


def plain_distance(source, target, transposition=False):
    matrix = [[0] * (len(target) + 1) for _ in range(len(source) + 1)]
    for row in range(len(source) + 1):
        matrix[row][0] = row
    for column in range(len(target) + 1):
        matrix[0][column] = column
    for row in range(1, len(source) + 1):
        for column in range(1, len(target) + 1):
            matrix[row][column] = min(matrix[row - 1][column] + 1, matrix[row][column - 1] + 1,
                                      matrix[row - 1][column - 1] + (source[row - 1] != target[column - 1]))
            if transposition and row > 1 and column > 1 and source[row - 1] == target[column - 2] and source[row - 2] == target[column - 1]:
                matrix[row][column] = min(matrix[row][column], matrix[row - 2][column - 2] + 1)
    return matrix[-1][-1]


def baseline_score(host, references, transposition=False):
    if app.is_legitimate_host(host, references):
        return 0.0
    return max((1 - plain_distance(host, reference, transposition) / max(len(host), len(reference), 1)
                for reference in references), default=0.0)


def scores(items, references, scorer, params=None):
    return [scorer(item["host"], references, params) if params else scorer(item["host"], references) for item in items]


def threshold_for(items, values):
    labels = [item["label"] for item in items]
    best_threshold, best_j = 0.50, -1.0
    for step in range(51):
        threshold = 0.50 + step * 0.01
        predicted = [value >= threshold for value in values]
        true_positive = sum(actual and guess for actual, guess in zip(labels, predicted))
        false_positive = sum(not actual and guess for actual, guess in zip(labels, predicted))
        false_negative = sum(actual and not guess for actual, guess in zip(labels, predicted))
        true_negative = sum(not actual and not guess for actual, guess in zip(labels, predicted))
        recall = true_positive / max(true_positive + false_negative, 1)
        false_positive_rate = false_positive / max(false_positive + true_negative, 1)
        if recall - false_positive_rate > best_j:
            best_threshold, best_j = threshold, recall - false_positive_rate
    return round(best_threshold, 2)


def metrics(items, values, threshold):
    labels = [item["label"] for item in items]
    predicted = [value >= threshold for value in values]
    return {"recall": recall_score(labels, predicted, zero_division=0),
            "precision": precision_score(labels, predicted, zero_division=0),
            "f1": f1_score(labels, predicted, zero_division=0),
            "fpr": sum(not actual and guess for actual, guess in zip(labels, predicted)) / max(sum(not actual for actual in labels), 1),
            "pr_auc": average_precision_score(labels, values)}


def recall_by_variant(items, values, threshold):
    output = {}
    for variant in VARIANT_TYPES:
        selected = [(item, value) for item, value in zip(items, values) if item["variant"] == variant]
        if selected:
            output[variant] = metrics([item for item, _ in selected], [value for _, value in selected], threshold)["recall"]
    return output


def random_params(rng):
    while True:
        params = {name: rng.choice(values) for name, values in PARAMETER_RANGES.items()}
        if params["visual"] < params["substitution"] and params["primary"] > params["tld"]:
            params["transposition"] = 1.0
            return params


def initialize_calibration_worker(items, references):
    global CALIBRATION_ITEMS, CALIBRATION_REFERENCES
    CALIBRATION_ITEMS = items
    CALIBRATION_REFERENCES = references


def calibration_score(params):
    values = scores(CALIBRATION_ITEMS, CALIBRATION_REFERENCES, enhanced_score, params)
    labels = [item["label"] for item in CALIBRATION_ITEMS]
    return params, average_precision_score(labels, values)


def calibrate(items, references, rng):
    # Each configuration is independent, so workers evaluate the same 150-config search in parallel.
    configurations = [random_params(rng) for _ in range(150)]
    workers = min(8, os.cpu_count() or 1)
    with ProcessPoolExecutor(
        max_workers=workers,
        initializer=initialize_calibration_worker,
        initargs=(items, references),
    ) as executor:
        results = list(executor.map(calibration_score, configurations))
    return max(results, key=lambda result: result[1])


def evaluate_method(name, items, values, threshold):
    result = {"method": name, "threshold": threshold, **metrics(items, values, threshold)}
    result.update({f"recall_{key}": value for key, value in recall_by_variant(items, values, threshold).items()})
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "domains",
        nargs="?",
        default=str(Path(__file__).parents[1] / "research" / "data" / "ph_gov_domains.txt"),
    )
    parser.add_argument(
        "--output",
        default=str(Path(__file__).parents[1] / "research" / "results" / "results.csv"),
    )
    args = parser.parse_args()
    rng = random.Random(SEED)
    references, items = build_items(load_domains(args.domains), rng)
    splits = grouped_split(items, rng)
    print(f"Built {len(items)} items from {len(references)} reference domains; calibrating...")
    params, calibration_pr_auc = calibrate(splits["calibration"], references, rng)
    methods = {"proposed": (enhanced_score, params)}
    methods["Levenshtein"] = (baseline_score, {"transposition": False})
    methods["Damerau-Levenshtein"] = (baseline_score, {"transposition": True})
    methods["ablation_wd_equal_wi"] = (enhanced_score, {**params, "deletion": 1.0})
    methods["ablation_visual_equal_default"] = (enhanced_score, {**params, "visual": params["substitution"]})
    methods["ablation_no_multipliers"] = (enhanced_score, {**params, "primary": 1.0, "tld": 1.0})
    methods["ablation_no_transposition"] = (enhanced_score, {**params, "transposition": 999.0})
    results = []
    thresholds = {}
    for name, (scorer, method_params) in methods.items():
        validation_values = scores(splits["validation"], references, scorer, method_params)
        test_values = scores(splits["test"], references, scorer, method_params)
        thresholds[name] = threshold_for(splits["validation"], validation_values)
        results.append(evaluate_method(name, splits["test"], test_values, thresholds[name]))
    fieldnames = sorted({key for result in results for key in result})
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    print(f"Calibration PR-AUC: {calibration_pr_auc:.4f}")
    print(f"Chosen params: {params}")
    print(f"Thresholds: {thresholds}")
    print("\nMethod                         Recall  Precision  F1      FPR     PR-AUC")
    for result in results:
        print(f"{result['method']:<30} {result['recall']:.3f}   {result['precision']:.3f}      {result['f1']:.3f}   {result['fpr']:.3f}   {result['pr_auc']:.3f}")
    print(f"Saved {output_path}")


if __name__ == "__main__":
    main()
