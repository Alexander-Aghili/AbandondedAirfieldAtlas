"""Discover catalog pages once and collect parsing diagnostics."""

from collections import deque
from pathlib import Path
import re
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from .source import BASE, discover
from .parser import parse
from .source import clean
from .storage import atomic_json

PILOT = [
    ("CA/Airfields_CA_SanRafael.htm", "CA", "Marin County"),
    ("CA/Airfields_CA_NE.htm", "CA", "Northeastern California"),
    ("TX/Airfields_TX_BigBend.htm", "TX", "Big Bend"),
    ("MA/Airfields_MA_W.htm", "MA", "Western Massachusetts"),
]


class CatalogCrawler:
    def __init__(
        self, fetcher, pilot=False, progress_path=".cache/crawl-progress.json"
    ):
        self.fetcher = fetcher
        self.pilot = pilot
        self.progress_path = Path(progress_path)

    def crawl(self):
        seeds = (
            {urljoin(BASE, p): r for p, s, r in PILOT}
            if self.pilot
            else {BASE: "Catalog home"}
        )
        queue = deque(seeds)
        inventory = {
            u: {"url": u, "label": label, "discovered_from": []}
            for u, label in seeds.items()
        }
        features = []
        pages = []
        failures = []
        advertised = None
        state_names = {}
        while queue:
            url = queue.popleft()
            item = inventory[url]
            try:
                html, stamp = self.fetcher.get(url)
                if url == BASE:
                    match = re.search(
                        r"([\d,]+)\s+airfields",
                        clean(BeautifulSoup(html, "html.parser")),
                        re.I,
                    )
                    if match:
                        advertised = int(match.group(1).replace(",", ""))
                state = (
                    urlparse(url).path.strip("/").split("/")[0] if url != BASE else ""
                )
                if state == "HI" and "W_Pacific" in url:
                    state = "Pacific"
                soup = BeautifulSoup(html, "html.parser")
                title = clean(soup.title) if soup.title else item["label"]
                region = (
                    re.sub(
                        r"^Abandoned\s*&\s*Little-Known Airfields\s*:?\s*",
                        "",
                        title,
                        flags=re.I,
                    )
                    or item["label"]
                )
                diag = {}
                records = (
                    parse(html, url, state, region, stamp, diag) if url != BASE else []
                )
                features.extend(records)
                links = {} if self.pilot else discover(html, url)
                for child, label in links.items():
                    if url == BASE:
                        state_names[urlparse(child).path.strip("/").split("/")[0]] = (
                            label
                        )
                    if child not in inventory:
                        inventory[child] = {
                            "url": child,
                            "label": label or Path(urlparse(child).path).stem,
                            "discovered_from": [url],
                        }
                        queue.append(child)
                    elif url not in inventory[child]["discovered_from"]:
                        inventory[child]["discovered_from"].append(url)
                children = [u for u in links if u != url]
                if url != BASE and not records and not children:
                    failures.append(
                        {
                            "url": url,
                            "error": "No sections or catalog navigation detected",
                        }
                    )
                pages.append(
                    {
                        "url": url,
                        "entries": len(records),
                        "fetched_at": stamp,
                        "links": list(links),
                        **diag,
                    }
                )
                print(
                    f"[{len(pages)} fetched / {len(inventory)} discovered] {len(features)} entries — {url}",
                    flush=True,
                )
            except Exception as exc:
                failures.append(
                    {
                        "url": url,
                        "error": str(exc),
                        "http_status": getattr(exc, "status", None),
                    }
                )
                print(f"FAILED {url}: {exc}", flush=True)
            atomic_json(
                self.progress_path,
                {
                    "pages": pages,
                    "failures": failures,
                    "inventory": list(inventory.values()),
                    "queued": len(queue),
                    "entries": len(features),
                },
            )
        state_names["Pacific"] = "Western Pacific Islands"
        for feature in features:
            feature["properties"]["state_name"] = state_names.get(
                feature["properties"]["state"], feature["properties"]["state"]
            )
        return features, pages, failures, inventory, advertised


def crawl(fetcher, pilot=False):
    return CatalogCrawler(fetcher, pilot).crawl()
