import { $, num, sourceLink } from "./dom.js";
import { PAGE_SIZE } from "./constants.js";
export class ResultsView {
  constructor(app) {
    this.app = app;
  }
  render() {
    const fragment = document.createDocumentFragment();
    if (!this.app.visible.length) {
      const li = document.createElement("li");
      li.className = "empty-results";
      li.textContent =
        "No airfields match this view. Try another name or reset the filters.";
      fragment.append(li);
    }
    for (const [i, f] of this.app.visible.slice(0, this.app.limit).entries()) {
      const p = f.properties,
        li = document.createElement("li");
      if (this.app.selected === f.id) li.classList.add("selected");
      const index = document.createElement("div");
      index.className = "result-index";
      const state = document.createElement("span");
      state.textContent = (p.state_name || p.state).toUpperCase();
      const number = document.createElement("span");
      number.textContent = String(i + 1).padStart(3, "0");
      index.append(state, number);
      li.append(index, sourceLink(p));
      const meta = document.createElement("span");
      meta.className = "result-meta";
      meta.textContent = p.region;
      li.append(meta);
      if (f.geometry && this.app.mapView.map) {
        const b = document.createElement("button");
        b.className = "locate-button";
        b.textContent = "Locate";
        b.setAttribute("aria-label", `Locate ${p.name}`);
        b.onclick = () => this.app.mapView.locate(f);
        li.append(b);
      }
      const note = document.createElement("div");
      note.className = "result-note";
      const dot = document.createElement("i");
      dot.className = `quality-dot ${p.location_quality === "approximate" ? "approximate" : !f.geometry ? "missing" : ""}`;
      dot.setAttribute("aria-hidden", "true");
      const label = document.createElement("span");
      label.textContent = !f.geometry
        ? "No source coordinates"
        : p.location_quality === "approximate"
          ? "Approximate position"
          : p.location_quality === "reviewed"
            ? "Independently reviewed"
            : "Coordinates supplied by source";
      note.append(dot, label);
      li.append(note);
      if (p.record_origin === "index only") {
        const missing = document.createElement("div");
        missing.className = "result-note";
        missing.textContent =
          "Listed in the source index; airport section unavailable.";
        li.append(missing);
      }
      if (p.catalog_membership === "linked historical page") {
        const older = document.createElement("div");
        older.className = "result-note";
        older.textContent = "Older linked source page";
        li.append(older);
      }
      fragment.append(li);
    }
    $("results").replaceChildren(fragment);
    $("more").hidden = this.app.visible.length <= this.app.limit;
    $("more").textContent =
      `Show ${num(Math.min(PAGE_SIZE, this.app.visible.length - this.app.limit))} more airfields`;
  }
}
