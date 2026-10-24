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
    page_title="MKP Survey Control | Logical Limit",
    layout="wide",
    initial_sidebar_state="collapsed",
)


st.markdown(
    """
    <style>
    :root {
      --ll-navy: #123142;
      --ll-ink: #193642;
      --ll-muted: #647985;
      --ll-bg: #eef4f7;
      --ll-surface: #ffffff;
      --ll-line: #d5e0e6;
      --ll-accent: #278ca4;
      --ll-accent-dark: #176d83;
      --ll-green: #2d806c;
    }
    [data-testid="stAppViewContainer"], [data-testid="stApp"] {
      background: var(--ll-bg);
      color: var(--ll-ink);
    }
    header[data-testid="stHeader"] { background: rgba(238,244,247,.96); height: 2rem; }
    [data-testid="stSidebar"] { display: none; }
    .block-container { padding: 2.15rem .65rem .55rem; max-width: 100%; }
    h1, h2, h3 { color: var(--ll-navy); letter-spacing: 0; }
    h2 { font-size: 1.05rem; margin: 0; line-height: 1.2; }
    h3 { font-size: .98rem; }
    .app-masthead {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 1rem;
      align-items: center;
      background: var(--ll-surface);
      border: 1px solid var(--ll-line);
      border-radius: 4px;
      padding: .58rem .72rem;
      margin: 0 0 .35rem;
      box-shadow: 0 2px 8px rgba(18,49,66,.055);
    }
    .brand-lockup { display: flex; align-items: center; gap: .7rem; min-width: 0; }
    .brand-mark {
      width: 34px;
      height: 34px;
      display: grid;
      place-items: center;
      flex: 0 0 34px;
      color: white;
      background: var(--ll-accent-dark);
      border-radius: 4px;
      font-size: .72rem;
      font-weight: 800;
      letter-spacing: .04em;
    }
    .brand-kicker {
      color: var(--ll-accent-dark);
      font-size: .66rem;
      font-weight: 800;
      letter-spacing: .11em;
      line-height: 1.2;
      text-transform: uppercase;
    }
    .app-title {
      color: var(--ll-navy);
      font-size: 1.15rem;
      font-weight: 720;
      line-height: 1.15;
      margin-top: .05rem;
    }
    .app-subtitle { color: var(--ll-muted); font-size: .73rem; margin-top: .12rem; }
    .masthead-meta { display: flex; align-items: center; gap: .45rem; }
    .status-pill {
      background: #e7f4f1;
      border: 1px solid #b8d8d0;
      border-radius: 999px;
      color: #266b5c;
      font-size: .65rem;
      font-weight: 700;
      padding: .22rem .48rem;
      white-space: nowrap;
    }
    .revision-pill {
      border-left: 1px solid var(--ll-line);
      color: var(--ll-muted);
      font-size: .68rem;
      font-weight: 700;
      padding-left: .55rem;
      white-space: nowrap;
    }
    .project-head {
      display: flex;
      justify-content: space-between;
      align-items: end;
      gap: 1rem;
      background: var(--ll-surface);
      border: 1px solid var(--ll-line);
      border-bottom: 0;
      padding: .48rem .65rem .42rem;
      margin-top: .25rem;
    }
    .project-title { color: var(--ll-navy); font-size: 1rem; font-weight: 720; line-height: 1.2; }
    .project-note { color: var(--ll-muted); font-size: .69rem; margin-top: .08rem; }
    .project-crs { color: var(--ll-muted); font-size: .66rem; font-weight: 650; white-space: nowrap; }
    .kpi-strip {
      display: grid;
      grid-template-columns: repeat(var(--kpi-count), minmax(0, 1fr));
      background: var(--ll-surface);
      border: 1px solid var(--ll-line);
      margin: 0 0 .34rem;
    }
    .kpi-item { padding: .38rem .58rem .42rem; border-right: 1px solid var(--ll-line); min-width: 0; }
    .kpi-item:last-child { border-right: 0; }
    .kpi-label { color: var(--ll-muted); font-size: .62rem; font-weight: 700; text-transform: uppercase; line-height: 1.2; }
    .kpi-value { color: var(--ll-navy); font-size: 1.12rem; font-weight: 690; line-height: 1.25; margin-top: .08rem; }
    .kpi-detail { color: #81929b; font-size: .57rem; margin-top: .02rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .map-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: var(--ll-surface);
      border: 1px solid var(--ll-line);
      border-bottom: 0;
      padding: .32rem .55rem;
    }
    .map-head strong { color: var(--ll-navy); font-size: .78rem; }
    .map-head span { color: var(--ll-muted); font-size: .62rem; }
    [data-testid="stIFrame"] {
      border: 1px solid var(--ll-line);
      background: var(--ll-surface);
      box-shadow: 0 2px 8px rgba(18,49,66,.05);
    }
    [data-testid="stExpander"] {
      background: var(--ll-surface);
      border: 1px solid var(--ll-line);
      border-radius: 4px;
      margin-top: .3rem;
    }
    [data-testid="stDivider"] { border-color: var(--ll-line); }
    .stLinkButton > a {
      background: var(--ll-accent-dark) !important;
      border: 1px solid var(--ll-accent-dark) !important;
      border-radius: 4px !important;
      color: #fff !important;
      font-weight: 650;
      box-shadow: 0 2px 5px rgba(9,52,81,.18);
    }
    .stLinkButton > a:hover { background: #145271 !important; border-color: #145271 !important; }
    .submission-kicker { color: var(--ll-green); font-size: .7rem; font-weight: 750; letter-spacing: .1em; margin: .35rem 0 -.25rem; }
    .source-note {
      color: #40525b;
      font-size: .9rem;
      line-height: 1.45;
      background: var(--ll-surface);
      border-left: 4px solid var(--ll-green);
      border-radius: 0 3px 3px 0;
      padding: .3rem .55rem;
      margin: .05rem 0 .35rem;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    [data-testid="stTabs"] [role="tablist"] { gap: .95rem; border-bottom: 1px solid var(--ll-line); }
    [data-testid="stTabs"] button[role="tab"] { color: #536a76; padding: .2rem 0 .38rem; font-size: .75rem; }
    [data-testid="stTabs"] button[role="tab"][aria-selected="true"] { color: var(--ll-accent-dark); font-weight: 700; }
    [data-testid="stTabs"] [data-baseweb="tab-highlight"] { background-color: var(--ll-accent); }
    iframe { display: block; }
    @media (max-width: 760px) {
      .block-container { padding: 2.1rem .35rem .5rem; }
      .app-masthead { grid-template-columns: 1fr; gap: .35rem; }
      .masthead-meta { justify-content: flex-start; }
      .app-title { font-size: 1rem; }
      .kpi-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .kpi-item:nth-child(2n) { border-right: 0; }
      .kpi-item { border-bottom: 1px solid var(--ll-line); }
      .project-crs { display: none; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def render_app_masthead() -> None:
    st.markdown(
        """
        <header class="app-masthead">
          <div class="brand-lockup">
            <div class="brand-mark">LLC</div>
            <div>
              <div class="brand-kicker">Logical Limit Consulting LLP · Bhopal</div>
              <div class="app-title">Mohanpura Kundaliya Survey Planning &amp; Control</div>
              <div class="app-subtitle">Flight coverage, AOI validation and DGPS survey-control review</div>
            </div>
          </div>
          <div class="masthead-meta">
            <span class="status-pill">DATA SYNCHRONIZED</span>
            <span class="revision-pill">Client Review · R0</span>
          </div>
        </header>
        """,
        unsafe_allow_html=True,
    )


def render_project_header(title: str, note: str) -> None:
    st.markdown(
        f"""
        <section class="project-head">
          <div>
            <div class="project-title">{title}</div>
            <div class="project-note">{note}</div>
          </div>
          <div class="project-crs">WGS 84 · UTM Zone 43N</div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_kpi_strip(items: list[tuple[str, str, str]]) -> None:
    cards = "".join(
        f'<div class="kpi-item"><div class="kpi-label">{label}</div><div class="kpi-value">{value}</div><div class="kpi-detail">{detail}</div></div>'
        for label, value, detail in items
    )
    st.markdown(
        f'<div class="kpi-strip" style="--kpi-count:{len(items)}">{cards}</div>',
        unsafe_allow_html=True,
    )


def render_map_header(title: str, detail: str) -> None:
    st.markdown(
        f'<div class="map-head"><strong>{title}</strong><span>{detail}</span></div>',
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

    render_project_header(
        "Mohanpura Final Coverage and Survey Control",
        "Final flight geotags, AOI and BM/TBM control register · 12 October 2026",
    )

    uploaded_locations_file = st.session_state.get("mohanpura_locations")
    uploaded_points: list[list[float | str]] = []
    upload_error: str | None = None
    if uploaded_locations_file is not None:
        try:
            uploaded_points = parse_uploaded_locations(uploaded_locations_file)
        except Exception as exc:
            upload_error = str(exc)

    render_kpi_strip(
        [
            ("Final flight geotags", f"{summary['geotagged_images']:,}", "Accepted image locations"),
            ("Final AOI", f"{float(summary.get('aoi_km2', 0)):.2f} km²", "Client submission boundary"),
            ("BM / reference", f"{dgps_types.get('BM/Base', 0):,}", "Primary survey control"),
            ("TBM", f"{dgps_types.get('TBM', 0):,}", "Temporary benchmarks"),
        ]
    )

    map_html = SOURCE_WEBMAP.read_text(encoding="utf-8")
    if uploaded_points:
        map_html = add_uploaded_layer(map_html, uploaded_points)
    render_map_header("Survey control map", "Use the layer control to switch basemaps and survey overlays")
    render_map_html(map_html)

    with st.expander("Final submission, uploads and control records", expanded=False):
        render_submission_downloads()
        st.file_uploader(
            "Upload location file only",
            type=["csv", "geojson", "json"],
            help="Use a CSV with lat/lon columns or a GeoJSON point file. Do not upload photographs here.",
            key="mohanpura_locations",
        )
        if upload_error:
            st.error(f"Could not read uploaded locations: {upload_error}")
        elif uploaded_locations_file is not None:
            st.success(f"Loaded {len(uploaded_points):,} uploaded photo locations for this session.")
        st.caption("Uploaded locations are added to the current session map only.")
        st.json(dgps, expanded=False)


def download_asset(path: Path, label: str, mime: str) -> None:
    st.download_button(label, data=path.read_bytes(), file_name=path.name, mime=mime, use_container_width=True)


def render_map_html(map_html: str) -> None:
    """Render the embedded map across current and earlier Streamlit releases."""
    if hasattr(st, "iframe"):
        st.iframe(map_html, height=300)
    else:
        components.html(map_html, height=300, scrolling=False)


def render_kundaliya() -> None:
    summary = load_json(KUNDALIYA_SUMMARY, KUNDALIYA_SUMMARY.stat().st_mtime_ns)
    controls = load_json(KUNDALIYA_CONTROLS, KUNDALIYA_CONTROLS.stat().st_mtime_ns)
    render_project_header(
        "Kundaliya Flight Planning and Survey Control",
        "Finalized 100 m-smoothed PMF AOI and controller missions KUN-M001 to KUN-M108 · R0",
    )

    render_kpi_strip(
        [
            ("Flight missions", f"{summary['mission_count']:,}", "DJI controller packages"),
            ("Smoothed AOI", f"{summary['smoothed_aoi_ha']:,.1f} ha", "PMF survey boundary"),
            ("Planned coverage", f"{summary['coverage_pct']:.2f}%", "AOI coverage target"),
            ("BM", f"{summary['bm_count']:,}", "Long-term benchmarks"),
            ("TBM", f"{summary['tbm_count']:,}", "Temporary benchmarks"),
        ]
    )

    render_map_header("Flight mission map", "R0 mission footprints, AOI and DGPS survey control")
    render_map_html(KUNDALIYA_WEBMAP.read_text(encoding="utf-8"))

    with st.expander("Download Kundaliya flight plans and view control records", expanded=False):
        first = st.columns(3)
        with first[0]:
            download_asset(KUNDALIYA_DIR / "Kundaliya_Final_Controller_KML_R0.zip", "Controller KML package", "application/zip")
        with first[1]:
            download_asset(KUNDALIYA_DIR / "Kundaliya_Final_Flight_Plan_R0_Combined.kmz", "Combined flight plan KMZ", "application/vnd.google-earth.kmz")
        with first[2]:
            download_asset(KUNDALIYA_DIR / "Kundaliya_Final_Mission_Register_R0.csv", "Mission register CSV", "text/csv")
        second = st.columns(3)
        with second[0]:
            download_asset(KUNDALIYA_DIR / "Kundaliya_Final_Flight_Plan_R0_Combined.kml", "Combined flight plan KML", "application/vnd.google-earth.kml+xml")
        with second[1]:
            download_asset(KUNDALIYA_DIR / "Kundaliya_BM.kml", "Kundaliya BM KML", "application/vnd.google-earth.kml+xml")
        with second[2]:
            download_asset(KUNDALIYA_DIR / "Kundaliya_TBM.kml", "Kundaliya TBM KML", "application/vnd.google-earth.kml+xml")
        st.json(controls, expanded=False)


require_delivery_assets()
ensure_static_webmap()
render_app_masthead()
mohanpura_tab, kundaliya_tab = st.tabs(["Mohanpura", "Kundaliya"])
with mohanpura_tab:
    render_mohanpura()
with kundaliya_tab:
    render_kundaliya()
