# Mohanpura Drone Coverage Streamlit Map

Streamlit web map for reviewing Mohanpura drone photo geotags, AOI coverage, and DGPS BM/TBM control points.

## Run Locally

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Deploy On Streamlit Cloud

This repository is ready for Streamlit Cloud deployment.

1. Open Streamlit Cloud.
2. Create a new app from this GitHub repository.
3. Use `streamlit_app.py` as the app entry point.

Local start command:

```bash
streamlit run streamlit_app.py
```

## Data Layers

- Drone photo geotags: `outputs/drone_geotags/drone_photo_locations.csv`
- Mohanpura AOI: `outputs/drone_geotags/mohanpura_aoi.geojson`
- DGPS BM/TBM: `outputs/drone_geotags/mohanpura_dgps_bm_tbm.geojson`
