"""Build the Streamlit map assets from the Mohanpura final submission records.

The script is intentionally run locally: the approved final-submission data live
outside the Streamlit repository. It validates each source before writing a
portable copy of the map assets used by Streamlit Cloud.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from pyproj import Transformer


FINAL_AOI_KM2 = 34.526724988574045
EXPECTED_FLIGHT_GEOTAGS = 30_113
EXPECTED_CONTROL_POINTS = 60
EPSG_UTM_43N = "EPSG:32643"
EPSG_WGS84 = "EPSG:4326"


@dataclass(frozen=True)
class Bounds:
    """WGS 84 bounds for a generated delivery asset."""

    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float


def parse_args() -> argparse.Namespace:
    """Return validated command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-root", type=Path, required=True, help="Streamlit app directory.")
    parser.add_argument("--final-root", type=Path, required=True, help="Final submission package directory.")
    parser.add_argument("--flight-csv", type=Path, required=True, help="Approved final flight-geotag CSV.")
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    """Read a UTF-8 CSV and reject an empty or headerless input."""
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            raise ValueError(f"{path} has no header row.")
        rows = list(reader)
    if not rows:
        raise ValueError(f"{path} has no records.")
    return rows


def float_value(row: dict[str, str], column: str, source: Path) -> float:
    """Read a finite coordinate field with source context on failure."""
    try:
        value = float(row[column])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"Invalid {column!r} in {source.name}: {row!r}") from error
    if not (-10_000_000.0 < value < 10_000_000.0):
        raise ValueError(f"Out-of-range {column!r} in {source.name}: {value}")
    return value


def bounds_from_points(points: list[tuple[float, float]]) -> Bounds:
    """Return a WGS 84 bounding box from (longitude, latitude) points."""
    if not points:
        raise ValueError("Cannot create bounds from zero points.")
    longitudes, latitudes = zip(*points, strict=True)
    return Bounds(min(longitudes), min(latitudes), max(longitudes), max(latitudes))


def combine_bounds(*bounds: Bounds) -> Bounds:
    """Return the envelope covering all supplied bounds."""
    return Bounds(
        min(item.min_lon for item in bounds),
        min(item.min_lat for item in bounds),
        max(item.max_lon for item in bounds),
        max(item.max_lat for item in bounds),
    )


def aoi_feature(map_geometry_path: Path) -> tuple[dict[str, object], Bounds]:
    """Convert the approved UTM final AOI to a WGS 84 GeoJSON feature."""
    geometry_doc = json.loads(map_geometry_path.read_text(encoding="utf-8"))
    aoi = geometry_doc.get("aoi")
    if not isinstance(aoi, dict) or aoi.get("type") != "Polygon":
        raise ValueError(f"{map_geometry_path} does not contain an AOI polygon.")
    rings = aoi.get("coordinates")
    if not isinstance(rings, list) or not rings or not isinstance(rings[0], list):
        raise ValueError(f"{map_geometry_path} AOI has no valid outer ring.")

    transformer = Transformer.from_crs(EPSG_UTM_43N, EPSG_WGS84, always_xy=True)
    transformed_rings: list[list[list[float]]] = []
    for ring in rings:
        transformed_ring: list[list[float]] = []
        for coordinate in ring:
            if isinstance(coordinate, str):
                parts = coordinate.split()
                if len(parts) != 2:
                    raise ValueError(f"Invalid AOI coordinate: {coordinate!r}")
                east, north = float(parts[0]), float(parts[1])
            elif isinstance(coordinate, list) and len(coordinate) == 2:
                east, north = float(coordinate[0]), float(coordinate[1])
            else:
                raise ValueError(f"Invalid AOI coordinate: {coordinate!r}")
            lon, lat = transformer.transform(east, north)
            transformed_ring.append([round(lon, 9), round(lat, 9)])
        if len(transformed_ring) < 4 or transformed_ring[0] != transformed_ring[-1]:
            raise ValueError("Final AOI outer ring is not a closed polygon.")
        transformed_rings.append(transformed_ring)

    exterior = [(point[0], point[1]) for point in transformed_rings[0]]
    feature = {
        "type": "Feature",
        "properties": {
            "name": "Mohanpura final submission AOI",
            "area_km2": FINAL_AOI_KM2,
            "source": "Final submission Map_Geometry.json",
            "crs_source": EPSG_UTM_43N,
        },
        "geometry": {"type": "Polygon", "coordinates": transformed_rings},
    }
    return feature, bounds_from_points(exterior)


def flight_assets(flight_csv: Path) -> tuple[list[dict[str, str]], dict[str, object], Bounds]:
    """Create final flight CSV/GeoJSON records and validate the row count."""
    rows = read_csv(flight_csv)
    if len(rows) != EXPECTED_FLIGHT_GEOTAGS:
        raise ValueError(
            f"Expected {EXPECTED_FLIGHT_GEOTAGS:,} flight geotags, found {len(rows):,} in {flight_csv}."
        )
    points: list[tuple[float, float]] = []
    features: list[dict[str, object]] = []
    output_rows: list[dict[str, str]] = []
    for row in rows:
        lat = float_value(row, "lat", flight_csv)
        lon = float_value(row, "lon", flight_csv)
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError(f"Invalid WGS 84 flight point: {(lat, lon)!r}")
        photo = row.get("photo", "").strip()
        flight = row.get("flight", "").strip()
        if not photo or not flight:
            raise ValueError(f"Flight geotag lacks photo or flight identifier: {row!r}")
        points.append((lon, lat))
        output_rows.append({"photo": photo, "flight": flight, "lat": f"{lat:.9f}", "lon": f"{lon:.9f}"})
        features.append(
            {
                "type": "Feature",
                "properties": {"photo": photo, "flight": flight},
                "geometry": {"type": "Point", "coordinates": [round(lon, 9), round(lat, 9)]},
            }
        )
    return output_rows, {"type": "FeatureCollection", "features": features}, bounds_from_points(points)


def control_assets(control_csv: Path) -> tuple[dict[str, object], dict[str, int], Bounds]:
    """Create display-ready BM/reference and TBM GeoJSON features."""
    rows = read_csv(control_csv)
    if len(rows) != EXPECTED_CONTROL_POINTS:
        raise ValueError(
            f"Expected {EXPECTED_CONTROL_POINTS:,} final control records, found {len(rows):,} in {control_csv}."
        )
    counts = {"BM/Base": 0, "TBM": 0}
    points: list[tuple[float, float]] = []
    features: list[dict[str, object]] = []
    for row in rows:
        source_type = row.get("PT_TYPE", "").strip()
        display_type = "TBM" if source_type == "TBM" else "BM/Base"
        lat = float_value(row, "LAT_DD", control_csv)
        lon = float_value(row, "LON_DD", control_csv)
        elevation = float_value(row, "ELEV_M", control_csv)
        point_id = row.get("POINT_ID", "").strip()
        if not point_id:
            raise ValueError(f"Control record has no POINT_ID: {row!r}")
        counts[display_type] += 1
        points.append((lon, lat))
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "point_id": point_id,
                    "type": display_type,
                    "source_type": source_type,
                    "source_id": row.get("SRC_ID", "").strip(),
                    "easting": float_value(row, "EAST_M", control_csv),
                    "northing": float_value(row, "NORTH_M", control_csv),
                    "elevation_m": elevation,
                    "date": row.get("OBS_DATE", "").strip(),
                    "inside_aoi": row.get("inside_aoi", "").strip(),
                    "inside_dem": row.get("inside_dem", "").strip(),
                },
                "geometry": {"type": "Point", "coordinates": [round(lon, 9), round(lat, 9)]},
            }
        )
    return {"type": "FeatureCollection", "features": features}, counts, bounds_from_points(points)


def replace_javascript_constant(html: str, name: str, value: object) -> str:
    """Replace an embedded JSON JavaScript constant exactly once."""
    replacement = f"const {name} = {json.dumps(value, separators=(',', ':'))};"
    pattern = rf"const {name} = .*?;"
    updated, count = re.subn(pattern, replacement, html, count=1, flags=re.DOTALL)
    if count != 1:
        raise ValueError(f"Could not replace {name!r} in web map template.")
    return updated


def write_json(path: Path, value: object) -> None:
    """Write deterministic UTF-8 JSON."""
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    """Write normalized final flight geotags."""
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["photo", "flight", "lat", "lon"])
        writer.writeheader()
        writer.writerows(rows)


def build_webmap(
    template_path: Path,
    output_path: Path,
    drone_rows: list[dict[str, str]],
    aoi: dict[str, object],
    controls: dict[str, object],
    bounds: Bounds,
    control_counts: dict[str, int],
) -> None:
    """Refresh the embedded Leaflet map without changing its interaction design."""
    html = template_path.read_text(encoding="utf-8")
    drone_points = [[float(row["lat"]), float(row["lon"])] for row in drone_rows]
    html = replace_javascript_constant(html, "dronePoints", drone_points)
    html = replace_javascript_constant(html, "mohanpuraAoi", aoi)
    html = replace_javascript_constant(html, "dgpsControl", controls)
    html = replace_javascript_constant(
        html,
        "projectBounds",
        [[bounds.min_lat, bounds.min_lon], [bounds.max_lat, bounds.max_lon]],
    )
    html = html.replace("Mohanpura Drone Coverage and Survey Control", "Mohanpura Final Coverage and Survey Control")
    html = html.replace("Mohanpura Drone Coverage", "Mohanpura Final Coverage")
    html = html.replace(
        "<div class=\"metric\"><b>14,871</b><span>Drone photos</span></div>",
        f"<div class=\"metric\"><b>{len(drone_rows):,}</b><span>Final flight geotags</span></div>",
    )
    html = html.replace(
        "<div class=\"metric\"><b>24</b><span>BM/Base</span></div>",
        f"<div class=\"metric\"><b>{control_counts['BM/Base']}</b><span>BM / reference</span></div>",
    )
    html = html.replace(
        "<div class=\"metric\"><b>12</b><span>TBM</span></div>",
        f"<div class=\"metric\"><b>{control_counts['TBM']}</b><span>TBM</span></div>",
    )
    html = html.replace("Drone photograph geotags", "Final flight geotags")
    html = html.replace("Mohanpura AOI outline", "Final submission AOI")
    html = html.replace("'Mohanpura AOI': aoiLayer", "'Final submission AOI': aoiLayer")
    html = html.replace("'Drone photo locations': droneLayer", "'Final flight geotags': droneLayer")
    html = html.replace("'DGPS BM/Base': bmLayer", "'BM / reference': bmLayer")
    output_path.write_text(html, encoding="utf-8")


def main() -> None:
    """Build and validate portable final-submission map assets."""
    args = parse_args()
    app_root = args.app_root.resolve()
    final_root = args.final_root.resolve()
    flight_csv = args.flight_csv.resolve()
    data_dir = app_root / "outputs" / "drone_geotags"
    control_csv = final_root / "03_GIS" / "BM_TBM.csv"
    map_geometry = final_root / "03_GIS" / "Map_Geometry.json"
    template = data_dir / "drone_photo_webmap.html"
    if not app_root.is_dir() or not final_root.is_dir() or not flight_csv.is_file():
        raise FileNotFoundError("App root, final root, or flight CSV does not exist.")
    if not control_csv.is_file() or not map_geometry.is_file() or not template.is_file():
        raise FileNotFoundError("Final control/AOI source or web map template is missing.")

    flights, flight_geojson, flight_bounds = flight_assets(flight_csv)
    aoi, aoi_bounds = aoi_feature(map_geometry)
    controls, control_counts, control_bounds = control_assets(control_csv)
    all_bounds = combine_bounds(flight_bounds, aoi_bounds, control_bounds)

    write_csv(data_dir / "drone_photo_locations.csv", flights)
    write_json(data_dir / "drone_photo_locations.geojson", flight_geojson)
    write_json(data_dir / "mohanpura_aoi.geojson", {"type": "FeatureCollection", "features": [aoi]})
    write_json(data_dir / "mohanpura_dgps_bm_tbm.geojson", controls)
    summary = {
        "source_version": "Final submission · 12 October 2026",
        "source_flight_csv": str(flight_csv),
        "source_control_csv": str(control_csv),
        "source_aoi": str(map_geometry),
        "geotagged_images": len(flights),
        "flight_groups": len({row["flight"] for row in flights}),
        "aoi_km2": FINAL_AOI_KM2,
        "bounds_wgs84": asdict(all_bounds),
        "control_counts": control_counts,
        "outputs": [
            "drone_photo_locations.csv",
            "drone_photo_locations.geojson",
            "mohanpura_aoi.geojson",
            "mohanpura_dgps_bm_tbm.geojson",
            "drone_photo_webmap.html",
        ],
    }
    write_json(data_dir / "summary.json", summary)
    build_webmap(template, template, flights, aoi, controls, all_bounds, control_counts)
    static_map = app_root / "static" / "drone_photo_webmap.html"
    static_map.parent.mkdir(parents=True, exist_ok=True)
    build_webmap(template, static_map, flights, aoi, controls, all_bounds, control_counts)
    write_json(data_dir / "final_sync_manifest.json", {"summary": summary, "validation": "passed"})
    print(
        "Final Streamlit map assets refreshed: "
        f"{len(flights):,} geotags; {control_counts['BM/Base']} BM/reference; "
        f"{control_counts['TBM']} TBM; {FINAL_AOI_KM2:.2f} km² AOI."
    )


if __name__ == "__main__":
    main()
