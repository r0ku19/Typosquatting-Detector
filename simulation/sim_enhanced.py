import sys
from urllib.parse import urlparse


INSERT_COST = 1.0
DELETION_COST = 1.15
SUBSTITUTION_COST = 1.25
VISUAL_SUBSTITUTION_COST = 0.2
TRANSPOSITION_COST = 1.0
SEGMENT_MULTIPLIER = 1.8
# These pairs represent visually confusable character substitutions.
VISUAL_PAIRS = {
    ("o", "0"), ("0", "o"), ("i", "1"), ("1", "i"), ("l", "1"), ("1", "l"),
    ("s", "5"), ("5", "s"), ("e", "3"), ("3", "e"), ("a", "@"), ("@", "a"),
    ("g", "q"), ("q", "g"), ("g", "9"), ("9", "g"), ("t", "7"), ("7", "t"),
}


def normalize(value):
    # Compare hostnames only, regardless of whether the user enters a full URL.
    value = (value or "").strip().lower()
    parsed = urlparse(value if "://" in value else f"http://{value}")
    return (parsed.hostname or parsed.path.split("/")[0]).strip(".")


def substitution_cost(source_char, target_char):
    # An exact match is free; a visual pair receives the reduced visual cost.
    if source_char == target_char:
        return 0.0
    if (source_char, target_char) in VISUAL_PAIRS:
        return VISUAL_SUBSTITUTION_COST
    return SUBSTITUTION_COST


def enhanced_levenshtein(source, target, segment_multiplier):
    # source is the candidate; target is the legitimate reference.
    # The extra row and column represent the empty-string starting cases.
    matrix = [[0.0 for _ in range(len(target) + 1)] for _ in range(len(source) + 1)]
    # Store the chosen operation at each cell so the final path can be explained.
    operations = [[None for _ in range(len(target) + 1)] for _ in range(len(source) + 1)]

    # Initialize deletion costs, applying the segment multiplier.
    for row in range(1, len(source) + 1):
        matrix[row][0] = matrix[row - 1][0] + DELETION_COST * segment_multiplier
        operations[row][0] = ("DELETE", source[row - 1], "-", DELETION_COST)
    # Initialize insertion costs, applying the segment multiplier.
    for column in range(1, len(target) + 1):
        matrix[0][column] = matrix[0][column - 1] + INSERT_COST * segment_multiplier
        operations[0][column] = ("INSERT", "-", target[column - 1], INSERT_COST)

    # Each cell chooses the cheapest replacement, deletion, or insertion.
    for row in range(1, len(source) + 1):
        for column in range(1, len(target) + 1):
            replacement_cost = substitution_cost(source[row - 1], target[column - 1])
            choices = [
                (
                    matrix[row - 1][column - 1]
                    + replacement_cost * segment_multiplier,
                    "MATCH" if replacement_cost == 0.0 else "SUBST",
                    source[row - 1],
                    target[column - 1],
                    replacement_cost,
                ),
                (
                    matrix[row - 1][column] + DELETION_COST * segment_multiplier,
                    "DELETE",
                    source[row - 1],
                    "-",
                    DELETION_COST,
                ),
                (
                    matrix[row][column - 1] + INSERT_COST * segment_multiplier,
                    "INSERT",
                    "-",
                    target[column - 1],
                    INSERT_COST,
                ),
            ]
            best = min(choices, key=lambda choice: choice[0])
            matrix[row][column] = best[0]
            operations[row][column] = best[1:]

            # Also consider swapping adjacent characters as one transposition.
            if (
                row > 1
                and column > 1
                and source[row - 1] == target[column - 2]
                and source[row - 2] == target[column - 1]
            ):
                transposition = (
                    matrix[row - 2][column - 2]
                    + TRANSPOSITION_COST * segment_multiplier
                )
                if transposition < matrix[row][column]:
                    matrix[row][column] = transposition
                    operations[row][column] = (
                        "TRANSPOSE",
                        source[row - 2 : row],
                        target[column - 2 : column],
                        TRANSPOSITION_COST,
                    )

    path = []
    row, column = len(source), len(target)
    # Reconstruct the cheapest operation path from the final matrix cell.
    while row or column:
        name, source_chars, target_chars, cost = operations[row][column]
        step = 2 if name == "TRANSPOSE" else 1
        path.append(
            (
                target_chars,
                source_chars,
                name,
                cost * segment_multiplier,
                matrix[row][column],
            )
        )
        row -= 0 if name == "INSERT" else step
        column -= 0 if name == "DELETE" else step

    # Reverse the backward path so the trace reads from first to last operation.
    return matrix[-1][-1], list(reversed(path))


def get_inputs():
    default_target = "dfa.gov.ph"
    default_candidate = "dfa.qov.ph"
    if len(sys.argv) > 1:
        # Command-line arguments take priority when provided.
        target = sys.argv[1]
        candidate = sys.argv[2] if len(sys.argv) > 2 else default_candidate
    else:
        # With no arguments, allow interactive input and retain defaults on Enter.
        target = input("Target URL: ").strip() or default_target
        candidate = input("Candidate URL: ").strip() or default_candidate
    return normalize(target), normalize(candidate)


def main():
    target, candidate = get_inputs()
    # Pass candidate first because the algorithm names it source.
    raw_distance, path = enhanced_levenshtein(
        candidate, target, SEGMENT_MULTIPLIER
    )

    print(f"[Target: {target} | Candidate: {candidate}] BEFORE Similarity Check...")
    for iteration, (target_char, source_char, operation, cost, current_dist) in enumerate(
        path, start=1
    ):
        print(
            f"Iter {iteration:03d} | char_t={target_char} | char_s={source_char} "
            f"| op={operation} | cost={cost:.2f} | current_dist={current_dist:.2f}"
        )

    # Normalize by the longer hostname, matching the backend similarity formula.
    similarity = max(
        0.0, 1.0 - (raw_distance / max(len(target), len(candidate)))
    )
    # The backend threshold determines whether the candidate is high risk.
    risk_level = "HIGH_RISK_TYPOSQUAT" if similarity >= 0.82 else "SAFE"
    print(
        f"[Target: {target} | Candidate: {candidate}] "
        f"AFTER Raw_Dist={raw_distance:.2f} Similarity={similarity:.2f} "
        f"VERDICT={risk_level}"
    )


if __name__ == "__main__":
    main()
