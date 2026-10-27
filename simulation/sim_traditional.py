import sys
from urllib.parse import urlparse


INSERT_COST = 1.0
DELETION_COST = 1.0
SUBSTITUTION_COST = 1.0


def normalize(value):
    # Compare hostnames only, regardless of whether the user enters a full URL.
    value = (value or "").strip().lower()
    parsed = urlparse(value if "://" in value else f"http://{value}")
    return (parsed.hostname or parsed.path.split("/")[0]).strip(".")


def levenshtein(source, target):
    # source is the candidate; target is the legitimate reference.
    # The extra row and column represent the empty-string starting cases.
    matrix = [[0.0 for _ in range(len(target) + 1)] for _ in range(len(source) + 1)]
    # Store the chosen operation at each cell so the final path can be explained.
    operations = [[None for _ in range(len(target) + 1)] for _ in range(len(source) + 1)]

    # Initialize the cost of deleting the candidate one character at a time.
    for row in range(1, len(source) + 1):
        matrix[row][0] = matrix[row - 1][0] + DELETION_COST
        operations[row][0] = ("DELETE", source[row - 1], "-", DELETION_COST)
    # Initialize the cost of inserting the target one character at a time.
    for column in range(1, len(target) + 1):
        matrix[0][column] = matrix[0][column - 1] + INSERT_COST
        operations[0][column] = ("INSERT", "-", target[column - 1], INSERT_COST)

    # Each cell chooses the cheapest match/substitution, deletion, or insertion.
    for row in range(1, len(source) + 1):
        for column in range(1, len(target) + 1):
            replacement_cost = (
                0.0 if source[row - 1] == target[column - 1] else SUBSTITUTION_COST
            )
            choices = [
                (
                    matrix[row - 1][column - 1] + replacement_cost,
                    "MATCH" if replacement_cost == 0.0 else "SUBST",
                    source[row - 1],
                    target[column - 1],
                    replacement_cost,
                ),
                (
                    matrix[row - 1][column] + DELETION_COST,
                    "DELETE",
                    source[row - 1],
                    "-",
                    DELETION_COST,
                ),
                (
                    matrix[row][column - 1] + INSERT_COST,
                    "INSERT",
                    "-",
                    target[column - 1],
                    INSERT_COST,
                ),
            ]
            best = min(choices, key=lambda choice: choice[0])
            matrix[row][column] = best[0]
            operations[row][column] = best[1:]

    # The bottom-right cell is the minimum distance for the complete strings.
    return matrix[-1][-1], trace(matrix, operations, source, target)


def trace(matrix, operations, source, target):
    path = []
    row, column = len(source), len(target)
    # Walk backward through the chosen operations, then reverse for display order.
    while row or column:
        name, source_chars, target_chars, cost = operations[row][column]
        path.append(
            (target_chars, source_chars, name, cost, matrix[row][column])
        )
        row -= 0 if name == "INSERT" else 1
        column -= 0 if name == "DELETE" else 1
    return list(reversed(path))


def get_inputs():
    default_target = "dfa.gov.ph"
    default_candidate = "dfa.qov.ph"
    if len(sys.argv) > 1:
        # Command-line arguments take priority when provided.
        target = sys.argv[1]
        candidate = sys.argv[2] if len(sys.argv) > 2 else default_candidate
    else:
        # With no arguments, allow interactive input and retain defaults on Enter.
        try:
            target = input("Target URL: ").strip() or default_target
            candidate = input("Candidate URL: ").strip() or default_candidate
        except EOFError:
            target, candidate = default_target, default_candidate
    return normalize(target), normalize(candidate)


def main():
    target, candidate = get_inputs()
    # Pass candidate first because the algorithm names it source.
    raw_distance, path = levenshtein(candidate, target)

    print(f"[Target: {target} | Candidate: {candidate}] BEFORE Similarity Check...")
    for iteration, (target_char, source_char, operation, cost, current_dist) in enumerate(
        path, start=1
    ):
        print(
            f"Iter {iteration:03d} | char_t={target_char} | char_s={source_char} "
            f"| op={operation} | cost={cost:.2f} | current_dist={current_dist:.2f}"
        )

    # Traditional detection uses a direct raw-distance cutoff.
    risk_level = "HIGH_RISK_TYPOSQUAT" if raw_distance <= 2.0 else "SAFE"
    # Normalize distance by the longer hostname so lengths are comparable.
    similarity = 1.0 - raw_distance / max(len(target), len(candidate), 1)
    print(
        f"[Target: {target} | Candidate: {candidate}] "
        f"AFTER Raw_Dist={raw_distance:.2f} Similarity={similarity:.2f} "
        f"VERDICT={risk_level}"
    )


if __name__ == "__main__":
    main()
