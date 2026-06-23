import re
import sys
import httpx

EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')

FALSE_POSITIVE_TLDS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".css", ".js",
    ".woff", ".woff2", ".ttf", ".eot", ".ico", ".webp",
}

# Domains that commonly appear as false positives in source code
FALSE_POSITIVE_DOMAINS = {
    "sentry.io", "example.com", "schema.org", "w3.org",
    "jquery.com", "google.com", "googleapis.com", "cloudflare.com",
}

PREFER_PREFIXES = ("info", "contact", "hello", "office", "admin", "team")

_client = httpx.Client(timeout=10, follow_redirects=True, verify=False)


def _extract_emails(html: str) -> list[str]:
    found = EMAIL_RE.findall(html)
    clean: list[str] = []
    for email in found:
        local, domain = email.rsplit("@", 1)
        # Skip false-positive TLDs (CSS/image refs embedded in addresses)
        if any(domain.endswith(tld) for tld in FALSE_POSITIVE_TLDS):
            continue
        if domain.lower() in FALSE_POSITIVE_DOMAINS:
            continue
        clean.append(email.lower())
    return list(dict.fromkeys(clean))  # dedup, preserve order


def _best_email(emails: list[str]) -> str:
    for prefix in PREFER_PREFIXES:
        for e in emails:
            if e.startswith(prefix + "@") or e.startswith(prefix + "."):
                return e
    return emails[0]


def _try_fetch(url: str) -> str | None:
    try:
        resp = _client.get(url)
        if resp.status_code < 400:
            return resp.text
    except Exception:
        pass
    return None


def enrich_lead(website: str) -> str | None:
    """
    Fetch homepage and contact pages of `website`. Return best email found, or None.
    """
    if not website:
        return None

    base = website.rstrip("/")
    pages = [
        base,
        base + "/contact",
        base + "/contact-us",
        base + "/about",
    ]

    for url in pages:
        html = _try_fetch(url)
        if html:
            emails = _extract_emails(html)
            if emails:
                return _best_email(emails)

    return None


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "https://squeegeeguy.com"
    result = enrich_lead(url)
    print(f"Email found: {result}" if result else "No email found")
