[TSEB_Model_Explorer_README.md](https://github.com/user-attachments/files/34772153/TSEB_Model_Explorer_README.md)
# TSEB Model Explorer

**Live viewer:** https://terraobserver.github.io/tseb-model-explorer/  
**Source code:** https://github.com/TerraObserver/tseb-model-explorer

A lightweight, static web viewer for exploring UAV-derived **Two-Source Energy Balance (TSEB)** results across sites, flight dates, and times. It compares three TSEB formulations—**Priestley–Taylor (PT), Penman–Monteith (PM), and Shuttleworth–Wallace (SW)**—and optionally connects them to eddy covariance (EC) observations. It is built with HTML, JavaScript, [Leaflet](https://leafletjs.com/), and [Chart.js](https://www.chartjs.org/), and is hosted on GitHub Pages. **No backend or database server is needed.**

## 1. What does the viewer show?

**TSEB Explorer**
- Three synchronized maps (PT / PM / SW) for **Rn, H, LE, and G** (W m⁻²).
- Site → date → flight time selection, with common display limits for comparing models.
- Per-model pixel distributions and summary statistics (mean, median, standard deviation, P01, P99).
- Optional *daily* EC-tower context with H, LE, available energy (Rn − G), and an upstream-defined advection diagnostic.

**TSEB–EC Validation**
- Modeled TSEB versus **energy-balance-closure-corrected** EC measurements for Rn, H, LE, and G.
- Component-level N, RMSE, MAE, bias, Pearson r, and r².
- The displayed **bias = modeled − corrected tower**; **r² is Pearson correlation squared**, not a measure of agreement with the 1:1 line.

The demonstration dataset includes **42 flights across three sites (OLA, VAC, WWF)**, each with three model outputs and four energy-flux maps. The viewer is a **visualization layer**: it neither runs pyTSEB nor calculates footprint-weighted fluxes or performs EC closure corrections.

## 2. Build your own viewer with TSEB outputs

### A. Copy the website

Fork this repository to your GitHub account, or download its ZIP. The website itself is `index.html`; it loads files from `data/`. You can first open the public live viewer and explore the existing example without installing anything.

For local preparation (Python 3.10+ recommended):

```bash
git clone https://github.com/TerraObserver/tseb-model-explorer.git
cd tseb-model-explorer
python -m pip install -r requirements.txt
```

### B. Prepare a few TSEB GeoTIFFs

Place your **already computed** multiband TSEB GeoTIFFs in `input_tifs/`, using this naming convention:

```text
input_tifs/
  OLA_20240723_1300_PT.tif
  OLA_20240723_1300_PM.tif
  OLA_20240723_1300_SW.tif
```

- `OLA` = site ID; `20240723` = flight date; `1300` = flight time; `PT/PM/SW` = model.
- Each GeoTIFF should contain the same four variables. The default 1-based band mapping is **Rn=1, H=2, LE=3, G=4**; override with `--bands RN H LE G` if needed.
- PT, PM and SW rasters must share a CRS, resolution, spatial extent, and pixel grid; the input GeoTIFFs must have a valid CRS.
- The script applies simple finite-value and range screening. **Review the `QA_RANGES` and `DISPLAY` dictionaries in `scripts/build_viewer_data.py` for your analysis**, especially if your flux ranges or units differ.

Create the viewer-ready static data:

```bash
python scripts/build_viewer_data.py --input input_tifs --reset-data
```

**Important:** `--reset-data` **deletes the existing `data/` folder**, including the demonstration rasters and optional tower JSON files. Only use it in a fork/local copy once you are ready to replace the demo. Back up any data you want to keep. Without this flag, the index is rebuilt but older files may remain on disk; do **not** publish the original demo's tower JSON alongside your new flights.

The builder reprojects map images to **EPSG:4326**, writes transparent PNG overlays and per-flight statistics/histograms, and creates `data/index.json`. Pixel statistics are from screened source values; PNGs are for **display, not quantitative raster analysis**.

### C. Test locally

From the repository root:

```bash
python -m http.server 8000
```

Open **http://localhost:8000/** in your browser. Use the dropdowns to test sites, dates, times, and components. A local HTTP server is necessary because the browser typically restricts `fetch()` when `index.html` is opened directly with `file://`.

### D. Optional: add your EC validation data

The validation tab needs one point per **site × date × time × model × component**. Create a CSV with at least:

```csv
site,date,time,model,component,modeled,tower_corrected
OLA,20240723,1300,PT,LE,410.5,392.2
```

`modeled` should be the model flux evaluated for the relevant **EC footprint**, not the simple map-wide mean; `tower_corrected` must be calculated upstream using your documented closure method. See `examples/validation_points_template.csv` for the optional fields.

```bash
python scripts/build_validation_json.py --csv my_ec_validation.csv
```

This creates `data/closure_data_components.json`. The script only **formats an already matched/validated dataset**. It does not compute tower corrections, choose time windows, or model footprints. If the JSON is absent, the enhanced viewer displays a no-data message instead of failing.

### E. Optional: add daily tower/advection context

Use `examples/advection_template.json` as the schema for `data/advection_data.json`. Its structure is `sites → SITE → YYYY-MM-DD → {summary, timeseries}`, with hourly/daytime values for H, LE, available energy, VPD, wind and any existing **research-defined** advection flags. The viewer **does not diagnose advection** from raw tower measurements. If this file is absent, the daily-context panel simply reports no data.

### F. Publish your own viewer

Commit the updated `data/`, `index.html`, the scripts, and this README to your fork. In **GitHub repository → Settings → Pages**, publish from the `main` branch and the `/ (root)` folder (or adapt to your GitHub Pages setup). Your site will be hosted under a URL like:

`https://YOUR_USERNAME.github.io/tseb-model-explorer/`

No Streamlit, server, API credentials, or running computer is required once deployed.

## 3. How the files connect

```text
index.html                        # Interface + Leaflet/Chart.js code
scripts/
  build_viewer_data.py           # GeoTIFF → PNG + metadata + histograms + index
  build_validation_json.py       # Prepared TSEB–EC CSV → validation JSON
examples/                        # Optional sample formats, not research results
requirements.txt                 # Python dependencies for data preparation only
data/
  index.json                     # Lists sites, dates, flights, variables, display scales
  flights/SITE_YYYYMMDD_HHMM/
    metadata.json                # Geographic bounds, PNG paths, QA/QC, pixel statistics
    histograms.json              # Binned distributions for PT, PM, SW
  rasters/*.png                  # Display images positioned by Leaflet
  closure_data_components.json  # Optional footprint-matched TSEB–EC validation
  advection_data.json           # Optional daily tower/advection diagnostics
```

**Data flow:** TSEB GeoTIFFs → Python preprocessing → PNG + JSON → `index.html` → browser. Independently, footprint-matched TSEB/EC and daily-tower analyses → optional JSON → validation/context tabs.

## 4. Notes for research reuse

- **Do not substitute** PNG pixel colors for flux values; retain the original GeoTIFFs for scientific processing.
- Ensure **matching timestamps**, consistent units/sign conventions, footprint aggregation, tower data QA/QC, and a documented energy-balance closure correction before interpreting validation results.
- The original demonstration JSON describes a **Bowen-ratio-preserving correction** for H and LE while leaving Rn and G unchanged. This is an example, not an automatic correction performed by the website.
- A common display scale aids side-by-side visual comparison but may clip visually saturated extremes. Pixel statistics are computed from screened source values, not color-clipped PNGs.
- The geographic PNG overlays are rendered in EPSG:4326 for Leaflet. Source GeoTIFF coordinates and pixel values remain independent of this display transformation.
- All published JSON and PNG assets are publicly downloadable. Avoid uploading confidential locations, private EC records, or local machine paths in metadata.
- The HTML includes **three fixed model panels (PT, PM, SW)** and **four fixed flux selections**. To use another model or variable, edit those interface elements and corresponding JavaScript references; changing JSON alone is insufficient.

**Scientific software background:** [pyTSEB — Héctor Nieto](https://github.com/hectornieto/pyTSEB). The scripts here process precomputed model outputs; no pyTSEB source code is included.

## 5. Suggested 10-minute demonstration

1. **Show the website** (1 min): choose a site, date, time, then compare PT/PM/SW for LE.
2. **Explain the data flow** (2 min): point to `index.html`, `data/index.json`, one `metadata.json`, and one PNG.
3. **Build one new flight** (4 min): copy three GeoTIFFs; run the builder; refresh the local page.
4. **Discuss EC integration** (2 min): separate footprint validation and daily tower context from the maps.
5. **Publish** (1 min): push the fork and show the GitHub Pages setting.

Start with **one flight and only map products**. Add tower validation once its matching and correction are complete.

**Reuse permissions:** Publishing a repository publicly is not the same as adding an open-source license. If you want colleagues to redistribute or adapt the code outside GitHub, add a `LICENSE` file (for example, MIT) after choosing the terms you prefer.
