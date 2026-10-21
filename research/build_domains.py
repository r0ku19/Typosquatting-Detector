import argparse
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

WEB_URL = "https://www.gov.ph/es/directory-of-department-and-agencies.html"
HOST_PATTERN = re.compile(r"(?:[a-z0-9-]+\.)+gov\.ph", re.IGNORECASE)


def normalize(host):
    host = host.lower().strip().strip(".,;:!?)]}>'\"")
    if host.startswith("www."):
        host = host[4:]
    return host.rstrip(".")


def hosts_from(text):
    # Regex extraction is followed by normalization and filtering of non-website domains.
    hosts = set()
    for match in HOST_PATTERN.findall(text):
        host = normalize(match)
        if host != "gov.ph" and "@" not in host:
            hosts.add(host)
    return hosts


def pdf_text(path):
    # PDF extraction may split ".gov" across lines; repair it before regex matching.
    text = "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    return re.sub(r"\.\s+(gov|ph)\b", r".\1", text)


def web_text():
    response = requests.get(WEB_URL, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    links = " ".join(anchor.get("href", "") for anchor in soup.find_all("a"))
    return f"{soup.get_text(' ')} {links}"


def main():
    parser = argparse.ArgumentParser(description="Build a .gov.ph domain list from a PDF and gov.ph directory.")
    parser.add_argument("pdf", type=Path, help="Path to the DBM Philippine Government Directory PDF")
    parser.add_argument("--url", action="store_true", help="Also scan the public gov.ph directory page")
    args = parser.parse_args()

    # The PDF is the required source; the public page is an optional supplement.
    domains = hosts_from(pdf_text(args.pdf))
    if args.url:
        domains.update(hosts_from(web_text()))

    output = Path(__file__).parent / "data" / "domains.txt"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(sorted(domains)) + "\n", encoding="utf-8")
    print(f"Found {len(domains)} hosts; wrote {output}")
    print("\n".join(sorted(domains)[:20]))


if __name__ == "__main__":
    main()
