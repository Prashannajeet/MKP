from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "outputs" / "drone_geotags"
DGPS_GEOJSON = DATA_DIR / "mohanpura_dgps_bm_tbm.geojson"
SUMMARY_JSON = DATA_DIR / "summary.json"
SOURCE_WEBMAP = DATA_DIR / "drone_photo_webmap.html"
STATIC_DIR = ROOT / "static"
STATIC_WEBMAP = STATIC_DIR / "drone_photo_webmap.html"


st.set_page_config(
    page_title="Mohanpura Drone Coverage",
    layout="wide",
)


st.markdown(
    """
    <style>
    .block-container { padding: .75rem .9rem 1rem; max-width: 100%; }
    h1 { font-size: 1.45rem; letter-spacing: 0; margin-bottom: .35rem; }
    [data-testid="stMetric"] {
      background: #f8fafb;
      border: 1px solid #d9e1e8;
      border-radius: 6px;
      padding: 8px 10px;
    }
    [data-testid="stMetricLabel"] { color: #52616d; }
    .source-note {
      color: #52616d;
      font-size: .86rem;
      margin-top: -.2rem;
      margin-bottom: .65rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_static_webmap() -> None:
    STATIC_DIR.mkdir(exist_ok=True)
    if not STATIC_WEBMAP.exists() or STATIC_WEBMAP.stat().st_mtime < SOURCE_WEBMAP.stat().st_mtime:
        STATIC_WEBMAP.write_text(SOURCE_WEBMAP.read_text(encoding="utf-8"), encoding="utf-8")


def normalized_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def pick_column(fieldnames: list[str], choices: set[str]) -> str | None:
    lookup = {normalized_name(name): name for name in fieldnames}
    for choice in choices:
        if choice in lookup:
            return lookup[choice]
    return None


def parse_uploaded_csv(raw: bytes) -> list[list[float | str]]:
    text = raw.decode("utf-8-sig", errors="replace")
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample)
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        raise ValueError("CSV has no header row.")

    lat_col = pick_column(reader.fieldnames, {"lat", "latitude", "gpslat", "gpslatitude", "y"})
    lon_col = pick_column(reader.fieldnames, {"lon", "long", "longitude", "lng", "gpslon", "gpslongitude", "x"})
    name_col = pick_column(reader.fieldnames, {"name", "photo", "filename", "file", "image", "id", "pointid"})
    if not lat_col or not lon_col:
        raise ValueError("CSV must include latitude/longitude columns, for example lat, lon.")

    points: list[list[float | str]] = []
    for index, row in enumerate(reader, start=1):
        try:
            lat = float(str(row.get(lat_col, "")).strip())
            lon = float(str(row.get(lon_col, "")).strip())
        except ValueError:
            continue
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        label = str(row.get(name_col, "")).strip() if name_col else ""
        points.append([round(lat, 7), round(lon, 7), label or f"Uploaded-{index}"])
    return points


def parse_uploaded_geojson(raw: bytes) -> list[list[float | str]]:
    data = json.loads(raw.decode("utf-8-sig", errors="replace"))
    features = data.get("features", [data]) if isinstance(data, dict) else []
    points: list[list[float | str]] = []
    for index, feature in enumerate(features, start=1):
        geometry = feature.get("geometry", {}) if isinstance(feature, dict) else {}
        if geometry.get("type") != "Point":
            continue
        coords = geometry.get("coordinates", [])
        if len(coords) < 2:
            continue
        lon = float(coords[0])
        lat = float(coords[1])
        props = feature.get("properties", {}) or {}
        label = str(props.get("name") or props.get("filename") or props.get("id") or f"Uploaded-{index}")
        points.append([round(lat, 7), round(lon, 7), label])
    return points


def parse_uploaded_locations(uploaded_file) -> list[list[float | str]]:
    raw = uploaded_file.getvalue()
    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix == ".csv":
        return parse_uploaded_csv(raw)
    if suffix in {".geojson", ".json"}:
        return parse_uploaded_geojson(raw)
    raise ValueError("Upload a CSV, GeoJSON, or JSON point file.")


def add_uploaded_layer(base_html: str, uploaded_points: list[list[float | str]]) -> str:
    if not uploaded_points:
        return base_html

    payload = json.dumps(uploaded_points, ensure_ascii=False, separators=(",", ":"))
    layer_script = f"""
    const uploadedPoints = {payload};
    const UploadedCanvasLayer = L.Layer.extend({{
      onAdd: function(map) {{
        this._map = map;
        this._canvas = L.DomUtil.create('canvas', 'leaflet-layer');
        this._canvas.style.position = 'absolute';
        this._canvas.style.pointerEvents = 'none';
        map.getPane('controlPane').appendChild(this._canvas);
        map.on('resize zoomend moveend overlayadd', this._schedule, this);
        this._reset();
      }},
      onRemove: function(map) {{
        L.DomUtil.remove(this._canvas);
        map.off('resize zoomend moveend overlayadd', this._schedule, this);
      }},
      _schedule: function() {{
        if (this._frame) cancelAnimationFrame(this._frame);
        this._frame = requestAnimationFrame(() => this._reset());
      }},
      _reset: function() {{
        const size = this._map.getSize();
        const topLeft = this._map.containerPointToLayerPoint([0, 0]);
        L.DomUtil.setPosition(this._canvas, topLeft);
        this._canvas.width = size.x;
        this._canvas.height = size.y;
        this._draw();
      }},
      _draw: function() {{
        const ctx = this._canvas.getContext('2d');
        const size = this._map.getSize();
        ctx.clearRect(0, 0, size.x, size.y);
        ctx.fillStyle = 'rgba(22,163,74,0.88)';
        ctx.strokeStyle = 'rgba(20,83,45,0.95)';
        ctx.lineWidth = 1.2;
        const margin = 16;
        for (let i = 0; i < uploadedPoints.length; i++) {{
          const p = uploadedPoints[i];
          const c = this._map.latLngToContainerPoint([p[0], p[1]]);
          if (c.x < -margin || c.y < -margin || c.x > size.x + margin || c.y > size.y + margin) continue;
          ctx.beginPath();
          ctx.rect(c.x - 3.5, c.y - 3.5, 7, 7);
          ctx.fill();
          ctx.stroke();
        }}
      }}
    }});
    const uploadedLayer = new UploadedCanvasLayer();
    uploadedLayer.addTo(map);
"""
    html = base_html.replace("    tbmLayer.addTo(map);\n\n    L.control.layers(", f"    tbmLayer.addTo(map);\n{layer_script}\n    L.control.layers(")
    html = html.replace("        'DGPS TBM': tbmLayer", "        'DGPS TBM': tbmLayer,\n        'Uploaded photo locations': uploadedLayer")
    html = html.replace(
        '<p class="legend-item"><span class="legend-tbm"></span>DGPS TBM control</p>',
        '<p class="legend-item"><span class="legend-tbm"></span>DGPS TBM control</p>\n    <p class="legend-item"><span style="width:10px;height:10px;background:#16a34a;border:1px solid #14532d;display:inline-block;flex:0 0 auto;"></span>Uploaded photo locations</p>',
    )
    return html


ensure_static_webmap()
summary = load_json(SUMMARY_JSON)
dgps = load_json(DGPS_GEOJSON)
dgps_types: dict[str, int] = {}
for feature in dgps["features"]:
    point_type = feature["properties"]["type"]
    dgps_types[point_type] = dgps_types.get(point_type, 0) + 1

st.title("Mohanpura Drone Coverage and Survey Control")
st.markdown(
    '<p class="source-note">Use the layer control inside the map to switch basemaps and toggle AOI, drone photo locations, BM/Base, and TBM layers.</p>',
    unsafe_allow_html=True,
)

with st.expander("Add client photo locations", expanded=False):
    uploaded_locations_file = st.file_uploader(
        "Upload location file only",
        type=["csv", "geojson", "json"],
        help="Use a CSV with lat/lon columns or a GeoJSON point file. Do not upload photographs here.",
    )
    uploaded_points: list[list[float | str]] = []
    if uploaded_locations_file is not None:
        try:
            uploaded_points = parse_uploaded_locations(uploaded_locations_file)
            st.success(f"Loaded {len(uploaded_points):,} uploaded photo locations for this session.")
        except Exception as exc:
            st.error(f"Could not read uploaded locations: {exc}")
    st.caption("Uploaded locations are added to the current session map only. Image files are not accepted or stored.")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Drone Photos", f"{summary['geotagged_images']:,}")
col2.metric("AOI Features", "1")
col3.metric("BM/Base", f"{dgps_types.get('BM/Base', 0):,}")
col4.metric("TBM", f"{dgps_types.get('TBM', 0):,}")

map_html = SOURCE_WEBMAP.read_text(encoding="utf-8")
if uploaded_points:
    map_html = add_uploaded_layer(map_html, uploaded_points)
components.html(map_html, height=820)

with st.expander("DGPS BM/TBM records", expanded=False):
    st.json(dgps, expanded=False)
