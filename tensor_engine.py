import os
import json
import hashlib
import duckdb
import requests
import h3
from datetime import datetime, timezone

DB_FILE = "data/spacetime_tensor.db"
HISTORY_DIR = "data/history"
EXPORT_DIR = "public"
API_DIR = os.path.join(EXPORT_DIR, "v1")

# USGS Real-Time Global Seismic & Geodynamics Feed (Authoritative, Zero-Auth)
USGS_SEISMIC_FEED = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson"
H3_RESOLUTION = 6

def compute_hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()

def classify_vertical_layer(depth_km: float) -> str:
    """Classifies vertical altitude/depth layer across 4D spacetime."""
    if depth_km < 0:
        return "ATMOSPHERE_LOW"
    elif depth_km <= 10.0:
        return "CRUST_SHALLOW"
    elif depth_km <= 70.0:
        return "CRUST_MID"
    elif depth_km <= 300.0:
        return "MANTLE_TRANSITION"
    else:
        return "MANTLE_DEEP"

def round_time_bucket(epoch_ms: int) -> str:
    """Rounds epoch milliseconds to hourly temporal buckets."""
    dt = datetime.fromtimestamp(epoch_ms / 1000.0, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:00:00Z")

def fetch_spatial_events():
    events = []
    headers = {"User-Agent": "H3-4D-Spacetime-Tensor/1.0"}
    try:
        r = requests.get(USGS_SEISMIC_FEED, headers=headers, timeout=20)
        if r.status_code == 200:
            features = r.json().get("features", [])
            for feat in features:
                props = feat.get("properties", {})
                geom = feat.get("geometry", {})
                coords = geom.get("coordinates", [])
                
                if len(coords) < 3:
                    continue

                lon = float(coords[0])
                lat = float(coords[1])
                depth = float(coords[2])
                mag = float(props.get("mag") or 0.0)
                epoch_time = int(props.get("time", 0))

                # Compute Spatial H3 Cell
                cell = h3.geo_to_h3(lat, lon, H3_RESOLUTION)
                v_layer = classify_vertical_layer(depth)
                t_bucket = round_time_bucket(epoch_time)
                
                # 4D Spacetime Coordinate Key: [H3:Layer:Time]
                tensor_coord = f"{cell}:{v_layer}:{t_bucket}"

                feature_vector = [
                    round(mag, 2),
                    round(depth, 2),
                    int(props.get("sig") or 0),
                    round(float(props.get("rms") or 0.0), 3)
                ]

                events.append({
                    "tensor_coord": tensor_coord,
                    "h3_index": cell,
                    "resolution": H3_RESOLUTION,
                    "latitude": round(lat, 4),
                    "longitude": round(lon, 4),
                    "depth_altitude_layer": v_layer,
                    "time_bucket_utc": t_bucket,
                    "event_type": str(props.get("type", "earthquake")),
                    "magnitude": mag,
                    "feature_vector": feature_vector,
                    "observed_at_utc": datetime.fromtimestamp(epoch_time / 1000.0, tz=timezone.utc).isoformat()
                })
    except Exception as e:
        print(f"Error fetching spatial feeds: {e}")
    return events

def build_static_api(conn):
    os.makedirs(API_DIR, exist_ok=True)
    now_iso = datetime.now(timezone.utc).isoformat()

    cur = conn.execute("SELECT * FROM spacetime_tensor ORDER BY observed_at_utc DESC")
    cols = [desc[0] for desc in cur.description]
    all_cells = [dict(zip(cols, row)) for row in cur.fetchall()]

    for c in all_cells:
        c["feature_vector"] = json.loads(c["feature_vector_json"])
        del c["feature_vector_json"]

    with open(os.path.join(API_DIR, "active-cells.json"), "w", encoding="utf-8") as f:
        json.dump({"metadata": {"updated_at": now_iso, "count": len(all_cells)}, "tensor_cells": all_cells}, f, indent=2)

    # 4D Slice: High Magnitude Events (Magnitude >= 3.5)
    high_mag = [c for c in all_cells if c["magnitude"] >= 3.5]
    with open(os.path.join(API_DIR, "high-impact-slices.json"), "w", encoding="utf-8") as f:
        json.dump({"metadata": {"updated_at": now_iso, "count": len(high_mag)}, "high_impact_cells": high_mag}, f, indent=2)

    lines = [
        "# H3 4D Spacetime Tensor Fabric",
        f"> Last Sync: {now_iso} UTC",
        "> Metric: 4D Spacetime Bins [H3_Resolution_6 : Vertical_Layer : Time_Bucket : Feature_Vector]",
        "",
        "## Top Active 4D Coordinate Cells"
    ]
    for c in high_mag[:20]:
        lines.append(
            f"- **`{c['tensor_coord']}`** (M{c['magnitude']:.1f} | {c['depth_altitude_layer']}): "
            f"Coords ({c['latitude']}, {c['longitude']}) | Vector: `{c['feature_vector']}`"
        )

    with open(os.path.join(EXPORT_DIR, "llms.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    html = f"""<!DOCTYPE html><html><head><title>H3 4D Spacetime Tensor Fabric</title></head>
    <body style='font-family:system-ui,sans-serif;max-width:900px;margin:2rem auto;line-height:1.6;padding:0 1rem;'>
    <h1>🌐 H3 4D Spacetime Tensor Fabric</h1>
    <p>Hierarchical 4D space-time-altitude tensor indexing physical planetary telemetry for AI agents.</p>
    <h3>Machine Feeds</h3>
    <ul>
      <li><a href='v1/active-cells.json'>/v1/active-cells.json</a> (Active 4D Spacetime Cells)</li>
      <li><a href='v1/high-impact-slices.json'>/v1/high-impact-slices.json</a> (High-Impact Anomaly Slices)</li>
      <li><a href='llms.txt'>llms.txt</a> (Token-Efficient Digest)</li>
      <li><a href='spacetime.parquet'>spacetime.parquet</a> (Queryable Columnar 4D Tensor)</li>
    </ul>
    <h3>Latest 4D Coordinate Intersections</h3>
    <table border="1" cellpadding="6" style="border-collapse:collapse;width:100%;text-align:left;">
      <tr><th>Tensor Coordinate</th><th>H3 Index</th><th>Vertical Layer</th><th>Time Bucket</th><th>Magnitude</th></tr>
      {"".join([f"<tr><td><code>{c['tensor_coord']}</code></td><td>{c['h3_index']}</td><td>{c['depth_altitude_layer']}</td><td>{c['time_bucket_utc']}</td><td><strong>M{c['magnitude']:.1f}</strong></td></tr>" for c in all_cells[:12]])}
    </table>
    </body></html>"""
    with open(os.path.join(EXPORT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)

def run():
    os.makedirs("data", exist_ok=True)
    os.makedirs(HISTORY_DIR, exist_ok=True)
    os.makedirs(EXPORT_DIR, exist_ok=True)

    conn = duckdb.connect(DB_FILE)
    with open("schema.sql", "r", encoding="utf-8") as f:
        conn.execute(f.read())

    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    date_str = now.strftime("%Y-%m-%d")
    year_str = now.strftime("%Y")
    month_str = now.strftime("%m")

    month_dir = os.path.join(HISTORY_DIR, year_str, month_str)
    os.makedirs(month_dir, exist_ok=True)
    daily_history_file = os.path.join(month_dir, f"{date_str}.jsonl")

    events = fetch_spatial_events()

    conn.execute("BEGIN TRANSACTION")

    for ev in events:
        coord = ev["tensor_coord"]
        cell = ev["h3_index"]
        res = ev["resolution"]
        lat = ev["latitude"]
        lon = ev["longitude"]
        layer = ev["depth_altitude_layer"]
        t_bucket = ev["time_bucket_utc"]
        e_type = ev["event_type"].replace("'", "''")
        mag = ev["magnitude"]
        vec_json = json.dumps(ev["feature_vector"])
        obs_utc = ev["observed_at_utc"]

        h_payload = {"coord": coord, "mag": mag, "vec": ev["feature_vector"]}
        content_hash = compute_hash(h_payload)

        existing = conn.execute(f"SELECT content_hash FROM spacetime_tensor WHERE tensor_coord = '{coord}'").fetchone()

        if not existing:
            conn.execute(f"""
                INSERT INTO spacetime_tensor (
                    tensor_coord, h3_index, resolution, latitude, longitude,
                    depth_altitude_layer, time_bucket_utc, event_type, magnitude,
                    feature_vector_json, content_hash, observed_at_utc
                ) VALUES (
                    '{coord}', '{cell}', {res}, {lat}, {lon},
                    '{layer}', '{t_bucket}', '{e_type}', {mag},
                    '{vec_json}', '{content_hash}', '{obs_utc}'
                )
            """)

            commit_id = conn.execute("SELECT nextval('seq_commit_id')").fetchone()[0]
            conn.execute(f"""
                INSERT INTO tensor_ledger (commit_id, timestamp_utc, operation, tensor_coord, h3_index, detail)
                VALUES ({commit_id}, '{now_iso}', 'INSERT_4D_CELL', '{coord}', '{cell}', 'Observed physical event indexed')
            """)

            entry = {
                "commit_id": commit_id, "timestamp_utc": now_iso, "operation": "INSERT_4D_CELL",
                "tensor_coord": coord, "h3_index": cell, "magnitude": mag, "content_hash": content_hash
            }
            with open(daily_history_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")

        elif existing[0] != content_hash:
            conn.execute(f"""
                UPDATE spacetime_tensor SET
                    magnitude = {mag},
                    feature_vector_json = '{vec_json}',
                    content_hash = '{content_hash}',
                    observed_at_utc = '{obs_utc}'
                WHERE tensor_coord = '{coord}'
            """)

            commit_id = conn.execute("SELECT nextval('seq_commit_id')").fetchone()[0]
            conn.execute(f"""
                INSERT INTO tensor_ledger (commit_id, timestamp_utc, operation, tensor_coord, h3_index, detail)
                VALUES ({commit_id}, '{now_iso}', 'UPDATE_4D_CELL', '{coord}', '{cell}', 'Cell features updated')
            """)

            entry = {
                "commit_id": commit_id, "timestamp_utc": now_iso, "operation": "UPDATE_4D_CELL",
                "tensor_coord": coord, "h3_index": cell, "magnitude": mag, "content_hash": content_hash
            }
            with open(daily_history_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")

    conn.execute("COMMIT")

    conn.execute(f"COPY (SELECT tensor_coord, h3_index, resolution, latitude, longitude, depth_altitude_layer, time_bucket_utc, event_type, magnitude, feature_vector_json, observed_at_utc FROM spacetime_tensor) TO '{EXPORT_DIR}/spacetime.parquet' (FORMAT PARQUET)")
    build_static_api(conn)
    conn.close()

if __name__ == "__main__":
    run()
