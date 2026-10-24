"""Build portable Kundaliya flight-plan and control assets for Streamlit."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path


KML_NS = {"k": "http://www.opengis.net/kml/2.2"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-root", type=Path, required=True)
    parser.add_argument("--plan-root", type=Path, required=True)
    parser.add_argument("--bm-kml", type=Path, required=True)
    parser.add_argument("--tbm-kml", type=Path, required=True)
    return parser.parse_args()


def coordinates(text: str | None) -> list[list[float]]:
    if not text:
        return []
    points = []
    for token in text.split():
        parts = token.split(",")
        if len(parts) >= 2:
            points.append([round(float(parts[0]), 9), round(float(parts[1]), 9)])
    return points


def placemark_name(placemark: ET.Element) -> str:
    return (placemark.findtext("k:name", default="", namespaces=KML_NS) or "").strip()


def polygon_features(path: Path, mission_rows: dict[str, dict[str, str]]) -> list[dict]:
    root = ET.parse(path).getroot()
    features = []
    for placemark in root.findall(".//k:Placemark", KML_NS):
        name = placemark_name(placemark)
        if not name.startswith("KUN-M"):
            continue
        rings = []
        outer = placemark.find(".//k:outerBoundaryIs/k:LinearRing/k:coordinates", KML_NS)
        outer_ring = coordinates(outer.text if outer is not None else None)
        if len(outer_ring) < 4:
            raise ValueError(f"Mission {name} has an invalid polygon.")
        rings.append(outer_ring)
        for inner in placemark.findall(".//k:innerBoundaryIs/k:LinearRing/k:coordinates", KML_NS):
            ring = coordinates(inner.text)
            if len(ring) >= 4:
                rings.append(ring)
        row = mission_rows.get(name, {})
        properties = {
            "mission_id": name,
            "sequence": int(row.get("sequence", "0") or 0),
            "area_ha": round(float(row.get("area_ha", "0") or 0), 2),
            "river_chainage_m": round(float(row.get("river_chainage_m", "0") or 0), 1),
            "bank_side": row.get("bank_side", ""),
            "nodes": int(row.get("nodes", "0") or 0),
            "tbm_id": row.get("tbm_id", ""),
            "bm_id": row.get("pbm_id", ""),
        }
        features.append({"type": "Feature", "properties": properties, "geometry": {"type": "Polygon", "coordinates": rings}})
    return features


def first_polygon(path: Path) -> dict:
    root = ET.parse(path).getroot()
    placemark = root.find(".//k:Placemark", KML_NS)
    if placemark is None:
        raise ValueError(f"No AOI placemark found in {path}.")
    outer = placemark.find(".//k:outerBoundaryIs/k:LinearRing/k:coordinates", KML_NS)
    ring = coordinates(outer.text if outer is not None else None)
    if len(ring) < 4:
        raise ValueError("Kundaliya AOI polygon is invalid.")
    return {
        "type": "Feature",
        "properties": {"name": placemark_name(placemark) or "Kundaliya smoothed PMF AOI"},
        "geometry": {"type": "Polygon", "coordinates": [ring]},
    }


def point_features(path: Path, point_type: str) -> list[dict]:
    root = ET.parse(path).getroot()
    features = []
    for placemark in root.findall(".//k:Placemark", KML_NS):
        point = placemark.find(".//k:Point/k:coordinates", KML_NS)
        coords = coordinates(point.text if point is not None else None)
        if not coords:
            continue
        features.append(
            {
                "type": "Feature",
                "properties": {"point_id": placemark_name(placemark), "type": point_type},
                "geometry": {"type": "Point", "coordinates": coords[0]},
            }
        )
    return features


def read_register(path: Path) -> tuple[list[dict[str, str]], dict[str, dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    return rows, {row["controller_name"]: row for row in rows}


def bounds(features: list[dict]) -> list[list[float]]:
    points = []
    for feature in features:
        geometry = feature["geometry"]
        if geometry["type"] == "Point":
            points.append(geometry["coordinates"])
        else:
            points.extend(geometry["coordinates"][0])
    lons = [point[0] for point in points]
    lats = [point[1] for point in points]
    return [[min(lats), min(lons)], [max(lats), max(lons)]]


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_webmap(summary: dict, missions: dict, aoi: dict, controls: dict) -> str:
    payloads = {
        "summary": json.dumps(summary, separators=(",", ":")),
        "missions": json.dumps(missions, separators=(",", ":")),
        "aoi": json.dumps(aoi, separators=(",", ":")),
        "controls": json.dumps(controls, separators=(",", ":")),
    }
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Kundaliya Flight Planning and Survey Control</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
html,body,#map{{height:100%;margin:0}} body{{font-family:Arial,sans-serif;color:#172026}} .leaflet-container{{background:#eef2f3}}
.panel{{display:none;position:absolute;z-index:1000;top:12px;left:12px;width:350px;max-width:calc(100vw - 48px);background:rgba(255,255,255,.96);border:1px solid #b8c2cc;border-radius:6px;padding:12px 14px;box-shadow:0 3px 14px rgba(23,32,38,.18)}}
.panel h1{{font-size:17px;margin:0 0 8px;color:#0b1f2a}} .panel p{{font-size:12.5px;margin:5px 0}} .metrics{{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin:10px 0}} .metric{{border:1px solid #d6dde3;border-radius:6px;padding:7px;background:#f8fafb}} .metric b{{display:block;font-size:15px}} .metric span{{font-size:10.5px;color:#53616d}}
.legend{{display:flex;align-items:center;gap:7px}} .swatch{{width:20px;height:10px;display:inline-block}} .aoi{{border:3px solid #005f73}} .mission{{background:#2d806c80;border:1px solid #14532d}} .bm{{width:12px;height:12px;border-radius:50%;background:#1d4ed8;border:2px solid white}} .tbm{{width:0;height:0;border-left:7px solid transparent;border-right:7px solid transparent;border-bottom:13px solid #f59e0b}}
.control-marker{{transform:translate(-50%,-50%)}} .control-marker.bm{{width:14px;height:14px;border-radius:50%;background:#1d4ed8;border:2px solid white;box-shadow:0 0 0 1px #1e3a8a}} .control-marker.tbm{{width:0;height:0;border-left:9px solid transparent;border-right:9px solid transparent;border-bottom:16px solid #f59e0b;filter:drop-shadow(0 1px 2px #92400e)}}
.leaflet-tooltip.control-label,.leaflet-tooltip.mission-label{{background:rgba(255,255,255,.92);border:1px solid #b8c2cc;border-radius:4px;box-shadow:none;font:700 10px/1 Arial,sans-serif;padding:3px 4px}} .leaflet-tooltip.control-label:before,.leaflet-tooltip.mission-label:before{{display:none}}
@media(max-width:700px){{.panel{{width:290px}}.metrics{{grid-template-columns:repeat(2,1fr)}}}}
</style></head><body><div id="map"></div><div class="panel"><h1>Kundaliya Flight Planning and Survey Control</h1>
<div class="metrics"><div class="metric"><b>{summary['mission_count']}</b><span>Flight missions</span></div><div class="metric"><b>{summary['smoothed_aoi_ha']:,.1f}</b><span>AOI hectares</span></div><div class="metric"><b>{summary['coverage_pct']:.2f}%</b><span>Planned coverage</span></div><div class="metric"><b>{summary['bm_count']}</b><span>BM points</span></div><div class="metric"><b>{summary['tbm_count']}</b><span>TBM points</span></div><div class="metric"><b>{summary['maximum_mission_area_ha']:.1f} ha</b><span>Maximum mission</span></div></div>
<p class="legend"><span class="swatch aoi"></span>100 m-smoothed PMF AOI</p><p class="legend"><span class="swatch mission"></span>Controller mission boundary</p><p class="legend"><span class="bm"></span>DGPS BM</p><p class="legend"><span class="tbm"></span>DGPS TBM</p></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script><script>
const summary={payloads['summary']}; const missions={payloads['missions']}; const aoi={payloads['aoi']}; const controls={payloads['controls']};
const map=L.map('map',{{preferCanvas:true,zoomControl:false}}); L.control.zoom({{position:'bottomright'}}).addTo(map); L.control.scale({{position:'bottomleft',metric:true,imperial:false}}).addTo(map);
const osm=L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',{{maxZoom:19,attribution:'&copy; OpenStreetMap contributors'}}).addTo(map);
const topo=L.tileLayer('https://{{s}}.tile.opentopomap.org/{{z}}/{{x}}/{{y}}.png',{{maxZoom:17,attribution:'Map data &copy; OpenStreetMap contributors, SRTM | Map style &copy; OpenTopoMap'}});
const satellite=L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}',{{maxZoom:19,attribution:'Tiles &copy; Esri'}});
const aoiLayer=L.geoJSON(aoi,{{interactive:false,style:{{color:'#005f73',weight:3,fill:false}}}}).addTo(map);
const missionLayer=L.geoJSON(missions,{{style:{{color:'#14532d',weight:1.2,fillColor:'#2d806c',fillOpacity:.25}},onEachFeature:(f,l)=>{{const p=f.properties;l.bindPopup(`<b>${{p.mission_id}}</b><br>Area: ${{p.area_ha.toFixed(2)}} ha<br>Chainage: ${{p.river_chainage_m.toLocaleString()}} m<br>Bank: ${{p.bank_side||'—'}}<br>Nodes: ${{p.nodes}}<br>BM: ${{p.bm_id||'—'}} | TBM: ${{p.tbm_id||'—'}}`);l.bindTooltip(p.mission_id,{{className:'mission-label',sticky:true}})}}}}).addTo(map);
const bmLayer=L.layerGroup(),tbmLayer=L.layerGroup(); controls.features.forEach(f=>{{const p=f.properties,g=f.geometry.coordinates,isTbm=p.type==='TBM';const icon=L.divIcon({{className:`control-marker ${{isTbm?'tbm':'bm'}}`,iconSize:isTbm?[18,16]:[16,16],iconAnchor:isTbm?[9,15]:[8,8]}});const marker=L.marker([g[1],g[0]],{{icon}}).bindTooltip(p.point_id,{{direction:'right',offset:[7,0],className:'control-label'}}).bindPopup(`<b>${{p.point_id}}</b><br>${{p.type}}`);marker.addTo(isTbm?tbmLayer:bmLayer)}}); bmLayer.addTo(map);tbmLayer.addTo(map);
L.control.layers({{'OpenStreetMap':osm,'OpenTopoMap':topo,'Satellite':satellite}},{{'100 m-smoothed PMF AOI':aoiLayer,'Flight missions':missionLayer,'DGPS BM':bmLayer,'DGPS TBM':tbmLayer}},{{collapsed:true}}).addTo(map);
let framed=false;
function frameProject(){{
  const container=map.getContainer();
  if(container.clientWidth<100||container.clientHeight<100)return;
  map.invalidateSize();
  map.fitBounds(summary.bounds_wgs84,{{padding:[25,25],maxZoom:14}});
  framed=true;
}}
new ResizeObserver(()=>{{if(!framed)frameProject();else map.invalidateSize();}}).observe(map.getContainer());
setTimeout(frameProject,200);
</script></body></html>"""


def main() -> None:
    args = parse_args()
    root = args.plan_root.resolve()
    output = args.app_root.resolve() / "outputs" / "kundaliya"
    output.mkdir(parents=True, exist_ok=True)
    combined = root / "Kundaliya_Final_Flight_Plan_R0_Combined.kml"
    aoi_path = root / "Kundaliya_Final_Smoothed_PMF_AOI_100m.kml"
    register_path = root / "Kundaliya_Final_Mission_Register_R0.csv"
    summary_path = root / "Kundaliya_Final_R0_Summary.json"
    rows, row_lookup = read_register(register_path)
    missions_list = polygon_features(combined, row_lookup)
    if len(missions_list) != 108 or len(rows) != 108:
        raise ValueError(f"Expected 108 Kundaliya missions; found {len(missions_list)} polygons and {len(rows)} register rows.")
    aoi_feature = first_polygon(aoi_path)
    bm = point_features(args.bm_kml.resolve(), "BM")
    tbm = point_features(args.tbm_kml.resolve(), "TBM")
    controls_list = bm + tbm
    source_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    all_features = missions_list + [aoi_feature] + controls_list
    summary = {
        **source_summary,
        "source_version": "Kundaliya Flight Plan R0 · 24 October 2026",
        "mission_count": len(missions_list),
        "bm_count": len(bm),
        "tbm_count": len(tbm),
        "bounds_wgs84": bounds(all_features),
    }
    missions = {"type": "FeatureCollection", "features": missions_list}
    aoi = {"type": "FeatureCollection", "features": [aoi_feature]}
    controls = {"type": "FeatureCollection", "features": controls_list}
    write_json(output / "kundaliya_flight_missions.geojson", missions)
    write_json(output / "kundaliya_aoi.geojson", aoi)
    write_json(output / "kundaliya_bm_tbm.geojson", controls)
    write_json(output / "summary.json", summary)
    (output / "kundaliya_webmap.html").write_text(build_webmap(summary, missions, aoi, controls), encoding="utf-8")
    copies = {
        combined: "Kundaliya_Final_Flight_Plan_R0_Combined.kml",
        root / "Kundaliya_Final_Flight_Plan_R0_Combined.kmz": "Kundaliya_Final_Flight_Plan_R0_Combined.kmz",
        root / "Kundaliya_Final_Controller_KML_R0.zip": "Kundaliya_Final_Controller_KML_R0.zip",
        register_path: "Kundaliya_Final_Mission_Register_R0.csv",
        args.bm_kml.resolve(): "Kundaliya_BM.kml",
        args.tbm_kml.resolve(): "Kundaliya_TBM.kml",
    }
    for source, name in copies.items():
        shutil.copy2(source, output / name)
    print(f"Built Kundaliya app assets: {len(missions_list)} missions, {len(bm)} BM, {len(tbm)} TBM.")


if __name__ == "__main__":
    main()
