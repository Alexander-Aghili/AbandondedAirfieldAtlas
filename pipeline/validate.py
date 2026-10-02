"""Validate generated coordinates, counts, IDs and source anchors without network access."""

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
from urllib.parse import unquote, urlparse

from bs4 import BeautifulSoup

if __package__:
    from .source import allowed
    from .parser import coordinate_values
else:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from pipeline.source import allowed
    from pipeline.parser import coordinate_values


def validate(dataset, cache):
    errors = []
    warnings = []
    ids = set()
    pages = defaultdict(list)
    for feature in dataset["features"]:
        p = feature["properties"]
        rid = feature["id"]
        if rid in ids:
            errors.append(f"Duplicate identity: {rid}")
        ids.add(rid)
        if not allowed(p["source_url"]):
            errors.append(f"Invalid source URL: {rid}")
        if feature["geometry"]:
            lon, lat = feature["geometry"]["coordinates"]
            if not (-180 <= lon <= 180 and -90 <= lat <= 90):
                errors.append(f"Invalid coordinate range: {rid}")
            source = coordinate_values(p["coordinate_text"])
            if source != (lat, lon):
                errors.append(
                    f"Coordinate text does not match longitude-first geometry: {rid}"
                )
        elif p["location_quality"] != "missing":
            errors.append(f"Unlocated entry has incorrect quality: {rid}")
        pages[p["source_page"]].append(feature)
    for url, records in pages.items():
        file = Path(cache) / (hashlib.sha256(url.encode()).hexdigest() + ".json")
        if not file.exists():
            warnings.append(f"Cache missing: {url}")
            continue
        soup = BeautifulSoup(json.loads(file.read_text())["html"], "html.parser")
        for f in records:
            p = f["properties"]
            frag = unquote(urlparse(p["source_url"]).fragment)
            if p["anchor_verified"]:
                target = soup.find(id=frag) or soup.find("a", attrs={"name": frag})
                if not target:
                    errors.append(f'Anchor absent: {p["source_url"]}')
                else:
                    block = (
                        target
                        if target.name in ("p", "h1", "h2", "h3")
                        else target.find_parent(["p", "h1", "h2", "h3"])
                    )
                    if (
                        block
                        and not block.find(
                            "font", attrs={"size": lambda v: v in ("5", "6")}
                        )
                        and block.name not in ("h1", "h2", "h3")
                        and block.get_text(strip=True)
                    ):
                        warnings.append(
                            f'Anchor may target nonheading: {p["source_url"]}'
                        )
            elif frag:
                errors.append(f'Unverified fragment published: {p["source_url"]}')
    m = dataset["metadata"]
    mapped = sum(f["geometry"] is not None for f in dataset["features"])
    if (
        m["total"] != len(ids)
        or m["mapped"] != mapped
        or m["unlocated"] != len(ids) - mapped
    ):
        errors.append("Metadata counts do not match features")
    return {
        "records": len(ids),
        "mapped": mapped,
        "pages_with_entries": len(pages),
        "errors": errors,
        "warnings": warnings,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default="web/data/airfields.geojson")
    parser.add_argument("--cache", default=".cache/source")
    args = parser.parse_args()
    result = validate(json.loads(Path(args.dataset).read_text()), args.cache)
    print(json.dumps(result, indent=2))
    if result["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
