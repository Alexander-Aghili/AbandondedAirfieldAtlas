import test from "node:test";
import assert from "node:assert/strict";
import { AirfieldCatalog } from "../web/js/catalog.js";
import { validSource } from "../web/js/dom.js";
const record = (id, name, state, quality, geometry = null) => ({
  id,
  geometry,
  properties: {
    name,
    state,
    location_quality: quality,
    aliases: ["Old " + name],
    region: "Northern region",
    state_name: state === "CA" ? "California" : "Texas",
  },
});
const data = {
  type: "FeatureCollection",
  features: [
    record("b", "Beta Field", "TX", "missing"),
    record("a", "Alpha Airport", "CA", "approximate", {
      type: "Point",
      coordinates: [-120, 38],
    }),
  ],
};
test("search covers aliases and full state names without modifying source data", () => {
  const before = JSON.stringify(data),
    catalog = new AirfieldCatalog(data);
  assert.deepEqual(
    catalog.filter({ query: " OLD ALPHA " }).map((f) => f.id),
    ["a"],
  );
  assert.deepEqual(
    catalog.filter({ query: "california" }).map((f) => f.id),
    ["a"],
  );
  assert.equal(JSON.stringify(data), before);
});
test("filters combine and keep unlocated records searchable", () => {
  const catalog = new AirfieldCatalog(data);
  assert.deepEqual(catalog.filter({ state: "CA", quality: "missing" }), []);
  assert.deepEqual(
    catalog.filter({ query: "beta", quality: "missing" }).map((f) => f.id),
    ["b"],
  );
  assert.equal(catalog.filter({ query: "not found" }).length, 0);
  assert.deepEqual(
    catalog.features.map((f) => f.id),
    ["a", "b"],
  );
});
test("invalid collection fails with a useful error", () =>
  assert.throws(
    () => new AirfieldCatalog({ type: "Point" }),
    /dataset format/,
  ));
test("source links reject hostile URLs and credentials", () => {
  assert.equal(
    validSource("https://airfields-freeman.com/CA/Airfields_CA.htm#field"),
    true,
  );
  for (const url of [
    "javascript:alert(1)",
    "https://airfields-freeman.com.evil.org/",
    "https://user:pass@airfields-freeman.com/",
    "not a URL",
  ])
    assert.equal(validSource(url), false);
});
