"""Build portable Kundaliya drone-progress assets for the Streamlit app."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import geopandas as gpd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-root", type=Path, required=True)
    parser.add_argument("--analysis-root", type=Path, required=True)
    parser.add_argument("--field-package", type=Path)
    return parser.parse_args()


def write_geojson(path: Path, frame: gpd.GeoDataFrame) -> dict:
    frame = frame.to_crs(4326).copy()
    value = json.loads(frame.to_json(drop_id=True, to_wgs84=True))
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return value


def build_webmap(summary: dict, aoi: dict, previous: dict, additional: dict, balance: dict, missions: dict) -> str:
    payloads = {
        "summary": json.dumps(summary, separators=(",", ":")),
        "aoi": json.dumps(aoi, separators=(",", ":")),
        "previous": json.dumps(previous, separators=(",", ":")),
        "additional": json.dumps(additional, separators=(",", ":")),
        "balance": json.dumps(balance, separators=(",", ":")),
        "missions": json.dumps(missions, separators=(",", ":")),
    }
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Kundaliya Drone Survey Progress</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
html,body,#map{{height:100%;margin:0}} body{{font-family:Arial,sans-serif;color:#172026}} .leaflet-container{{background:#eef2f3}}
.legend{{background:rgba(255,255,255,.96);border:1px solid #b8c2cc;border-radius:4px;padding:8px 10px;box-shadow:0 2px 9px rgba(23,32,38,.15);font:11px/1.35 Arial,sans-serif}}
.legend b{{display:block;color:#17365d;font-size:12px;margin-bottom:4px}} .legend-row{{display:flex;align-items:center;gap:7px;margin:3px 0}} .swatch{{width:20px;height:11px;border:1px solid #66788a}}
.leaflet-popup-content{{font:12px/1.45 Arial,sans-serif}} .leaflet-control-layers{{font-size:11px}}
</style></head><body><div id="map"></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script><script>
const summary={payloads['summary']}; const aoi={payloads['aoi']}; const previous={payloads['previous']}; const additional={payloads['additional']}; const balance={payloads['balance']}; const missions={payloads['missions']};
const map=L.map('map',{{preferCanvas:true,zoomControl:false}}); L.control.zoom({{position:'bottomright'}}).addTo(map); L.control.scale({{position:'bottomleft',metric:true,imperial:false}}).addTo(map);
const osm=L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',{{maxZoom:19,attribution:'&copy; OpenStreetMap contributors'}}).addTo(map);
const topo=L.tileLayer('https://{{s}}.tile.opentopomap.org/{{z}}/{{x}}/{{y}}.png',{{maxZoom:17,attribution:'Map data &copy; OpenStreetMap contributors, SRTM | Map style &copy; OpenTopoMap'}});
const satellite=L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}',{{maxZoom:19,attribution:'Tiles &copy; Esri'}});
const previousLayer=L.geoJSON(previous,{{interactive:false,style:{{color:'#28754d',weight:.7,fillColor:'#50a773',fillOpacity:.66}}}}).addTo(map);
const additionalLayer=L.geoJSON(additional,{{interactive:false,style:{{color:'#087c78',weight:.8,fillColor:'#21a6a1',fillOpacity:.78}}}}).addTo(map);
const balanceLayer=L.geoJSON(balance,{{style:{{color:'#a85f00',weight:1.5,fillColor:'#f5b942',fillOpacity:.9}},onEachFeature:(f,l)=>l.bindPopup(`<b>${{f.properties.balance_id||'Balance area'}}</b><br>Estimated balance: ${{Number(f.properties.area_ha||0).toFixed(2)}} ha`)}}).addTo(map);
function missionStyle(f){{const p=Number(f.properties.estimated_covered_pct||0); if(p>=95)return {{color:'#526979',weight:.55,fill:false,opacity:.42}}; if(p>=20)return {{color:'#c56a00',weight:2,fill:false,opacity:1}}; return {{color:'#b42318',weight:2.3,fill:false,opacity:1}};}}
const missionLayer=L.geoJSON(missions,{{style:missionStyle,onEachFeature:(f,l)=>{{const p=f.properties;l.bindPopup(`<b>${{p.controller_name}}</b><br>Sequence: ${{p.sequence}}<br>Planned: ${{Number(p.planned_area_ha).toFixed(2)}} ha<br>Completed: ${{Number(p.estimated_covered_ha).toFixed(2)}} ha (${{Number(p.estimated_covered_pct).toFixed(2)}}%)<br>Balance: ${{Number(p.estimated_balance_ha).toFixed(2)}} ha<br>Status: ${{p.coverage_status}}<br>Priority: ${{p.field_priority}}`)}}}}).addTo(map);
const aoiLayer=L.geoJSON(aoi,{{interactive:false,style:{{color:'#17365d',weight:2.4,fill:false}}}}).addTo(map);
L.control.layers({{'OpenStreetMap':osm,'OpenTopoMap':topo,'Satellite':satellite}},{{'AOI boundary':aoiLayer,'Coverage through sortie 160':previousLayer,'Additional coverage, sorties 161–218':additionalLayer,'Estimated balance':balanceLayer,'R2 mission status':missionLayer}},{{collapsed:true}}).addTo(map);
const Legend=L.Control.extend({{onAdd:()=>{{const d=L.DomUtil.create('div','legend');d.innerHTML='<b>Drone survey status</b><div class="legend-row"><span class="swatch" style="background:#50a773"></span>Coverage through sortie 160</div><div class="legend-row"><span class="swatch" style="background:#21a6a1"></span>Additional coverage</div><div class="legend-row"><span class="swatch" style="background:#f5b942"></span>Estimated balance</div><div class="legend-row"><span class="swatch" style="background:transparent;border:2px solid #b42318"></span>Not covered mission</div>';return d}}}}); new Legend({{position:'topright'}}).addTo(map);
let framed=false; function frameProject(){{const c=map.getContainer();if(c.clientWidth<100||c.clientHeight<100)return;map.invalidateSize();map.fitBounds(summary.bounds_wgs84,{{padding:[24,24],maxZoom:14}});framed=true;}}
new ResizeObserver(()=>{{if(!framed)frameProject();else map.invalidateSize();}}).observe(map.getContainer()); setTimeout(frameProject,200);
</script></body></html>"""


def main() -> None:
    args = parse_args()
    source = args.analysis_root.resolve()
    output = args.app_root.resolve() / "outputs" / "kundaliya" / "coverage"
    output.mkdir(parents=True, exist_ok=True)

    stamp = "25Nov2026"
    gpkg = source / f"Kundaliya_Drone_Coverage_Balance_Analysis_{stamp}.gpkg"
    summary_source = source / f"Kundaliya_Drone_Coverage_Balance_Summary_{stamp}.json"
    summary = json.loads(summary_source.read_text(encoding="utf-8"))

    aoi_frame = gpd.read_file(gpkg, layer="R3_AOI")
    cumulative = gpd.read_file(gpkg, layer="Estimated_Cumulative_Coverage")
    additional = gpd.read_file(gpkg, layer="Additional_Coverage_After_112")
    balance = gpd.read_file(gpkg, layer="Estimated_Balance_Area")
    missions = gpd.read_file(gpkg, layer="R2_Mission_Status")

    previous_geom = cumulative.geometry.iloc[0].difference(additional.geometry.iloc[0]).buffer(0)
    previous = gpd.GeoDataFrame(
        [{"name": "Coverage through sortie 160", "area_ha": round(previous_geom.area / 10000.0, 3), "geometry": previous_geom}],
        crs=cumulative.crs,
    )
    minx, miny, maxx, maxy = aoi_frame.to_crs(4326).total_bounds
    summary["bounds_wgs84"] = [[miny, minx], [maxy, maxx]]
    summary["previous_baseline_covered_area_ha"] = round(previous_geom.area / 10000.0, 2)
    summary["progress_gain_percentage_points"] = round(
        summary["cumulative_estimated_covered_percent"] - (previous_geom.area / aoi_frame.geometry.iloc[0].area * 100.0), 2
    )

    aoi_json = write_geojson(output / "coverage_aoi.geojson", aoi_frame)
    previous_json = write_geojson(output / "coverage_previous.geojson", previous)
    additional_json = write_geojson(output / "coverage_additional.geojson", additional)
    balance_json = write_geojson(output / "coverage_balance.geojson", balance)
    missions_json = write_geojson(output / "coverage_mission_status.geojson", missions)
    (output / "coverage_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (output / "coverage_webmap.html").write_text(
        build_webmap(summary, aoi_json, previous_json, additional_json, balance_json, missions_json),
        encoding="utf-8",
    )

    copies = {
        source / f"Kundaliya_Drone_Coverage_Balance_Map_{stamp}.png": "Kundaliya_Drone_Coverage_Balance_Map_25Nov2026.png",
        source / f"Kundaliya_Drone_Coverage_Balance_Map_{stamp}.pdf": "Kundaliya_Drone_Coverage_Balance_Map_25Nov2026.pdf",
        source / f"Kundaliya_All_Sortie_Register_{stamp}.csv": "Kundaliya_All_Sortie_Register_25Nov2026.csv",
        source / f"Kundaliya_R2_Mission_Coverage_Balance_Register_{stamp}.csv": "Kundaliya_R2_Mission_Coverage_Balance_Register_25Nov2026.csv",
        source / f"Kundaliya_Field_Balance_Mission_List_{stamp}.csv": "Kundaliya_Field_Balance_Mission_List_25Nov2026.csv",
        source / f"Kundaliya_Estimated_Balance_Area_Field_{stamp}.kml": "Kundaliya_Estimated_Balance_Area_Field_25Nov2026.kml",
        source / f"Kundaliya_Estimated_Cumulative_Coverage_{stamp}.kml": "Kundaliya_Estimated_Cumulative_Coverage_25Nov2026.kml",
        gpkg: "Kundaliya_Drone_Coverage_Balance_Analysis_25Nov2026.gpkg",
    }
    if args.field_package:
        copies[args.field_package.resolve()] = "Kundaliya_Drone_Coverage_Balance_Field_Package_25Nov2026.zip"
    for source_path, output_name in copies.items():
        shutil.copy2(source_path, output / output_name)

    print(
        f"Built Kundaliya coverage assets: {summary['total_sortie_folders']} sorties, "
        f"{summary['cumulative_estimated_covered_percent']:.2f}% covered, "
        f"{summary['estimated_balance_area_ha']:.2f} ha balance."
    )


if __name__ == "__main__":
    main()
