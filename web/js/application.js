import { ResultsView } from "./results.js";
import { $, num } from "./dom.js";
import { AirfieldCatalog } from "./catalog.js";
import { AirfieldMap } from "./map.js";
import { PAGE_SIZE } from "./constants.js";
export class AirfieldApplication {
  constructor() {
    this.visible = [];
    this.limit = PAGE_SIZE;
    this.selected = null;
    this.updating = false;
    this.mapView = new AirfieldMap(this);
    this.results = new ResultsView(this);
  }
  get features() {
    return this.catalog?.features || [];
  }
  resetResults() {
    this.limit = PAGE_SIZE;
    this.selected = null;
    this.render();
  }
  message(text) {
    $("map-error-text").textContent = text;
    $("map-error").hidden = false;
  }
  saveState() {
    if (this.updating) return;
    const p = new URLSearchParams();
    for (const [key, id] of [
      ["q", "search"],
      ["state", "state"],
      ["quality", "quality"],
    ])
      if ($(id).value) p.set(key, $(id).value);
    if ($("in-view").checked) p.set("inview", "1");
    if (this.mapView.activeLayer === "satellite") p.set("layer", "satellite");
    if (this.mapView.map) {
      const c = this.mapView.map.getCenter();
      p.set("lat", c.lat.toFixed(4));
      p.set("lon", c.lng.toFixed(4));
      p.set("z", this.mapView.map.getZoom());
    }
    history.replaceState(
      null,
      "",
      `${location.pathname}${p.size ? "?" + p : ""}${location.hash}`,
    );
  }

  render(updateMap = true) {
    const q = $("search").value.trim().toLowerCase(),
      bounds = this.mapView.map?.getBounds();
    const matching = this.catalog.filter({
      query: q,
      state: $("state").value,
      quality: $("quality").value,
    });
    this.visible = matching.filter(
      (f) =>
        !$("in-view").checked ||
        !this.mapView.map ||
        (f.geometry &&
          bounds.contains([
            f.geometry.coordinates[1],
            f.geometry.coordinates[0],
          ])),
    );
    if (updateMap && this.mapView.clusters) {
      this.mapView.clusters.clearLayers();
      this.mapView.clusters.addLayers(
        matching
          .filter((f) => f.geometry)
          .map((f) => this.mapView.markers.get(f.id)),
      );
    }
    this.results.render();
    const unlocated = this.visible.filter((f) => !f.geometry).length;
    $("status").textContent =
      `${num(this.visible.length)} ${this.visible.length === 1 ? "airfield" : "airfields"}${unlocated ? ` · ${num(unlocated)} unlocated` : ""}`;
    this.saveState();
  }
  restore() {
    this.updating = true;
    const p = new URLSearchParams(location.search);
    $("search").value = p.get("q") || "";
    for (const key of ["state", "quality"]) $(key).value = p.get(key) || "";
    $("in-view").checked = p.get("inview") === "1";
    if (this.mapView.map) {
      const lat = Number(p.get("lat")),
        lon = Number(p.get("lon")),
        z = Number(p.get("z"));
      if (
        p.has("lat") &&
        p.has("lon") &&
        p.has("z") &&
        Number.isFinite(lat) &&
        Number.isFinite(lon) &&
        Math.abs(lat) <= 85 &&
        Math.abs(lon) <= 180 &&
        z >= 2 &&
        z <= 19
      )
        this.mapView.map.setView([lat, lon], z);
    }
    this.mapView.setLayer(p.get("layer") || "map");
    this.updating = false;
    this.render();
  }
  async init() {
    this.bindPageControls();
    try {
      const response = await fetch("data/airfields.geojson");
      if (!response.ok)
        throw new Error("The catalog could not load. Reload to try again.");
      const data = await response.json();
      this.catalog = new AirfieldCatalog(data);
      this.displayCatalog(data.metadata);
      try {
        this.mapView.setupMap();
      } catch (error) {
        this.message(error.message || String(error));
        $("in-view").disabled = true;
        for (const id of ["street", "satellite", "fit", "view"])
          $(id).disabled = true;
      }
      this.bindCatalogControls();
      this.restore();
    } catch (error) {
      $("status").textContent = error.message || String(error);
      this.message(error.message || String(error));
      $("refresh").textContent = "Dataset unavailable";
    }
  }
  bindPageControls() {
    matchMedia("(max-width: 760px)").addEventListener("change", (e) => {
      if (!e.matches) {
        $("result-scroll").hidden = false;
        $("toggle-results").setAttribute("aria-expanded", "true");
        $("toggle-results").textContent = "Hide list";
      }
    });
    $("about").onclick = () => $("about-dialog").showModal();
    $("close-about").onclick = () => $("about-dialog").close();
    $("about-dialog").onclick = (e) => {
      if (e.target === $("about-dialog")) {
        const r = $("about-dialog").getBoundingClientRect();
        if (
          e.clientX < r.left ||
          e.clientX > r.right ||
          e.clientY < r.top ||
          e.clientY > r.bottom
        )
          $("about-dialog").close();
      }
    };
    $("dismiss-error").onclick = () => ($("map-error").hidden = true);
    $("toggle-results").onclick = () => {
      const expanded =
        $("toggle-results").getAttribute("aria-expanded") === "true";
      $("toggle-results").setAttribute("aria-expanded", String(!expanded));
      $("toggle-results").textContent = expanded ? "Show list" : "Hide list";
      $("result-scroll").hidden = expanded;
    };
    document.addEventListener("keydown", (e) => {
      if (
        e.key === "/" &&
        !["INPUT", "TEXTAREA", "SELECT"].includes(
          document.activeElement.tagName,
        ) &&
        !$("about-dialog").open
      ) {
        e.preventDefault();
        $("search").focus();
      }
    });
  }
  displayCatalog(metadata) {
    const states = new Map(
      this.features.map((f) => [
        f.properties.state,
        f.properties.state_name || f.properties.state,
      ]),
    );
    for (const [state, name] of [...states.entries()].sort((a, b) =>
      a[1].localeCompare(b[1]),
    )) {
      const o = document.createElement("option");
      o.value = state;
      o.textContent = name;
      $("state").append(o);
    }
    $("total-stat").textContent = num(this.features.length);
    $("mapped-stat").textContent = num(
      this.features.filter((f) => f.geometry).length,
    );
    const meta = metadata,
      stamp = new Date(meta.generated_at).toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
        year: "numeric",
      });
    $("refresh").textContent =
      `Updated ${stamp} · ${meta.coverage_complete ? "Catalog reconciled" : "Source discrepancies noted"}`;
    const coverage = [
      `${num(meta.total)} entries: ${num(meta.mapped)} mapped and ${num(meta.unlocated)} unlocated.`,
      `${num(meta.approximate)} approximate positions; ${num(meta.links_without_anchor)} links open a regional source page.`,
    ];
    if (meta.advertised_count) {
      coverage.push(
        `The source lists ${num(meta.advertised_count)} airfields; extracted airport sections differ by ${meta.count_difference}.`,
      );
    }
    if (meta.index_only_entries) {
      coverage.push(
        `${num(meta.index_only_entries)} source-index entries have no available airport section and remain unlocated.`,
      );
    }
    coverage.push(
      meta.coverage_complete
        ? "Counts and parsing checks reconcile."
        : "Coverage discrepancies are recorded in the extraction report.",
    );
    $("coverage").textContent = coverage.join(" ");
  }
  bindCatalogControls() {
    for (const id of ["search", "state", "quality", "in-view"])
      $(id).addEventListener(id === "search" ? "input" : "change", () => {
        this.resetResults();
        $("result-scroll").scrollTop = 0;
      });
    $("more").onclick = () => {
      this.limit += PAGE_SIZE;
      this.results.render();
    };
    $("reset").onclick = () => {
      $("search").value = "";
      $("state").value = "";
      $("quality").value = "";
      $("in-view").checked = false;
      this.resetResults();
    };
    $("street").onclick = () => this.mapView.setLayer("map");
    $("satellite").onclick = () => this.mapView.setLayer("satellite");
    $("fit").onclick = this.mapView.fit.bind(this.mapView);
    $("view").onchange = () => {
      if ($("view").value === "all") {
        this.mapView.fit();
        return;
      }
      const views = {
        us: [[38, -98], 4],
        ak: [[64, -152], 4],
        hi: [[20.8, -157], 6],
        pacific: [[13, 145], 4],
        territories: [[18.2, -66.4], 8],
      };
      const [center, zoom] = views[$("view").value];
      this.mapView.map?.setView(center, zoom);
    };
    window.addEventListener("popstate", this.restore.bind(this));
  }
}
