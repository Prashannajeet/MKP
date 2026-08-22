from __future__ import annotations

import json
from pathlib import Path

import streamlit as st


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

col1, col2, col3, col4 = st.columns(4)
col1.metric("Drone Photos", f"{summary['geotagged_images']:,}")
col2.metric("AOI Features", "1")
col3.metric("BM/Base", f"{dgps_types.get('BM/Base', 0):,}")
col4.metric("TBM", f"{dgps_types.get('TBM', 0):,}")

st.iframe("/app/static/drone_photo_webmap.html?v=9", height=820)

with st.expander("DGPS BM/TBM table", expanded=False):
    rows = []
    for feature in dgps["features"]:
        row = dict(feature["properties"])
        row["longitude"] = feature["geometry"]["coordinates"][0]
        row["latitude"] = feature["geometry"]["coordinates"][1]
        rows.append(row)
    st.dataframe(rows, hide_index=True, width="stretch")
