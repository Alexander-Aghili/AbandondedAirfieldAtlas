import unittest
from pipeline.extract import parse, allowed


class ExtractionTests(unittest.TestCase):
    def test_section_coordinates_and_anchors(self):
        html = """<p><a href="#a">Index</a></p><p><a name="a"></a><font size="5">Old Airport / Alias, CA</font></p><p>41, -121.62 (CA)</p><p>History mentions 33, -100.</p><p>Its precise location has not been determined.</p><p><font size="5">Replacement Airport, CA</font></p><p>39.16 ,-121.57</p><p><font size="5">Missing Field, CA</font></p><p>No coordinates available</p>"""
        records = parse(
            html, "https://airfields-freeman.com/CA/test.htm", "CA", "Test", "today"
        )
        self.assertEqual(len(records), 3)
        self.assertEqual(records[0]["geometry"]["coordinates"], [-121.62, 41])
        self.assertEqual(records[0]["properties"]["location_quality"], "approximate")
        self.assertTrue(records[0]["properties"]["source_url"].endswith("#a"))
        self.assertFalse(records[1]["properties"]["anchor_verified"])
        self.assertEqual(records[1]["geometry"]["coordinates"], [-121.57, 39.16])
        self.assertIsNone(records[2]["geometry"])
        self.assertNotEqual(records[0]["id"], records[1]["id"])

    def test_url_allowlist(self):
        self.assertTrue(allowed("https://airfields-freeman.com/CA/test.htm"))
        for url in [
            "javascript:alert(1)",
            "https://evil.test/",
            "https://airfields-freeman.com.evil.test/",
            "https://user@airfields-freeman.com/",
        ]:
            self.assertFalse(allowed(url))

    def test_invalid_coordinates(self):
        records = parse(
            "<h2>Example Airport</h2><p>91, -121</p>",
            "https://airfields-freeman.com/x.htm",
            "CA",
            "Test",
            "today",
        )
        self.assertIsNone(records[0]["geometry"])


class LayoutTests(unittest.TestCase):
    def test_split_numbers_and_multiline_heading(self):
        html = """<p><a href="#combined">Example Airport</a></p><p><font size="5">Example Airport /</font></p><p><a name="combined"></a><font size="5">Naval Outlying Landing Field, CA</font></p><p><font>37.6</font>92, <font>-</font>121.79</p>"""
        diag = {}
        records = parse(
            html, "https://airfields-freeman.com/CA/x.htm", "CA", "Test", "today", diag
        )
        self.assertEqual(len(records), 1)
        self.assertIn("Naval Outlying", records[0]["properties"]["name"])
        self.assertEqual(records[0]["geometry"]["coordinates"], [-121.79, 37.692])
        self.assertTrue(records[0]["properties"]["source_url"].endswith("#combined"))
        self.assertFalse(diag["unmatched_toc"])

    def test_index_prefers_referenced_anchor(self):
        html = '<p><a href="#actual">Example Airport</a></p><p><a name="actual"></a><a name="typo"></a><font size="5">Example Airport, CA</font></p><p>39, -121</p>'
        record = parse(
            html, "https://airfields-freeman.com/x.htm", "CA", "Test", "today"
        )[0]
        self.assertTrue(record["properties"]["source_url"].endswith("#actual"))

    def test_discovery_is_recursive_same_domain_html_only(self):
        from pipeline.extract import discover

        html = """<a href="../TX/Airfields_TX.htm#one">Texas</a><a href="Airfields_CA_NE.htm">NE</a><a href="Airfields_CA_NE.htm#two">NE</a><a href="photo.jpg">Photo</a><a href="https://evil.test/Airfields_Evil.htm">Bad</a>"""
        urls = discover(html, "https://airfields-freeman.com/CA/Airfields_CA.htm")
        self.assertEqual(
            set(urls),
            {
                "https://airfields-freeman.com/TX/Airfields_TX.htm",
                "https://airfields-freeman.com/CA/Airfields_CA_NE.htm",
            },
        )

    def test_crawler_discovers_unknown_pages_and_cycles(self):
        from pipeline.extract import crawl, BASE
        from unittest.mock import patch

        class FakeFetcher:
            def get(self, url):
                if url == BASE:
                    return (
                        '<p>2 airfields</p><a href="XY/Airfields_XY.htm">Example state</a>',
                        "now",
                    )
                if url.endswith("Airfields_XY.htm"):
                    return '<a href="Airfields_XY_N.htm">Northern region</a>', "now"
                return (
                    '<a href="Airfields_XY.htm">Back</a><h2>One Airport</h2><p>40, -100</p><h2>Two Field</h2><p>Unknown position</p>',
                    "now",
                )

        with patch("pipeline.crawler.atomic_json"):
            records, pages, failures, inventory, count = crawl(FakeFetcher())
        self.assertEqual(len(records), 2)
        self.assertEqual(len(inventory), 3)
        self.assertFalse(failures)
        self.assertEqual(count, 2)
        self.assertIsNone(records[1]["geometry"])
        self.assertEqual(records[0]["properties"]["state_name"], "Example state")


class CoordinateTests(unittest.TestCase):
    def test_hemispheres_and_narrative_numbers(self):
        from pipeline.extract import coordinate_values

        self.assertEqual(
            coordinate_values("28.71 North / 96.25 West (TX)"), (28.71, -96.25)
        )
        self.assertEqual(coordinate_values("14.2 South / 170.3 East"), (-14.2, 170.3))
        self.assertIsNone(coordinate_values("2,293 TBFs and other aircraft."))
        self.assertIsNone(coordinate_values("History mentions 40, -100."))


class PublishingTests(unittest.TestCase):
    def test_failed_refresh_retains_existing_dataset(self):
        import json
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from pipeline.extract import main

        with tempfile.TemporaryDirectory() as directory:
            dataset = Path(directory) / "airfields.geojson"
            dataset.write_text('{"previous":true}')
            with patch("sys.argv", ["extract", "--output", directory]), patch(
                "pipeline.extract.Fetcher"
            ), patch(
                "pipeline.extract.crawl",
                return_value=(
                    [],
                    [],
                    [{"url": "failed", "error": "timeout"}],
                    {},
                    2884,
                ),
            ):
                with self.assertRaises(SystemExit):
                    main()
            self.assertEqual(dataset.read_text(), '{"previous":true}')
            self.assertEqual(
                json.loads((Path(directory) / "coverage.json").read_text())["failures"][
                    0
                ]["error"],
                "timeout",
            )


class MembershipTests(unittest.TestCase):
    def test_current_navigation_and_retired_citations(self):
        from pipeline.extract import BASE, catalog_membership

        pages = [
            {"url": BASE, "entries": 0, "links": [BASE + "CA/Airfields_CA.htm"]},
            {
                "url": BASE + "CA/Airfields_CA.htm",
                "entries": 0,
                "links": [BASE + "CA/Airfields_CA_New.htm"],
            },
            {
                "url": BASE + "CA/Airfields_CA_New.htm",
                "entries": 1,
                "links": [BASE + "CA/Airfields_CA_Old.htm"],
            },
        ]

        def record(page, rid):
            return {
                "id": rid,
                "geometry": {"type": "Point", "coordinates": [-121, 39]},
                "properties": {
                    "name": "Example Airport, CA",
                    "source_page": page,
                    "source_url": page + "#example",
                },
            }

        features = [
            record(BASE + "CA/Airfields_CA_Old.htm", "old"),
            record(BASE + "CA/Airfields_CA_New.htm", "new"),
        ]
        dead = [{"url": BASE + "CA/Airfields_CA_Retired.htm", "http_status": 404}]
        records, failures, unavailable, duplicates, current = catalog_membership(
            pages, features, dead
        )
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["id"], "new")
        self.assertEqual(len(duplicates), 1)
        self.assertFalse(failures)
        self.assertEqual(unavailable, dead)
        self.assertIn(BASE + "CA/Airfields_CA_New.htm", current)
        self.assertNotIn(BASE + "CA/Airfields_CA_Old.htm", current)


class CompletenessTests(unittest.TestCase):
    def test_index_only_reference_is_retained_unlocated(self):
        from pipeline.extract import retain_index_only

        records = [
            {
                "properties": {
                    "state": "TX",
                    "state_name": "Texas",
                    "region": "Corpus Christi",
                    "source_page": "https://airfields-freeman.com/TX/x.htm",
                    "fetched_at": "now",
                    "page_revision": "1/1/26",
                }
            }
        ]
        pages = [
            {
                "url": "https://airfields-freeman.com/TX/x.htm",
                "unmatched_toc": [
                    {"name": "Example Field / Alias", "fragment": "missing"}
                ],
            }
        ]
        result = retain_index_only(records, pages)[-1]
        self.assertIsNone(result["geometry"])
        self.assertEqual(result["properties"]["location_quality"], "missing")
        self.assertEqual(result["properties"]["source_url"], pages[0]["url"])
        self.assertFalse(result["properties"]["anchor_verified"])

    def test_identical_repeated_source_sections_merge(self):
        from pipeline.extract import BASE, catalog_membership

        def record(rid):
            return {
                "id": rid,
                "geometry": {"type": "Point", "coordinates": [-100, 40]},
                "properties": {
                    "name": "Example Field",
                    "source_page": BASE + "TX/Airfields_TX.htm",
                    "source_url": BASE + "TX/Airfields_TX.htm#" + rid,
                    "section_fingerprint": "same-content",
                },
            }

        pages = [
            {"url": BASE, "entries": 0, "links": [BASE + "TX/Airfields_TX.htm"]},
            {"url": BASE + "TX/Airfields_TX.htm", "entries": 2, "links": []},
        ]
        records, _, _, duplicates, _ = catalog_membership(
            pages, [record("first"), record("copy")], []
        )
        self.assertEqual(len(records), 1)
        self.assertEqual(len(duplicates), 1)

    def test_coordinate_artifacts_beside_images_are_not_locations(self):
        records = parse(
            '<h2>Example Field</h2><p><img src="history.jpg">40.76, -73.31</p>',
            "https://airfields-freeman.com/WV/x.htm",
            "WV",
            "Example",
            "now",
        )
        self.assertIsNone(records[0]["geometry"])


if __name__ == "__main__":
    unittest.main()
