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
KUNDALIYA_DIR = ROOT / "outputs" / "kundaliya"
KUNDALIYA_SUMMARY = KUNDALIYA_DIR / "summary.json"
KUNDALIYA_CONTROLS = KUNDALIYA_DIR / "kundaliya_bm_tbm.geojson"
KUNDALIYA_WEBMAP = KUNDALIYA_DIR / "kundaliya_webmap.html"
GOOGLE_DRIVE_SUBMISSION_URL = "https://drive.google.com/drive/folders/1GTC_fSJDd5ROt-he2B7grUV5Ks9-81uV?usp=sharing"
FINAL_SUBMISSION_FOLDER = "Mohanpura Final Submission · 12 October 2026"
FINAL_DELIVERABLES = (
    ("A3 Survey Atlas", "Terrain, orthomosaic, contours and PMF mapping"),
    ("PMF Risk Report", "PMF inundation assessment and map sheets"),
    ("PMF Building Risk Atlas", "Building-level PMF risk mapping"),
    ("River Cross-Section Atlas", "HEC-RAS-ready cross-sections and stationing"),
)


st.set_page_config(
    page_title="MKP Survey Planning",
    layout="wide",
)


st.markdown(
    """
    <style>
    :root { --ll-navy: #093451; --ll-paper: #f3ecdf; --ll-cream: #fffaf0; --ll-line: #c9bfae; --ll-green: #2d806c; }
    [data-testid="stAppViewContainer"], [data-testid="stApp"] { background: var(--ll-paper); color: var(--ll-navy); }
    [data-testid="stHeader"] { background: rgba(243,236,223,.90); }
    html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] { height: 100vh; overflow: hidden; }
    [data-testid="stHeader"] { display: none; }
    .block-container { padding: .35rem .8rem .45rem; max-width: 100%; height: 100vh; overflow: hidden; }
    h1 { color: var(--ll-navy); font-size: 1.45rem; letter-spacing: 0; margin: 0 0 .1rem; line-height: 1.1; }
    h2 { color: var(--ll-navy); font-size: 1.15rem; margin: .15rem 0 .2rem; line-height: 1.15; }
    h3 { color: var(--ll-navy); }
    [data-testid="stMetric"] {
      background: var(--ll-cream);
      border: 1px solid var(--ll-line);
      border-radius: 8px;
      box-shadow: 0 2px 8px rgba(53,45,30,.08);
      padding: 5px 9px;
      min-height: 58px;
    }
    [data-testid="stMetricLabel"] { color: #53616d; }
    [data-testid="stMetricValue"] { color: var(--ll-navy); }
    [data-testid="stExpander"] {
      background: rgba(255,250,240,.76);
      border: 1px solid var(--ll-line);
      border-radius: 8px;
    }
    [data-testid="stDivider"] { border-color: var(--ll-line); }
    .stLinkButton > a {
      background: var(--ll-navy) !important;
      border: 1px solid var(--ll-navy) !important;
      border-radius: 6px !important;
      color: #fffaf0 !important;
      font-weight: 650;
      box-shadow: 0 2px 5px rgba(9,52,81,.18);
    }
    .stLinkButton > a:hover { background: #145271 !important; border-color: #145271 !important; }
    .submission-kicker { color: var(--ll-green); font-size: .73rem; font-weight: 750; letter-spacing: .12em; margin: .55rem 0 -.35rem; }
    .source-note {
      color: #40525b;
      font-size: .9rem;
      line-height: 1.45;
      background: rgba(255,250,240,.74);
      border-left: 4px solid var(--ll-green);
      border-radius: 0 6px 6px 0;
      padding: .3rem .55rem;
      margin: .05rem 0 .35rem;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    div[role="radiogroup"] { gap: .25rem; margin: 0 0 .15rem; }
    div[role="radiogroup"] label { padding-top: 0; padding-bottom: 0; }
    [data-testid="stMetricValue"] { font-size: 1.45rem; }
    [data-testid="stMetricLabel"] { font-size: .78rem; }
    [data-testid="stSidebar"] .block-container { height: auto; overflow-y: auto; padding: .8rem; }
    iframe { display: block; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def load_json(path: Path, modified_ns: int) -> dict:
    """Load JSON, invalidating the cache when a delivery asset changes."""
    del modified_ns
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
        ctx.fillStyle = hexToRgba(styleState.clientColor, 0.88);
        ctx.strokeStyle = hexToRgba(styleState.clientStroke, 0.95);
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
    html = base_html.replace("    L.control.layers(", f"{layer_script}\n    L.control.layers(")
    html = html.replace("        'DGPS TBM': tbmLayer", "        'DGPS TBM': tbmLayer,\n        'Uploaded photo locations': uploadedLayer")
    html = html.replace("      clientPhotoLayer._reset();", "      clientPhotoLayer._reset();\n      uploadedLayer._reset();")
    html = html.replace(
        '<p class="legend-item"><span class="legend-tbm"></span>DGPS TBM control</p>',
        '<p class="legend-item"><span class="legend-tbm"></span>DGPS TBM control</p>\n    <p class="legend-item"><span style="width:10px;height:10px;background:#16a34a;border:1px solid #14532d;display:inline-block;flex:0 0 auto;"></span>Uploaded photo locations</p>',
    )
    return html


def render_submission_downloads() -> None:
    """Show the client-facing final-delivery gateway hosted in Google Drive."""
    st.markdown('<div class="submission-kicker">FINAL SUBMISSION · 12 OCTOBER 2026</div>', unsafe_allow_html=True)
    st.subheader("Mohanpura final submission")
    st.caption("Final survey, terrain, PMF risk and cross-section deliverables")
    st.link_button(
        "Open final-delivery downloads in Google Drive",
        GOOGLE_DRIVE_SUBMISSION_URL,
        type="primary",
        use_container_width=False,
    )
    st.caption(f"Delivery package: {FINAL_SUBMISSION_FOLDER}")
    columns = st.columns(4)
    for column, (title, description) in zip(columns, FINAL_DELIVERABLES):
        with column:
            st.markdown(f"**{title}**")
            st.caption(description)


def require_delivery_assets() -> None:
    """Stop with an actionable message when the synchronized delivery data is missing."""
    required = (
        SUMMARY_JSON,
        DGPS_GEOJSON,
        SOURCE_WEBMAP,
        KUNDALIYA_SUMMARY,
        KUNDALIYA_CONTROLS,
        KUNDALIYA_WEBMAP,
    )
    missing = [path.relative_to(ROOT) for path in required if not path.is_file()]
    if missing:
        st.error("The survey app cannot find its synchronized delivery data.")
        st.code("\n".join(str(path) for path in missing), language=None)
        st.info("Run the Mohanpura and Kundaliya asset-build scripts, then restart the app.")
        st.stop()


def render_mohanpura() -> None:
    summary = load_json(SUMMARY_JSON, SUMMARY_JSON.stat().st_mtime_ns)
    dgps = load_json(DGPS_GEOJSON, DGPS_GEOJSON.stat().st_mtime_ns)
    dgps_types: dict[str, int] = {}
    for feature in dgps["features"]:
        point_type = feature["properties"]["type"]
        dgps_types[point_type] = dgps_types.get(point_type, 0) + 1

    with st.sidebar:
        st.subheader("Mohanpura project files")
        st.link_button(
            "Open final-delivery folder",
            GOOGLE_DRIVE_SUBMISSION_URL,
            type="primary",
            use_container_width=True,
        )
        st.caption(FINAL_SUBMISSION_FOLDER)
        for title, description in FINAL_DELIVERABLES:
            st.markdown(f"**{title}**")
            st.caption(description)
        st.divider()
        uploaded_locations_file = st.file_uploader(
            "Add photo-location file",
            type=["csv", "geojson", "json"],
            help="Use a CSV with lat/lon columns or a GeoJSON point file.",
            key="mohanpura_locations",
        )
        uploaded_points: list[list[float | str]] = []
        if uploaded_locations_file is not None:
            try:
                uploaded_points = parse_uploaded_locations(uploaded_locations_file)
                st.success(f"Loaded {len(uploaded_points):,} locations.")
            except Exception as exc:
                st.error(f"Could not read uploaded locations: {exc}")
        with st.expander("BM/TBM data", expanded=False):
            st.json(dgps, expanded=False)

    st.subheader("Mohanpura Final Coverage and Survey Control")
    st.markdown(
        '<p class="source-note">Final-submission reference: flight geotags, final AOI and BM/TBM control register dated 12 October 2026. Use the map layer control to switch basemaps and survey overlays.</p>',
        unsafe_allow_html=True,
    )
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Final Flight Geotags", f"{summary['geotagged_images']:,}")
    col2.metric("Final AOI", f"{float(summary.get('aoi_km2', 0)):.2f} km²")
    col3.metric("BM / Reference", f"{dgps_types.get('BM/Base', 0):,}")
    col4.metric("TBM", f"{dgps_types.get('TBM', 0):,}")

    map_html = SOURCE_WEBMAP.read_text(encoding="utf-8")
    if uploaded_points:
        map_html = add_uploaded_layer(map_html, uploaded_points)
    render_map_html(map_html)


def download_asset(path: Path, label: str, mime: str) -> None:
    st.download_button(label, data=path.read_bytes(), file_name=path.name, mime=mime, use_container_width=True)


def render_map_html(map_html: str) -> None:
    """Render the embedded map across current and earlier Streamlit releases."""
    if hasattr(st, "iframe"):
        st.iframe(map_html, height=500)
    else:
        components.html(map_html, height=500, scrolling=False)


def render_kundaliya() -> None:
    summary = load_json(KUNDALIYA_SUMMARY, KUNDALIYA_SUMMARY.stat().st_mtime_ns)
    controls = load_json(KUNDALIYA_CONTROLS, KUNDALIYA_CONTROLS.stat().st_mtime_ns)
    with st.sidebar:
        st.subheader("Kundaliya project files")
        download_asset(KUNDALIYA_DIR / "Kundaliya_Final_Controller_KML_R0.zip", "Controller KML package", "application/zip")
        download_asset(KUNDALIYA_DIR / "Kundaliya_Final_Flight_Plan_R0_Combined.kmz", "Combined flight plan KMZ", "application/vnd.google-earth.kmz")
        download_asset(KUNDALIYA_DIR / "Kundaliya_Final_Flight_Plan_R0_Combined.kml", "Combined flight plan KML", "application/vnd.google-earth.kml+xml")
        download_asset(KUNDALIYA_DIR / "Kundaliya_Final_Mission_Register_R0.csv", "Mission register CSV", "text/csv")
        download_asset(KUNDALIYA_DIR / "Kundaliya_BM.kml", "Kundaliya BM KML", "application/vnd.google-earth.kml+xml")
        download_asset(KUNDALIYA_DIR / "Kundaliya_TBM.kml", "Kundaliya TBM KML", "application/vnd.google-earth.kml+xml")
        with st.expander("BM/TBM data", expanded=False):
            st.json(controls, expanded=False)

    st.subheader("Kundaliya Flight Planning and Survey Control")
    st.markdown(
        '<p class="source-note">Planning reference: Kundaliya Flight Plan R0 dated 24 October 2026. The map presents the finalized 100 m-smoothed PMF AOI, controller missions KUN-M001 to KUN-M108, and the supplied BM/TBM control locations.</p>',
        unsafe_allow_html=True,
    )

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Flight Missions", f"{summary['mission_count']:,}")
    col2.metric("Smoothed AOI", f"{summary['smoothed_aoi_ha']:,.1f} ha")
    col3.metric("Planned Coverage", f"{summary['coverage_pct']:.2f}%")
    col4.metric("BM", f"{summary['bm_count']:,}")
    col5.metric("TBM", f"{summary['tbm_count']:,}")

    render_map_html(KUNDALIYA_WEBMAP.read_text(encoding="utf-8"))


require_delivery_assets()
ensure_static_webmap()
title_col, project_col = st.columns([3.4, 1.25])
with title_col:
    st.title("Mohanpura and Kundaliya Survey Planning")
with project_col:
    project = st.radio(
        "Project",
        ["Mohanpura", "Kundaliya"],
        horizontal=True,
        label_visibility="collapsed",
    )
if project == "Mohanpura":
    render_mohanpura()
else:
    render_kundaliya()
