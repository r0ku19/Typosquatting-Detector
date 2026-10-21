from backend import app


def check_detection(url):
    matched_domain, similarity_score, is_typosquat = app.detect_typosquat(url)
    print(
        f"{url}: typosquat={is_typosquat}, "
        f"matched_domain={matched_domain}, similarity={similarity_score:.4f}"
    )
    return matched_domain, similarity_score, is_typosquat


def main():
    matched_domain, similarity_score, is_typosquat = check_detection("bri.gov.ph")
    assert is_typosquat is True
    assert matched_domain == "bir.gov.ph"
    assert similarity_score >= 0.85

    matched_domain, _, is_typosquat = check_detection("www.philhealth.gov.ph")
    assert is_typosquat is False

    matched_domain, similarity_score, is_typosquat = check_detection("evilphilhealth.gov.ph")
    print(
        "evilphilhealth.gov.ph check: "
        f"is_typosquat={is_typosquat}, "
        f"matched_domain={matched_domain}, "
        f"similarity_score={similarity_score:.4f}"
    )

    _, _, is_typosquat = check_detection("ph1lhealth.gov.ph")
    assert is_typosquat is True

    _, _, is_typosquat = check_detection("dti.gov.ph")
    assert is_typosquat is False

    app.VISUAL_SUBSTITUTION_COST = 0.5
    assert app.substitution_cost("o", "0") == 0.5
    print("Runtime visual substitution setting check: passed")

    print("All checks passed.")


if __name__ == "__main__":
    main()