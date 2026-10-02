"""Retain unlocated index records and reconcile current and historical pages."""

from collections import deque
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse
from .source import BASE
from .parser import title_key


def retain_index_only(features, pages):
    """Keep unmatched source-index entries searchable without inventing a point."""
    by_page = {f["properties"]["source_page"]: f["properties"] for f in features}
    for page in pages:
        template = by_page.get(page["url"])
        if not template:
            continue
        for entry in page.get("unmatched_toc", []):
            rid = hashlib.sha256(
                (page["url"] + "#" + entry["fragment"]).encode()
            ).hexdigest()[:16]
            props = {
                k: template[k]
                for k in (
                    "state",
                    "state_name",
                    "region",
                    "source_page",
                    "fetched_at",
                    "page_revision",
                )
            }
            props.update(
                {
                    "id": rid,
                    "name": entry["name"],
                    "aliases": [a.strip() for a in entry["name"].split(" / ")[1:]],
                    "source_url": page["url"],
                    "anchor_verified": False,
                    "location_quality": "missing",
                    "coordinate_text": None,
                    "record_origin": "index only",
                    "index_fragment": entry["fragment"],
                    "notes": [
                        "Listed in the source index, but no corresponding airport section or source coordinates were found."
                    ],
                }
            )
            features.append(
                {"type": "Feature", "id": rid, "geometry": None, "properties": props}
            )
    return features


def catalog_membership(pages, features, failures):
    """Trace current menus separately from citations inside airport histories."""
    by_url = {p["url"]: p for p in pages}
    current = {BASE} if BASE in by_url else set(by_url)
    queue = deque([BASE])
    while queue:
        url = queue.popleft()
        page = by_url.get(url)
        if page and not page["entries"]:
            for child in page.get("links", []):
                if url != BASE:
                    folder = Path(urlparse(url).path).parent.name
                    child_folder = Path(urlparse(child).path).parent.name
                    code = re.match(
                        r"Airfields_([A-Z]{2})(?:_|\.)", Path(urlparse(child).path).name
                    )
                    if child_folder != folder or (code and code.group(1) != folder):
                        continue
                if child not in current:
                    current.add(child)
                    queue.append(child)
    unavailable = [
        f
        for f in failures
        if f.get("http_status") in (404, 410) and f["url"] not in current
    ]
    failures = [f for f in failures if f not in unavailable]
    # Equal names AND equal exact source coordinates are evidence of copies.
    # Nearby points or merely similar names are never merged.
    features.sort(key=lambda f: f["properties"]["source_page"] not in current)
    unique = {}
    duplicates = []
    for f in features:
        p = f["properties"]
        p["catalog_membership"] = (
            "current menu" if p["source_page"] in current else "linked historical page"
        )
        key = (title_key(p["name"]), json.dumps(f["geometry"], sort_keys=True))
        if (
            key in unique
            and f["geometry"] is not None
            and (
                p["source_page"] != unique[key]["properties"]["source_page"]
                or (
                    p.get("section_fingerprint")
                    and p["section_fingerprint"]
                    == unique[key]["properties"].get("section_fingerprint")
                )
            )
        ):
            kept = unique[key]
            kept["properties"].setdefault("alternate_source_urls", []).append(
                p["source_url"]
            )
            duplicates.append(
                {
                    "kept": kept["properties"]["source_url"],
                    "duplicate": p["source_url"],
                    "reason": "Identical name and source coordinates on different pages, or identical repeated section content",
                }
            )
        elif key in unique:
            unique[(key, f["id"])] = f
        else:
            unique[key] = f
    return list(unique.values()), failures, unavailable, duplicates, current
