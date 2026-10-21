"""Collect Philippine government domains from web directory pages."""

import argparse
import logging
import random
import re
import time
from pathlib import Path
from typing import Iterable

import requests
from bs4 import BeautifulSoup

CHROME_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
DOMAIN_PATTERN = re.compile(
    r"^(?:(?:https?:)?//)?(?:www\.)?"
    r"((?:[a-z0-9-]+\.)+gov\.ph)"
    r"(?::\d+)?(?:[/?#].*)?$",
    re.IGNORECASE,
)

LOGGER = logging.getLogger(__name__)


def domain_from_href(href: str) -> str | None:
    """Return a cleaned .gov.ph domain when href is a matching URL."""
    match = DOMAIN_PATTERN.match(href.strip())
    return match.group(1).lower() if match else None


def fetch_domains(
    starting_urls: Iterable[str], session: requests.Session
) -> set[str]:
    """Fetch each starting page and collect matching anchor domains."""
    domains: set[str] = set()

    for index, url in enumerate(starting_urls):
        if index:
            time.sleep(random.uniform(3, 6))

        try:
            response = session.get(url, timeout=30)
            response.raise_for_status()
        except requests.RequestException as error:
            LOGGER.warning("Skipping %s: %s", url, error)
            continue

        soup = BeautifulSoup(response.text, "html.parser")
        for anchor in soup.find_all("a"):
            href = anchor.get("href")
            if not isinstance(href, str):
                continue
            domain = domain_from_href(href)
            if domain:
                domains.add(domain)

    return domains


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract unique .gov.ph domains from directory pages."
    )
    parser.add_argument(
        "starting_urls",
        nargs="+",
        help="One or more directory page URLs to scan.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("scraped_domains.txt"),
        help="Output file (default: scraped_domains.txt).",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args()

    session = requests.Session()
    session.headers.update({"User-Agent": CHROME_USER_AGENT})
    domains = fetch_domains(args.starting_urls, session)

    args.output.write_text(
        "\n".join(sorted(domains)) + ("\n" if domains else ""),
        encoding="utf-8",
    )
    LOGGER.info("Wrote %d unique domains to %s", len(domains), args.output)


if __name__ == "__main__":
    main()
