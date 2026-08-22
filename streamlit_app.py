from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import folium
import pandas as pd
import pydeck as pdk
import streamlit as st
from folium.plugins import FastMarkerCluster, Fullscreen, MeasureControl
from streamlit_folium import st_folium


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "outputs" / "drone_geotags"
DRONE_CSV = DATA_DIR / "drone_photo_locations.csv"
AOI_GEOJSON = DATA_DIR / "mohanpura_aoi.geojson"
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
    .block-container { padding-top: 1.1rem; padding-bottom: 1rem; }
    h1 { font-size: 1.65rem; letter-spacing: 0; margin-bottom: .3rem; }
    [data-testid="stMetric"] {
      background: #f8fafb;
      border: 1px solid #d9e1e8;
      border-radius: 6px;
      padding: 10px 12px;
    }
    [data-testid="stMetricLabel"] { color: #52616d; }
    .source-note {
      color: #52616d;
      font-size: .86rem;
      margin-top: -.2rem;
      margin-bottom: .8rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def load_summary() -> dict:
    return json.loads(SUMMARY_JSON.read_text(encoding="utf-8"))


def ensure_static_webmap() -> None:
    STATIC_DIR.mkdir(exist_ok=True)
    if not STATIC_WEBMAP.exists() or STATIC_WEBMAP.stat().st_mtime < SOURCE_WEBMAP.stat().st_mtime:
        STATIC_WEBMAP.write_text(SOURCE_WEBMAP.read_text(encoding="utf-8"), encoding="utf-8")


@st.cache_data(show_spinner=False)
def load_drone_points() -> pd.DataFrame:
    df = pd.read_csv(DRONE_CSV)
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    return df


@st.cache_data(show_spinner=False)
def load_geojson(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def geojson_bounds(geojson: dict) -> list[list[float]]:
    lats: list[float] = []
    lons: list[float] = []

    def walk(coords):
        if isinstance(coords, list) and coords and isinstance(coords[0], (int, float)):
            lons.append(float(coords[0]))
            lats.append(float(coords[1]))
            return
        if isinstance(coords, list):
            for item in coords:
                walk(item)

    for feature in geojson.get("features", []):
        walk(feature["geometry"]["coordinates"])
    return [[min(lats), min(lons)], [max(lats), max(lons)]]


def geojson_polygon_rows(geojson: dict) -> list[dict[str, Any]]:
    rows = []
    for feature in geojson.get("features", []):
        geometry = feature.get("geometry", {})
        coords = geometry.get("coordinates", [])
        if geometry.get("type") == "Polygon" and coords:
            rows.append(
                {
                    "name": feature.get("properties", {}).get("name", "Mohanpura AOI"),
                    "polygon": coords[0],
                }
            )
        elif geometry.get("type") == "MultiPolygon":
            for polygon in coords:
                if polygon:
                    rows.append(
                        {
                            "name": feature.get("properties", {}).get("name", "Mohanpura AOI"),
                            "polygon": polygon[0],
                        }
                    )
    return rows


def dgps_dataframe(dgps: dict) -> pd.DataFrame:
    rows = []
    for feature in dgps["features"]:
        props = dict(feature["properties"])
        props["longitude"] = feature["geometry"]["coordinates"][0]
        props["latitude"] = feature["geometry"]["coordinates"][1]
        props["color"] = [245, 158, 11, 230] if props["type"] == "TBM" else [29, 78, 216, 230]
        props["radius"] = 85 if props["type"] == "TBM" else 70
        rows.append(props)
    return pd.DataFrame(rows)


def build_pydeck(df: pd.DataFrame, aoi: dict, dgps: dict) -> pdk.Deck:
    bounds = geojson_bounds(aoi)
    center_lat = (bounds[0][0] + bounds[1][0]) / 2
    center_lon = (bounds[0][1] + bounds[1][1]) / 2
    dgps_df = dgps_dataframe(dgps)

    layers = [
        pdk.Layer(
            "ScatterplotLayer",
            data=df,
            get_position="[lon, lat]",
            get_fill_color=[220, 38, 38, 115],
            get_line_color=[127, 29, 29, 180],
            get_radius=18,
            radius_min_pixels=1,
            radius_max_pixels=5,
            pickable=True,
            auto_highlight=True,
        ),
        pdk.Layer(
            "PolygonLayer",
            data=geojson_polygon_rows(aoi),
            get_polygon="polygon",
            get_fill_color=[10, 147, 150, 0],
            get_line_color=[0, 95, 115, 255],
            line_width_min_pixels=3,
            stroked=True,
            filled=False,
            pickable=False,
            auto_highlight=False,
        ),
        pdk.Layer(
            "ScatterplotLayer",
            data=dgps_df,
            get_position="[longitude, latitude]",
            get_fill_color="color",
            get_line_color=[255, 255, 255, 255],
            get_radius="radius",
            radius_min_pixels=5,
            radius_max_pixels=12,
            line_width_min_pixels=1,
            pickable=True,
            auto_highlight=True,
        ),
    ]

    tooltip = {
        "html": "<b>{name}{point_id}</b><br/>Type: {type}<br/>Elevation: {elevation_m} m<br/>Lat/Lon: {lat}{latitude}, {lon}{longitude}",
        "style": {"backgroundColor": "#172026", "color": "white"},
    }
    return pdk.Deck(
        map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
        initial_view_state=pdk.ViewState(
            latitude=center_lat,
            longitude=center_lon,
            zoom=11,
            pitch=0,
        ),
        layers=layers,
        tooltip=tooltip,
    )


def add_drone_points(map_obj: folium.Map, df: pd.DataFrame) -> None:
    group = folium.FeatureGroup(name="Drone photo locations", show=True, overlay=True)
    data = df[["lat", "lon"]].values.tolist()
    callback = """
    function (row) {
      return L.circleMarker(new L.LatLng(row[0], row[1]), {
        radius: 2.6,
        color: '#7f1d1d',
        weight: 0.7,
        fill: true,
        fillColor: '#dc2626',
        fillOpacity: 0.55
      });
    }
    """
    FastMarkerCluster(data=data, callback=callback, name="Drone photo locations").add_to(group)
    group.add_to(map_obj)


def add_aoi(map_obj: folium.Map, aoi: dict) -> None:
    folium.GeoJson(
        aoi,
        name="Mohanpura AOI",
        overlay=True,
        show=True,
        style_function=lambda _feature: {
            "color": "#005f73",
            "weight": 4,
            "opacity": 1,
            "fillOpacity": 0,
            "dashArray": "9 5",
        },
        highlight_function=lambda _feature: {
            "color": "#001f2a",
            "weight": 5,
            "fillOpacity": 0,
        },
    ).add_to(map_obj)


def add_dgps_points(map_obj: folium.Map, dgps: dict) -> None:
    bm_group = folium.FeatureGroup(name="DGPS BM/Base", show=True, overlay=True)
    tbm_group = folium.FeatureGroup(name="DGPS TBM", show=True, overlay=True)

    for feature in dgps["features"]:
        props = feature["properties"]
        lon, lat = feature["geometry"]["coordinates"]
        popup = folium.Popup(
            f"""
            <b>{props['point_id']}</b><br>
            <b>Type:</b> {props['type']}<br>
            <b>Elevation:</b> {props.get('elevation_m', '')} m<br>
            <b>Date:</b> {props.get('date', '')}<br>
            <b>Remark:</b> {props.get('remark', '')}<br>
            <b>Flight:</b> {props.get('flight_no', '')}<br>
            <b>UTM:</b> {props.get('easting', '')}, {props.get('northing', '')}
            """,
            max_width=360,
        )
        if props["type"] == "TBM":
            marker = folium.RegularPolygonMarker(
                location=(lat, lon),
                number_of_sides=3,
                radius=9,
                rotation=0,
                color="#92400e",
                weight=1.5,
                fill=True,
                fill_color="#f59e0b",
                fill_opacity=0.95,
                popup=popup,
                tooltip=f"{props['point_id']} | TBM",
            )
            marker.add_to(tbm_group)
        else:
            marker = folium.CircleMarker(
                location=(lat, lon),
                radius=6.5,
                color="#1e3a8a",
                weight=1.5,
                fill=True,
                fill_color="#1d4ed8",
                fill_opacity=0.95,
                popup=popup,
                tooltip=f"{props['point_id']} | BM/Base",
            )
            marker.add_to(bm_group)

    bm_group.add_to(map_obj)
    tbm_group.add_to(map_obj)


def build_map(df: pd.DataFrame, aoi: dict, dgps: dict, basemap: str) -> folium.Map:
    bounds = geojson_bounds(aoi)
    center = [(bounds[0][0] + bounds[1][0]) / 2, (bounds[0][1] + bounds[1][1]) / 2]
    map_obj = folium.Map(
        location=center,
        zoom_start=12,
        tiles=None,
        control_scale=True,
        prefer_canvas=True,
    )

    if basemap == "Esri World Imagery":
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Tiles &copy; Esri",
            name="Esri World Imagery",
            overlay=False,
            control=True,
        ).add_to(map_obj)
        folium.TileLayer(
            tiles="https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
            attr="Labels &copy; Esri",
            name="Reference labels",
            overlay=True,
            control=True,
            show=True,
        ).add_to(map_obj)
    else:
        folium.TileLayer("OpenStreetMap", name="OpenStreetMap", overlay=False, control=True).add_to(map_obj)

    # Add drone first, then AOI, then DGPS so the boundary and survey control sit above the photo cloud.
    add_drone_points(map_obj, df)
    add_aoi(map_obj, aoi)
    add_dgps_points(map_obj, dgps)

    folium.LayerControl(collapsed=False).add_to(map_obj)
    Fullscreen(position="topleft").add_to(map_obj)
    MeasureControl(position="topleft", primary_length_unit="kilometers").add_to(map_obj)
    map_obj.fit_bounds(bounds, padding=(24, 24))
    return map_obj


summary = load_summary()
ensure_static_webmap()
drone_df = load_drone_points()
aoi_geojson = load_geojson(AOI_GEOJSON)
dgps_geojson = load_geojson(DGPS_GEOJSON)

dgps_types = pd.Series([f["properties"]["type"] for f in dgps_geojson["features"]]).value_counts()

st.title("Mohanpura Drone Coverage and Survey Control")
st.markdown(
    '<p class="source-note">Use the layer control inside the map to switch basemaps and toggle AOI, drone photo locations, BM/Base, and TBM layers.</p>',
    unsafe_allow_html=True,
)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Drone Photos", f"{len(drone_df):,}")
col2.metric("AOI Features", f"{len(aoi_geojson['features']):,}")
col3.metric("BM/Base", f"{int(dgps_types.get('BM/Base', 0)):,}")
col4.metric("TBM", f"{int(dgps_types.get('TBM', 0)):,}")

st.iframe("/app/static/drone_photo_webmap.html?v=6", height=820, scrolling=False)

with st.expander("DGPS BM/TBM table", expanded=False):
    dgps_rows = []
    for feature in dgps_geojson["features"]:
        row = dict(feature["properties"])
        row["longitude"] = feature["geometry"]["coordinates"][0]
        row["latitude"] = feature["geometry"]["coordinates"][1]
        dgps_rows.append(row)
    st.dataframe(
        pd.DataFrame(dgps_rows),
        hide_index=True,
        width="stretch",
    )

with st.expander("Source files"):
    st.write(f"Drone geotags: `{DRONE_CSV}`")
    st.write(f"Mohanpura AOI: `{AOI_GEOJSON}`")
    st.write(f"DGPS BM/TBM: `{DGPS_GEOJSON}`")
    st.json(summary)
