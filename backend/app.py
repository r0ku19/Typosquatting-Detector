import os
from dataclasses import dataclass
from typing import List, Optional, Tuple
from urllib.parse import urlparse

from flask import Flask, jsonify, request

try:
    import mysql.connector as mysql_connector
except ImportError:  # pragma: no cover - keeps the prototype runnable without MySQL installed.
    mysql_connector = None


app = Flask(__name__)


@app.after_request
def add_extension_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    return response


# ============================================================================
# SETTINGS: change these values when tuning the thesis prototype.
# ============================================================================

# Database settings can be overridden with MYSQL_* environment variables.
DEFAULT_DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", "NewPasswordHere"),
    "database": os.getenv("MYSQL_DATABASE", "govph_typosquat"),
}

# Edit these costs to experiment with different edit penalties.
INSERT_COST = 1.0
DELETION_COST = 1.15
SUBSTITUTION_COST = 1.25
VISUAL_SUBSTITUTION_COST = 0.2
TRANSPOSITION_COST = 1.0

# A higher multiplier makes edits in that URL segment more important.
SEGMENT_MULTIPLIERS = {
    "subdomain": 1.0,
    "primary": 1.8,
    "tld": 0.7,
}

# A non-exact match at or above this score is flagged as a possible typosquat.
TYPOQUAT_THRESHOLD = float(os.getenv("TYPOQUAT_THRESHOLD", "0.82"))

# Used if MySQL is unavailable during development.
FALLBACK_DOMAINS = [
    "gov.ph",
    "philhealth.gov.ph",
    "bir.gov.ph",
    "lto.gov.ph",
    "pnp.gov.ph",
    "deped.gov.ph",
    "dfa.gov.ph",
    "dilg.gov.ph",
    "dict.gov.ph",
    "neda.gov.ph",
]

# Add or remove visually similar character pairs here.
VISUAL_PAIRS = {
    ("o", "0"),
    ("0", "o"),
    ("i", "1"),
    ("1", "i"),
    ("l", "1"),
    ("1", "l"),
    ("s", "5"),
    ("5", "s"),
    ("e", "3"),
    ("3", "e"),
    ("a", "@"),
    ("@", "a"),
    ("g", "9"),
    ("9", "g"),
    ("t", "7"),
    ("7", "t"),
}


@dataclass(frozen=True)
class HostSegments:
    subdomain: str
    primary: str
    tld: str


def normalize_url_or_host(value: str) -> str:
    """Return only the lowercase hostname from a URL or host string."""
    # Comparison uses hostnames only, so protocol, path, and query details are ignored.
    value = (value or "").strip().lower()
    if not value:
        return ""

    candidate = value if "://" in value else f"http://{value}"
    parsed = urlparse(candidate)
    host = parsed.hostname or ""

    if not host and parsed.path:
        host = parsed.path.split("/")[0]

    return host.strip(".")


def split_host_segments(host: str) -> HostSegments:
    """Split a host into the three parts used by the scoring algorithm."""
    # Philippine government hosts use the fixed public suffix "gov.ph".
    labels = [label for label in host.split(".") if label]
    if not labels:
        return HostSegments(subdomain="", primary="", tld="")

    if len(labels) >= 2 and labels[-2:] == ["gov", "ph"]:
        tld = "gov.ph"
        primary = labels[-3] if len(labels) >= 3 else ""
        subdomain = ".".join(labels[:-3]) if len(labels) > 3 else ""
        return HostSegments(subdomain=subdomain, primary=primary, tld=tld)

    if len(labels) == 1:
        return HostSegments(subdomain="", primary=labels[0], tld="")

    tld = ".".join(labels[-2:])
    primary = labels[-3] if len(labels) >= 3 else labels[0]
    subdomain = ".".join(labels[:-3]) if len(labels) > 3 else ""
    return HostSegments(subdomain=subdomain, primary=primary, tld=tld)


def substitution_cost(source_char: str, target_char: str) -> float:
    if source_char == target_char:
        return 0.0
    if (source_char, target_char) in VISUAL_PAIRS:
        return VISUAL_SUBSTITUTION_COST
    return SUBSTITUTION_COST


def enhanced_levenshtein(source: str, target: str, segment_multiplier: float) -> float:
    """Calculate weighted edit distance using a dynamic programming matrix."""
    # Each cell stores the cheapest weighted sequence of edits seen so far.
    source = source or ""
    target = target or ""
    source_length = len(source)
    target_length = len(target)

    matrix = [[0.0 for _ in range(target_length + 1)] for _ in range(source_length + 1)]

    for index in range(1, source_length + 1):
        matrix[index][0] = matrix[index - 1][0] + (DELETION_COST * segment_multiplier)
    for index in range(1, target_length + 1):
        matrix[0][index] = matrix[0][index - 1] + (INSERT_COST * segment_multiplier)

    for row in range(1, source_length + 1):
        for column in range(1, target_length + 1):
            deletion = matrix[row - 1][column] + (DELETION_COST * segment_multiplier)
            insertion = matrix[row][column - 1] + (INSERT_COST * segment_multiplier)
            replacement = matrix[row - 1][column - 1] + (
                substitution_cost(source[row - 1], target[column - 1]) * segment_multiplier
            )
            matrix[row][column] = min(deletion, insertion, replacement)

            # A transposition handles adjacent swaps such as "bri" versus "bir".
            if (
                row > 1
                and column > 1
                and source[row - 1] == target[column - 2]
                and source[row - 2] == target[column - 1]
            ):
                transposition = matrix[row - 2][column - 2] + (
                    TRANSPOSITION_COST * segment_multiplier
                )
                matrix[row][column] = min(matrix[row][column], transposition)

    return matrix[source_length][target_length]


def segment_distance(source: str, target: str, segment_name: str) -> Tuple[float, float]:
    if not source and not target:
        return 0.0, 0.0

    multiplier = SEGMENT_MULTIPLIERS[segment_name]
    distance = enhanced_levenshtein(source, target, multiplier)
    segment_length = max(len(source), len(target), 1)
    maximum_cost = segment_length * max(
        INSERT_COST,
        DELETION_COST,
        SUBSTITUTION_COST,
        TRANSPOSITION_COST,
    ) * multiplier
    return distance, maximum_cost


def score_host_pair(target_host: str, candidate_host: str) -> Tuple[float, float]:
    target_segments = split_host_segments(target_host)
    candidate_segments = split_host_segments(candidate_host)

    # Score each URL segment separately so primary-domain edits can be weighted.
    comparisons = [
        (target_segments.subdomain, candidate_segments.subdomain, "subdomain"),
        (target_segments.primary, candidate_segments.primary, "primary"),
        (target_segments.tld, candidate_segments.tld, "tld"),
    ]

    total_distance = 0.0
    total_capacity = 0.0

    for source_segment, candidate_segment, segment_name in comparisons:
        distance, capacity = segment_distance(source_segment, candidate_segment, segment_name)
        total_distance += distance
        total_capacity += capacity

    if total_capacity == 0:
        return 1.0, 0.0

    similarity = max(0.0, 1.0 - (total_distance / total_capacity))
    return similarity, total_distance


def get_mysql_connection(database: Optional[str] = None):
    if mysql_connector is None:
        raise RuntimeError("mysql-connector-python is not installed")

    config = dict(DEFAULT_DB_CONFIG)
    if database is not None:
        config["database"] = database
    return mysql_connector.connect(**config)


def load_legitimate_domains() -> List[str]:
    if mysql_connector is None:
        return list(FALLBACK_DOMAINS)

    try:
        connection = get_mysql_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT domain FROM legitimate_domains WHERE active = 1 ORDER BY domain ASC")
        domains = [row[0].lower().strip() for row in cursor.fetchall() if row and row[0]]
        cursor.close()
        connection.close()
        return domains or list(FALLBACK_DOMAINS)
    except Exception:
        return list(FALLBACK_DOMAINS)


def is_legitimate_host(host: str, domains: List[str]) -> bool:
    if host == "gov.ph":
        return True

    return any(
        domain != "gov.ph" and (host == domain or host.endswith(f".{domain}"))
        for domain in domains
    )


def detect_typosquat(target_url: str):
    normalized_host = normalize_url_or_host(target_url)
    if not normalized_host:
        return None, 0.0, False

    legitimate_domains = load_legitimate_domains()
    exact_match = is_legitimate_host(normalized_host, legitimate_domains)
    comparison_domains = [domain for domain in legitimate_domains if domain != "gov.ph"]

    best_domain = None
    best_score = -1.0

    # The closest reference domain is the one with the highest normalized similarity.
    for legitimate_domain in comparison_domains:
        similarity, _ = score_host_pair(normalized_host, legitimate_domain)
        if similarity > best_score:
            best_score = similarity
            best_domain = legitimate_domain

    # Known legitimate hosts are never flagged; unknown hosts need to exceed the threshold.
    is_typosquat = bool(best_domain) and not exact_match and best_score >= TYPOQUAT_THRESHOLD
    return best_domain, best_score if best_score >= 0 else 0.0, is_typosquat


@app.post("/check-url")
def check_url():
    # Both the CLI and Chrome extension use this same centralized endpoint.
    payload = request.get_json(silent=True) or {}
    target_url = (payload.get("url") or "").strip()

    if not target_url:
        return jsonify({"error": "A non-empty url field is required."}), 400

    try:
        matched_domain, similarity_score, is_typosquat = detect_typosquat(target_url)
        return jsonify(
            {
                "is_typosquat": is_typosquat,
                "similarity_score": round(similarity_score, 4),
                "matched_domain": matched_domain,
            }
        )
    except Exception as exc:
        return jsonify({"error": "Failed to process URL.", "details": str(exc)}), 500


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=True)