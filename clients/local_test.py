import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BACKEND_URL = "http://127.0.0.1:5000/check-url"


def scan_url(target_url: str):
    payload = json.dumps({"url": target_url}).encode("utf-8")
    request = Request(
        BACKEND_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urlopen(request, timeout=15) as response:
        body = response.read().decode("utf-8")
        return json.loads(body)


def main():
    print("Philippine .gov.ph Typosquatting Scanner")
    print("Press Ctrl+C to stop.\n")

    while True:
        try:
            target_url = input("Enter a URL to check: ").strip()

            if not target_url:
                print("Please enter a URL.\n")
                continue

            try:
                result = scan_url(target_url)
            except HTTPError as exc:
                print(f"Backend returned HTTP {exc.code}.")
                print(exc.read().decode("utf-8", errors="replace"))
                continue
            except URLError as exc:
                print(f"Unable to reach the backend: {exc.reason}")
                continue
            except json.JSONDecodeError:
                print("Backend response was not valid JSON.")
                continue

            print("\nScan Result")
            print(f"Typosquat detected: {result.get('is_typosquat')}")
            print(f"Similarity score: {result.get('similarity_score')}")
            print(f"Matched domain: {result.get('matched_domain')}")

            if result.get("is_typosquat"):
                print("Warning: This URL is suspicious and may be a typosquat.")
            else:
                print("No typosquatting flag raised.")
            print()
        except KeyboardInterrupt:
            print("\nScanner stopped.")
            break


if __name__ == "__main__":
    main()