# Abandoned Airfields Web Map Build Plan

Implementation guide  |  2 October 2026

Build an interactive map of the airfields cataloged at airfields-freeman.com. Visitors can pan, zoom, search, and filter the map. Clicking an individual airport marker opens its original Freeman entry in a new tab, ideally scrolled to the airport section. The map remains available in the original tab.

## Scope and evidence

The homepage reports 2,884 airfields. Regional pages inspected in Marin County, northeastern California, Big Bend, and western Massachusetts include coordinates beneath airfield headings. This establishes feasibility, but nationwide coordinate coverage has not yet been measured. The map will represent Freeman’s catalog, not a complete census of every abandoned airfield.

Initial scope: points, names and aliases, state or territory, source links, search, clustering, and visible location uncertainty. Historical imagery and runway outlines are later enhancements. Retain entries with missing coordinates in a searchable unlocated list.

## Recommended implementation

Use a Python extraction pipeline to generate a versioned GeoJSON dataset, then a static web app using Leaflet and marker clustering. A build process serves the dataset with the app. Visitors do not fetch or scrape Freeman’s pages; the only request to his site occurs when they follow a source link. Select a basemap provider whose tile usage terms support the expected traffic, and show its required attribution.

## Minimum record schema

| Field | Meaning |
| --- | --- |
| id and name | Stable record identifier and displayed airfield name |
| aliases and region | Other names, state or territory, and regional page label |
| geometry | Point in GeoJSON order [longitude, latitude], or null |
| source_page and source_url | Regional page URL and URL including the verified airport fragment |
| location_quality and notes | source supplied, approximate, reviewed, or missing; supporting notes |
| fetched_at and page_revision | Retrieval timestamp and source revision text when available |

Keep the original coordinate text in extraction records. Decimal places indicate numeric resolution, not proven positional accuracy. Do not label a source coordinate as independently verified.

## Collect and validate the airport dataset

### Step 1  Establish the source inventory

Fetch the homepage and follow its state and territory links. Follow regional links until reaching pages with airport entries. Resolve relative URLs against the containing page; strip fragments only when identifying pages to fetch. Allow only the intended source domain and relevant HTML pages. Deduplicate URLs and record discovery paths.

Check published crawl guidance. Start with one request at a time, a conservative delay such as two seconds, local caching, and bounded retries with backoff. Honor server responses requesting slower access. Fetch HTML first; downloading the historical image collection is unnecessary for the initial map.

### Step 2  Parse a small pilot sample

Start with the four inspected regions. Parse the HTML DOM rather than treating the whole page as one text string. Separate individual airport sections from the navigation index. Associate each heading with its nearby coordinate line and its section anchor, using the table of contents links as additional evidence. Record each entry even if its coordinates cannot be parsed.

Support integer and decimal coordinates, extra spaces, and irregular comma placement. For example, northeastern California includes “41, -121.62” and “39.16 ,-121.57”. Match coordinate lines near the heading, so a coordinate mentioned elsewhere in the history does not become the marker by accident.

### Step 3  Build precise source links

Inspect both element id attributes and legacy anchor name attributes. Preserve the fragment used by the source page. Verify that the fragment actually targets the airport heading or its immediately preceding anchor. Store page URL plus fragment as source_url. If no usable anchor exists, link to the regional page and flag that record for link review; never invent a fragment from the airport name.

### Step 4  Expand and reconcile the full catalog

Run the validated parser across the inventory. Report pages discovered, fetched, and failed; sections extracted; coordinate-bearing and unlocated entries; approximate entries; and links with or without valid anchors. Reconcile differences from the homepage count through failed pages, parsing gaps, duplicates, and source changes. Do not assume any difference is harmless.

### Step 5  Validate identities and coordinates

Check numeric ranges, coordinate order, and consistency with the record’s state or territory. Use review flags rather than rejecting every geographic outlier; island and territorial entries need appropriate bounds. Treat aliases as one record, while preserving distinct original and replacement airport locations. Nearby coordinates alone are insufficient evidence to merge records.

Keep corrections in a separate reviewed overrides file, with reason and supporting source. Generate GeoJSON and a coverage report only after applying these checks. Missing coordinates remain null rather than becoming a city centroid or a point at zero latitude and longitude.

## Build the web map and verify interaction

### Step 6  Create the map interface

Load the generated GeoJSON and display markers on a responsive map. Fit the initial view to the main US coverage, with a clear way to reach Alaska, Hawaii, territories, and other catalog regions. Cluster crowded markers. Clicking a cluster zooms or expands it; clicking an individual marker opens the corresponding source_url in a new tab.

Use a visible hover label on desktop and an accessible marker name. Include a search results list that remains usable on mobile and by keyboard. Each result offers a Locate action to center the map and a linked airport name that opens the source entry. Include state or territory and location-quality filters, a result count, and an unlocated entries view with working source links.

### Step 7  Make source navigation reliable

Open the link directly from the user’s click, rather than after an asynchronous fetch, to avoid browser popup blocking. Use a safe external-link configuration such as target="_blank" with rel="noopener noreferrer". Validate allowed source URLs and escape all scraped labels. Announce that airport links open a new tab. A nearby source credit should name Paul Freeman and link to the original website.

The marker click should navigate immediately. Any optional preview must not require a second click before opening the source. Do not embed the source website in an iframe or duplicate its historical narratives and image galleries in the initial release.

### Step 8  Show uncertainty clearly

Use distinguishable marker styling for approximate positions, with a textual legend so meaning does not depend on color alone. Keep “coordinates supplied by source” separate from “location independently reviewed”. A marker represents an airport location, not its property boundary or a usable runway. Include a concise historical-map label explaining that the map does not establish landing suitability or access permission.

### Step 9  Run release checks

Verify representative records from every parser layout, including integer coordinates, aliases, relocated airports, absent anchors, uncertain locations, and missing coordinates. Spot-check positions against the source text and available imagery. Test GeoJSON longitude-first order explicitly.

Test marker and result links on desktop and mobile, keyboard navigation, filter and search combinations, cluster expansion, empty results, and basemap or dataset loading failures. Confirm anchor targets within cached source HTML, then manually open a representative set of live entry links. Check the full page inventory for unresolved fetch or parse failures before calling coverage complete.

### Step 10  Publish the first release

Deploy the static app and dataset together. Display the dataset refresh date, mapped and unlocated counts, source attribution, and a way to report an incorrect location or link. Retain the last successful dataset and an easy rollback. Release readiness means every extracted record is either mapped or explicitly unlocated, source navigation works, and coverage limitations are visible.

## Resolve uncertain sites and maintain the map

### Step 11  Investigate only the exceptions

Prioritize entries with missing coordinates, explicit uncertainty, geographic conflicts, or coarse locations. The original Westwood Airport is a useful example: its page provides coordinates but states that its precise location has not been determined. Its marker should therefore remain approximate until additional evidence supports a better position.

Read the narrative for road intersections, distances, nearby towns, waterways, and historical chart years. Prefer the original full map over a cropped illustration. USGS topoView supplies historical maps as georeferenced GeoTIFFs, which can be overlaid on current maps without manually aligning each image.

For an unreferenced chart or aerial image, identify several stable control points distributed around the airfield, such as road intersections, railway crossings, and river junctions. Georeference it in GIS software, check alignment using additional landmarks, and transform the result to WGS84. Account for changed roads, shifted shorelines, old coordinate datums, and the limited precision of airport symbols on small-scale charts.

Record the derived point, source image and year, alignment method, independent check, and justified uncertainty. If the evidence supports only an area, retain an approximate point with an uncertainty note or an area overlay. Keep conflicting candidate locations under review rather than selecting one silently.

### Step 12  Add optional historical layers

Once point coverage is satisfactory, digitize runway centerlines or airport footprints from aligned historical maps. Keep these geometries separate from the marker dataset and label their dates. A historical overlay toggle can reveal the former layout beneath current development. Opening and closure filters can follow, but preserve date ranges and unknown dates instead of converting them into invented exact years.

### Step 13  Refresh without losing corrections

Run periodic extraction as a separate maintenance job. Compare new records, changed coordinates, renamed fields, and removed links with the previous dataset. Apply reviewed overrides after extraction. Flag large location changes and unexpected drops in record count for review before publishing. An unsuccessful refresh must leave the current map and dataset intact.

## Source references

Freeman homepage and catalog count
https://airfields-freeman.com/

Marin County coordinate examples
https://airfields-freeman.com/CA/Airfields_CA_SanRafael.htm

Northeastern California formatting and Westwood uncertainty
https://airfields-freeman.com/CA/Airfields_CA_NE.htm

Big Bend coordinate examples
https://airfields-freeman.com/TX/Airfields_TX_BigBend.htm

Western Massachusetts coordinate examples
https://airfields-freeman.com/MA/Airfields_MA_W.htm

USGS topoView georeferenced downloads
https://ngmdb.usgs.gov/topoview/help/
