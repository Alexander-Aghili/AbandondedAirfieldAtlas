# AbandondedAirfieldAtlas

An interactive map of [Paul Freeman’s Abandoned & Little-Known Airfields](https://airfields-freeman.com/) catalog. Search airfields, filter locations, switch between street and satellite imagery, and open original source entries.

Website (coming soon): [alexanderaghili.com/abandoded-airfield-atlas](https://alexanderaghili.com/abandoded-airfield-atlas).

## Run

```sh
python3 -m http.server 8000 --directory web
```

Open http://localhost:8000. The dataset is included; no build or backend is required. Maps and fonts require internet access.

## Update data

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pipeline.extract
```

The crawler discovers linked catalog pages automatically, caches HTML, and writes GeoJSON and a coverage report to `web/data/`. Use `--offline` to rebuild from cache or `--refresh` to fetch updated pages. Failed crawls preserve the published dataset.

Source coordinates are not independently verified. Approximate and unlocated entries are identified explicitly; coverage discrepancies remain in `coverage.json`.

## Code and checks

`pipeline/` separates fetching, parsing, crawling, reconciliation, and publication. `web/js/` separates catalog filtering, map controls, results, and application coordination.

```sh
.venv/bin/python -m unittest discover -s tests
.venv/bin/python -m pipeline.validate
node --test tests/*.test.mjs
```
