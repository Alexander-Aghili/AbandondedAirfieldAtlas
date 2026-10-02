"""Extract airfield sections and source coordinates from catalog HTML."""

import re
import hashlib
from urllib.parse import quote, unquote
from bs4 import BeautifulSoup
from .source import BASE, clean

COORD = re.compile(
    r"^\s*([+-]?\s*\d+(?:\.\d+)?)\s*°?\s*,\s*([+-]?\s*\d+(?:\.\d+)?)\s*°?(?=\s|\(|$)"
)
AIRFIELD = re.compile(
    r"airport|airfield|\bfield\b|\bAAF\b|\bNAS\b|strip|aerodrome|seaplane|landing|heliport|air park|airpark|aeroplex|air base|gliderport|flying|\bNOLF\b|\bNAAS\b|air station|air facility",
    re.I,
)
BOUNDS = {
    "CA": (-125, -114, 32, 43),
    "TX": (-107, -93, 25, 37),
    "MA": (-74, -69, 41, 43),
}


def coordinate_values(text):
    """Parse only a leading coordinate line, including explicit hemispheres."""
    match = COORD.match(text)
    if match:
        trailing = text[match.end() :].strip()
        if (
            trailing
            and not trailing.startswith("(")
            and not re.match(r"approx|uncertain|(?:West|East|W|E)\b", trailing, re.I)
        ):
            return None
        return tuple(float(value.replace(" ", "")) for value in match.groups())
    match = re.match(
        r"^\s*(\d+(?:\.\d+)?)\s*°?\s*(North|South|N|S)\s*[/,]\s*(\d+(?:\.\d+)?)\s*°?\s*(West|East|W|E)\b",
        text,
        re.I,
    )
    if match:
        lat, ns, lon, ew = match.groups()
        return (
            float(lat) * (-1 if ns.lower().startswith("s") else 1),
            float(lon) * (-1 if ew.lower().startswith("w") else 1),
        )
    return None


def title_key(text):
    text = text.lower()
    for full, short in [
        ("naval outlying landing field", "nolf"),
        ("naval outer landing field", "nolf"),
        ("army airfield", "aaf"),
        ("naval air station", "nas"),
    ]:
        text = text.replace(full, short)
    text = re.sub(r"\((?:old|original)\)", "", text)
    return re.sub(r"[^a-z0-9]", "", text)


def toc_matches(name, record):
    aliases = name.split(" / ")
    heading = record["properties"]["name"]
    return any(
        len(title_key(part)) > 5 and title_key(part) in title_key(heading)
        for part in aliases
    )


def heading_anchor(heading):
    if heading.get("id"):
        return heading["id"]
    anchors = [
        a
        for a in heading.find_all(True)
        if a.get("id") or (a.name == "a" and a.get("name"))
    ]
    if anchors:
        fragments = [a.get("id") or a.get("name") for a in anchors]
        referenced = {
            unquote(a["href"][1:])
            for a in heading.find_all_previous("a", href=True)
            if a["href"].startswith("#")
        }
        return next((f for f in fragments if f in referenced), fragments[0])
    # Legacy pages put empty anchors between a divider and the heading.
    previous = heading.find_previous_sibling()
    while previous and not clean(previous):
        if previous.get("id") or previous.get("name"):
            return previous.get("id") or previous.get("name")
        a = previous.find("a", attrs={"name": True}) or previous.find(
            attrs={"id": True}
        )
        if a:
            return a.get("id") or a.get("name")
        previous = previous.find_previous_sibling()
    return None


def section_layout(soup):
    blocks = soup.find_all(["p", "h1", "h2", "h3"])
    candidates = []
    for i, p in enumerate(blocks):
        text = clean(p)
        large = p.find("font", attrs={"size": lambda v: v in ("5", "6")}) or p.find(
            style=re.compile(r"font-size:\s*(?:18|20|22|24)pt", re.I)
        )
        if (
            not text
            or text.startswith("_")
            or len(text) > 400
            or re.fullmatch(r"[_\s–-]+", text)
        ):
            continue
        if not (large or p.name in ("h2", "h3")):
            continue
        # Table of contents and regional navigation are not airport headings.
        if p.find("a", href=True):
            continue
        nearby = blocks[i + 1 : i + 5]
        if AIRFIELD.search(text) or any(
            coordinate_values(clean(b)) is not None for b in nearby
        ):
            candidates.append((i, p, text))
    merged = []
    for start, p, text in candidates:
        if merged:
            previous, heading, name = merged[-1]
            between = blocks[previous + 1 : start]
            if (not heading_anchor(p) or name.endswith(("/", ","))) and all(
                not clean(b) or b in [c[1] for c in candidates] for b in between
            ):
                merged[-1] = (
                    previous,
                    heading if heading_anchor(heading) else p,
                    name + " " + text,
                )
                continue
        merged.append((start, p, text))
    return blocks, merged


def parse(html, url, state, region, fetched_at, diagnostics=None):
    soup = BeautifulSoup(html, "html.parser")
    blocks, headings = section_layout(soup)
    revision = re.search(r"Revised\s+([\d/]+)", clean(soup), re.I)
    records = []
    used_anchors = set()
    used_coordinates = set()
    for n, (start, heading, name) in enumerate(headings):
        end = headings[n + 1][0] if n + 1 < len(headings) else len(blocks)
        coord = next(
            (
                clean(b)
                for b in blocks[start + 1 : min(start + 12, end)]
                if not b.find("img") and coordinate_values(clean(b)) is not None
            ),
            None,
        )
        notes = []
        geometry = None
        quality = "missing"
        if coord:
            used_coordinates.add(coordinate_values(coord))
            lat, lon = coordinate_values(coord)
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                geometry = {"type": "Point", "coordinates": [lon, lat]}
                quality = "source supplied"
                if state in BOUNDS:
                    lo, hi, la, lb = BOUNDS[state]
                    if not (lo <= lon <= hi and la <= lat <= lb):
                        notes.append(
                            "Coordinate outside expected state bounds; review required."
                        )
            else:
                notes.append("Invalid coordinate range; review required.")
        narrative = " ".join(clean(p) for p in blocks[start + 1 : end])
        if geometry and (
            re.search(r"approximate|uncertain", coord or "", re.I)
            or re.search(
                r"(precise|exact) location.{0,180}(not|unknown)|location.{0,50}(approximate|uncertain)|approximately located",
                narrative,
                re.I,
            )
        ):
            quality = "approximate"
            notes.append("Source describes location uncertainty.")
        fragment = heading_anchor(heading)
        if fragment:
            used_anchors.add(fragment)
        else:
            notes.append("No verified heading anchor; source link opens regional page.")
        source = url + "#" + quote(fragment, safe="") if fragment else url
        identity = url + "#" + (fragment or name)
        rid = hashlib.sha256(identity.encode()).hexdigest()[:16]
        props = {
            "id": rid,
            "name": name,
            "aliases": [s.strip() for s in name.split(" / ")[1:]],
            "state": state,
            "region": region,
            "source_page": url,
            "source_url": source,
            "anchor_verified": bool(fragment),
            "location_quality": quality,
            "notes": notes,
            "coordinate_text": coord,
            "fetched_at": fetched_at,
            "page_revision": revision.group(1) if revision else None,
            "section_fingerprint": hashlib.sha256(narrative.encode()).hexdigest(),
        }
        records.append(
            {"type": "Feature", "id": rid, "geometry": geometry, "properties": props}
        )
    if diagnostics is not None:
        # Coordinate lines not consumed near a heading flag unsupported layouts.
        diagnostics["unassigned_coordinates"] = [
            clean(p)
            for p in blocks
            if coordinate_values(clean(p)) is not None
            and coordinate_values(clean(p)) not in used_coordinates
        ]
        diagnostics["headings"] = len(headings)
        # Only top-of-page local links count as table-of-contents evidence.
        first = headings[0][1] if headings else None
        toc = {}
        if first:
            for a in first.find_all_previous("a", href=True):
                if a["href"].startswith("#") and clean(a):
                    toc[unquote(a["href"][1:])] = clean(a)
        diagnostics["toc_entries"] = len(toc)
        diagnostics["unmatched_toc"] = [
            {"fragment": frag, "name": name}
            for frag, name in toc.items()
            if frag not in used_anchors
            and AIRFIELD.search(name)
            and not any(toc_matches(name, r) for r in records)
        ]
    return records
