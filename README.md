```markdown
# 🌐 H3 4D Spacetime Tensor Fabric

An autonomous data plane running entirely on GitHub Actions. It ingests global real-world physical telemetry, maps coordinates to Uber H3 discrete hexagonal spatial cells, segments events by vertical altitude/depth bands, and buckets them into hourly temporal bins.

## Multi-Dimensional Indexing
- **Spatial Dimension**: Uber H3 Discrete Global Grid (Resolution 6)
- **Vertical Dimension**: `ATMOSPHERE_LOW`, `CRUST_SHALLOW`, `CRUST_MID`, `MANTLE_TRANSITION`, `MANTLE_DEEP`
- **Temporal Dimension**: ISO-8601 hourly discrete windows (`YYYY-MM-DDTHH:00:00Z`)
- **Query Efficiency**: Supports remote HTTP byte-range queries directly over `spacetime.parquet`.

## Machine Feeds
- [`v1/active-cells.json`](public/v1/active-cells.json) (All active 4D coordinate cells)
- [`v1/high-impact-slices.json`](public/v1/high-impact-slices.json) (Significant anomaly slices)
- [`llms.txt`](public/llms.txt) (Token-efficient LLM digest)
- `spacetime.parquet` (Columnar Parquet 4D database)

## Architecture
- **Source**: USGS Global Geodynamics & Seismic Feeds
- **Coordinate Transformation**: Uber H3 + Python
- **Database**: DuckDB + Parquet
- **Ledger**: Append-only Git-committed JSONL in `/data/history`
- **Edge CDN**: GitHub Pages (Fastly CDN) 