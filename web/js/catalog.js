/** Immutable source records with a reusable search index. */
export class AirfieldCatalog {
  constructor(data) {
    if (data.type !== "FeatureCollection" || !Array.isArray(data.features)) {
      throw new Error("The dataset format is invalid.");
    }
    this.features = [...data.features].sort((a, b) =>
      a.properties.name.localeCompare(b.properties.name),
    );
    this.searchIndex = new Map(
      this.features.map((feature) => {
        const p = feature.properties;
        return [
          feature.id,
          [p.name, ...(p.aliases || []), p.region, p.state, p.state_name]
            .join(" ")
            .toLowerCase(),
        ];
      }),
    );
  }
  filter({ query = "", state = "", quality = "" } = {}) {
    const term = query.trim().toLowerCase();
    return this.features.filter((feature) => {
      const p = feature.properties;
      return (
        (!term || this.searchIndex.get(feature.id).includes(term)) &&
        (!state || p.state === state) &&
        (!quality || p.location_quality === quality)
      );
    });
  }
}
