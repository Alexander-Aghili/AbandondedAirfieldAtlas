import { PAGE_SIZE } from "./constants.js";
import { $, num, validSource } from "./dom.js";
export class AirfieldMap {
  constructor(app) {
    this.app = app;
    this.map = null;
    this.clusters = null;
    this.markers = new Map();
    this.activeLayer = "map";
    this.layers = {};
  }
  locate(f) {
    if (!this.map) return;
    this.app.selected = f.id;
    const m = this.markers.get(f.id);
    if (!m) return;
    this.clusters.zoomToShowLayer(m, () => {
      this.map.setView(m.getLatLng(), Math.max(this.map.getZoom(), 14), {
        animate: !matchMedia("(prefers-reduced-motion: reduce)").matches,
      });
      m.openTooltip();
    });
    this.app.results.render();
  }
  setLayer(name) {
    this.activeLayer = name === "satellite" ? "satellite" : "map";
    if (this.map) {
      for (const layer of Object.values(this.layers))
        if (this.map.hasLayer(layer)) this.map.removeLayer(layer);
      this.layers[this.activeLayer].addTo(this.map);
      $("map-error").hidden = true;
    }
    $("street").setAttribute(
      "aria-pressed",
      String(this.activeLayer === "map"),
    );
    $("satellite").setAttribute(
      "aria-pressed",
      String(this.activeLayer === "satellite"),
    );
    this.app.saveState();
  }
  fit() {
    if (!this.map) return;
    const points = this.app.visible
      .filter((f) => f.geometry)
      .map((f) => [f.geometry.coordinates[1], f.geometry.coordinates[0]]);
    if (points.length)
      this.map.fitBounds(points, { padding: [65, 65], maxZoom: 14 });
    else this.app.message("No mapped locations match the current filters.");
  }
  setupMap() {
    if (!window.L || !L.markerClusterGroup)
      throw new Error(
        "The map could not load. You can still search the catalog and open source entries.",
      );
    this.map = L.map("map", {
      maxZoom: 19,
      minZoom: 2,
      zoomControl: true,
      worldCopyJump: true,
    }).setView([38, -98], 4);
    this.clusters = L.markerClusterGroup({
      showCoverageOnHover: false,
      removeOutsideVisibleBounds: true,
      maxClusterRadius: 48,
      iconCreateFunction: (cluster) =>
        L.divIcon({
          html: `<span class="cluster-disc ${cluster.getChildCount() >= 100 ? "large" : ""}">${num(cluster.getChildCount())}</span>`,
          className: "airfield-cluster",
          iconSize: [48, 48],
        }),
    });
    this.map.addLayer(this.clusters);
    this.layers.map = L.tileLayer(
      "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
      {
        maxZoom: 19,
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      },
    );
    this.layers.satellite = L.tileLayer(
      "https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      {
        maxZoom: 19,
        attribution:
          'Imagery &copy; <a href="https://www.arcgis.com/home/item.html?id=10df2279f9684e4a9f6a7f08febac2a9">Esri</a>, Vantor, Earthstar Geographics & GIS User Community',
      },
    );
    for (const [name, layer] of Object.entries(this.layers))
      layer.on("tileerror", () => {
        if (this.activeLayer === name)
          this.app.message(
            `${name === "satellite" ? "Satellite imagery" : "Map tiles"} are unavailable. Try the other basemap; catalog links remain available.`,
          );
      });
    for (const f of this.app.features) {
      if (!f.geometry) continue;
      const p = f.properties,
        [lon, lat] = f.geometry.coordinates;
      const m = L.marker([lat, lon], {
        title: `${p.name} (opens source in a new tab)`,
        alt: p.name,
        keyboard: true,
        icon: L.divIcon({
          html: `<span class="dot ${p.location_quality === "approximate" ? "approximate" : ""}"></span>`,
          className: "airfield-marker",
          iconSize: [28, 28],
          iconAnchor: [14, 14],
        }),
      });
      const label = document.createElement("div"),
        title = document.createElement("span"),
        quality = document.createElement("small");
      title.textContent = p.name;
      quality.textContent = `${p.location_quality} · Open source entry ↗`;
      label.append(title, quality);
      m.bindTooltip(label, { direction: "top", offset: [0, -10] });
      m.on("click", () => {
        if (validSource(p.source_url))
          window.open(p.source_url, "_blank", "noopener,noreferrer");
      });
      this.markers.set(f.id, m);
    }
    this.map.on("moveend", () => {
      const c = this.map.getCenter();
      $("map-location").textContent =
        `${Math.abs(c.lat).toFixed(2)}° ${c.lat >= 0 ? "N" : "S"}   ${Math.abs(c.lng).toFixed(2)}° ${c.lng >= 0 ? "E" : "W"}`;
      if ($("in-view").checked) {
        this.app.limit = PAGE_SIZE;
        this.app.render(false);
      } else this.app.saveState();
    });
  }
}
