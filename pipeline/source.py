"""Catalog URL rules and recursive link discovery."""

import re
from urllib.parse import urlparse, urldefrag, urljoin
from bs4 import BeautifulSoup

BASE = "https://airfields-freeman.com/"


def allowed(url):
    p = urlparse(url)
    return (
        p.scheme in ("https", "http")
        and p.hostname in ("airfields-freeman.com", "www.airfields-freeman.com")
        and not p.username
        and not p.password
        and p.port in (None, 80, 443)
    )


def canonical(url):
    p = urlparse(urldefrag(url)[0])
    if not allowed(url):
        return None
    return "https://airfields-freeman.com" + (p.path or "/")


def catalog_url(url):
    p = urlparse(url)
    return allowed(url) and bool(re.search(r"/Airfields_[^/]+\.html?$", p.path, re.I))


def discover(html, url):
    """Only follow catalog HTML links; never fetch historical images."""
    found = {}
    for a in BeautifulSoup(html, "html.parser").find_all("a", href=True):
        target = canonical(urljoin(url, a["href"]))
        if target and catalog_url(target):
            label = clean(a)
            if target not in found or len(label) > len(found[target]):
                found[target] = label
    return found


def clean(element):
    """Normalize visible text without splitting inline coordinate digits."""
    return " ".join(element.get_text("", strip=False).split())
