"""Coverage reporting and guarded dataset publication."""

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from .reconciliation import retain_index_only, catalog_membership
from .storage import atomic_json


class DatasetPublisher:
    def __init__(self, output, pilot=False, allow_partial=False):
        self.output = Path(output)
        self.pilot = pilot
        self.allow_partial = allow_partial

    def publish(self, features, pages, failures, inventory, advertised):
        features = retain_index_only(features, pages)
        features, failures, unavailable, source_duplicates, current_menu = (
            catalog_membership(pages, features, failures)
        )
        current_count = sum(
            f["properties"]["catalog_membership"] == "current menu" for f in features
        )
        current_sections = sum(
            f["properties"]["catalog_membership"] == "current menu"
            and f["properties"].get("record_origin") != "index only"
            for f in features
        )
        index_only = sum(
            f["properties"].get("record_origin") == "index only" for f in features
        )
        ids = Counter(f["id"] for f in features)
        duplicate_ids = sorted(i for i, count in ids.items() if count > 1)
        gaps = [
            {
                "url": p["url"],
                "unassigned_coordinates": p.get("unassigned_coordinates", []),
                "unmatched_toc": p.get("unmatched_toc", []),
            }
            for p in pages
            if p.get("unassigned_coordinates") or p.get("unmatched_toc")
        ]
        out = self.output
        current = out / "airfields.geojson"
        previous = json.loads(current.read_text()) if current.exists() else None
        old_by_id = (
            {f["id"]: f for f in previous.get("features", [])} if previous else {}
        )
        new_by_id = {f["id"]: f for f in features}
        changes = {
            "added": sorted(new_by_id.keys() - old_by_id.keys()),
            "removed": sorted(old_by_id.keys() - new_by_id.keys()),
            "coordinate_changes": [
                {
                    "id": rid,
                    "previous": old_by_id[rid]["geometry"],
                    "current": new_by_id[rid]["geometry"],
                }
                for rid in new_by_id.keys() & old_by_id.keys()
                if new_by_id[rid]["geometry"] != old_by_id[rid]["geometry"]
            ],
        }
        unexpected_drop = bool(
            previous
            and previous.get("metadata", {}).get("scope")
            == "Catalog-wide automated crawl"
            and len(features) < len(old_by_id) * 0.95
        )
        report = {
            "scope": (
                "Four-region pilot" if self.pilot else "Catalog-wide automated crawl"
            ),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "pages_discovered": len(inventory),
            "pages_fetched": len(pages),
            "pages": pages,
            "failures": failures,
            "unavailable_historical_links": unavailable,
            "source_duplicates": source_duplicates,
            "changes": changes,
            "unexpected_drop": unexpected_drop,
            "current_menu_entries": current_count,
            "current_menu_sections": current_sections,
            "index_only_entries": index_only,
            "supplemental_entries": len(features) - current_count,
            "parsing_gaps": gaps,
            "inventory": list(inventory.values()),
            "total": len(features),
            "mapped": sum(f["geometry"] is not None for f in features),
            "unlocated": sum(f["geometry"] is None for f in features),
            "approximate": sum(
                f["properties"]["location_quality"] == "approximate" for f in features
            ),
            "links_without_anchor": sum(
                not f["properties"]["anchor_verified"] for f in features
            ),
            "duplicate_ids": duplicate_ids,
            "advertised_count": advertised,
            "count_difference": current_sections - advertised if advertised else None,
            "coverage_complete": not self.pilot
            and not failures
            and not gaps
            and not duplicate_ids
            and current_sections == advertised,
        }
        atomic_json(out / "coverage.json", report)
        if (failures or duplicate_ids or unexpected_drop) and not self.allow_partial:
            raise SystemExit(
                "Dataset retained: unresolved failures. See coverage.json."
            )
        current = out / "airfields.geojson"
        if current.exists():
            atomic_json(
                out / "airfields.previous.geojson", json.loads(current.read_text())
            )
        metadata = {
            k: v
            for k, v in report.items()
            if k
            not in (
                "pages",
                "inventory",
                "parsing_gaps",
                "state_names",
                "duplicate_ids",
                "source_duplicates",
                "unavailable_historical_links",
                "changes",
            )
        }
        metadata["parsing_gap_count"] = len(gaps)
        atomic_json(
            current,
            {"type": "FeatureCollection", "metadata": metadata, "features": features},
        )
        print(json.dumps(metadata, indent=2))
