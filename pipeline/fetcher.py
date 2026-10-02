"""Serial, robots-aware requests with an offline HTML cache."""

import hashlib
import json
import time
from pathlib import Path
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser
import requests
from .source import BASE, allowed
from .storage import atomic_json


class SourceUnavailable(RuntimeError):
    def __init__(self, url, status):
        self.status = status
        super().__init__(f"HTTP {status}: {url}")


class Fetcher:
    def __init__(self, cache, delay=2, refresh=False, offline=False):
        self.cache = Path(cache)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.last = 0
        self.delay = max(2, delay)
        self.refresh = refresh
        self.offline = offline
        self.session = requests.Session()
        self.session.headers["User-Agent"] = (
            "AbandonedAirfieldsCatalog/0.2 (serial cached historical map research)"
        )
        self.robots = RobotFileParser()
        self.robots.parse(self.get(BASE + "robots.txt", check=False)[0].splitlines())

    def get(self, url, check=True):
        if not allowed(url):
            raise ValueError("Disallowed source URL")
        if check and not self.robots.can_fetch(self.session.headers["User-Agent"], url):
            raise ValueError("Robots guidance disallows URL")
        key = self.cache / (hashlib.sha256(url.encode()).hexdigest() + ".json")
        if key.exists() and not self.refresh:
            d = json.loads(key.read_text())
            if d.get("status") in (404, 410):
                raise SourceUnavailable(url, d["status"])
            return d["html"], d["fetched_at"]
        if self.offline:
            raise RuntimeError("Page is not cached: " + url)
        last_error = None
        for attempt in range(3):
            time.sleep(
                max(
                    0,
                    max(self.delay, self.robots.crawl_delay("*") or 0)
                    - (time.monotonic() - self.last),
                )
            )
            try:
                # Validate each redirect BEFORE requesting it.
                target = url
                for hop in range(6):
                    r = self.session.get(target, timeout=45, allow_redirects=False)
                    self.last = time.monotonic()
                    if r.is_redirect:
                        target = urljoin(target, r.headers["Location"])
                        if not allowed(target):
                            raise ValueError("Redirect outside source domain")
                        if check and not self.robots.can_fetch(
                            self.session.headers["User-Agent"], target
                        ):
                            raise ValueError("Redirect disallowed by robots")
                        time.sleep(self.delay)
                        continue
                    break
                else:
                    raise ValueError("Too many redirects")
                if r.status_code in (429, 500, 502, 503, 504):
                    retry = r.headers.get("Retry-After", "")
                    try:
                        wait = int(retry)
                    except ValueError:
                        try:
                            wait = max(
                                0,
                                (
                                    parsedate_to_datetime(retry)
                                    - datetime.now(timezone.utc)
                                ).total_seconds(),
                            )
                        except (ValueError, TypeError):
                            wait = 0
                    time.sleep(max(2 ** (attempt + 2), wait))
                    last_error = f"HTTP {r.status_code}"
                    continue
                if r.status_code in (404, 410):
                    atomic_json(
                        key,
                        {
                            "url": url,
                            "status": r.status_code,
                            "html": r.text,
                            "fetched_at": datetime.now(timezone.utc).isoformat(),
                        },
                    )
                    raise SourceUnavailable(url, r.status_code)
                r.raise_for_status()
                stamp = datetime.now(timezone.utc).isoformat()
                atomic_json(key, {"url": url, "html": r.text, "fetched_at": stamp})
                return r.text, stamp
            except (requests.Timeout, requests.ConnectionError) as exc:
                last_error = str(exc)
                time.sleep(2 ** (attempt + 2))
        raise RuntimeError(f"Retries exhausted: {url}: {last_error}")
