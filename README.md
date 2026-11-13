[TSEB_Explorer_README.md](https://github.com/user-attachments/files/34785263/TSEB_Explorer_README.md)
# TSEB Model Explorer

**Live example:** https://terraobserver.github.io/tseb-model-explorer/  
**Source repository:** https://github.com/TerraObserver/tseb-model-explorer

A **static, browser-based viewer** for UAV-derived **Two-Source Energy Balance (TSEB)** outputs. It compares the Priestley–Taylor (PT), Penman–Monteith (PM), and Shuttleworth–Wallace (SW) variants for **Rn, H, LE, and G** (W m⁻²) across sites, dates, and UAV flight times. It also displays optional *previously processed* eddy-covariance (EC) validation and daily tower/advection context. The website is a single `index.html` using Leaflet and Chart.js; it runs on GitHub Pages without a backend, database, or Streamlit.

> **Scope:** This repository is for **displaying and packaging model outputs**. It does **not** run pyTSEB, process raw drone imagery, calculate EC footprints, perform tower energy-balance closure corrections, or diagnose advection from raw tower records. Those scientific processing stages must be completed separately.

## 1. What's provided, and what's not

The included research demo has **42 flights** at **3 sites (OLA, VAC, WWF)**: 3 models × 4 fluxes × 42 flights = **504 map PNGs**. It includes the paired per-flight JSON metadata and histograms, plus derived EC validation and daily tower data. You can reproduce the **website display** with these assets immediately.

| Available in this repository | Not available in this repository |
| --- | --- |
| `index.html` and ready-to-display `data/` | Original UAV imagery or original TSEB input rasters |
| 504 rendered PNGs, index, metadata and histograms | Original multiband TSEB GeoTIFFs for the 42 flights |
| Derived, matched TSEB–EC validation data in JSON | Raw EC tower measurements and footprint calculation inputs/scripts |
| Prepared daily tower/advection JSON | Script/criteria used to compute the research advection classification |
| Python converter scripts and **synthetic** example GeoTIFFs (in this reusable release) | TSEB simulation code, weather/soil/canopy inputs and model configurations |

**Important:** The PNGs and derived JSON **cannot** reconstruct the original quantitative GeoTIFFs or the upstream science. Colleagues can use this as a *viewer template* with **their own precomputed, georeferenced TSEB outputs**. Independent replication of the underlying modeling and tower validation requires those separate pipelines and inputs.

## 2. Quick start: open the existing 42-flight demo

**No Python packages are required to view it online.** Open the [live viewer](https://terraobserver.github.io/tseb-model-explorer/).

To serve a downloaded copy locally:

```bash
# Run this inside the directory that contains index.html
python -m http.server 8000
```

Open `http://localhost:8000/` and check the map and EC validation tabs. Python's built-in HTTP server is sufficient; do **not** double-click `index.html` because browser `file://` restrictions often block its JSON requests. Leaflet, Chart.js and OpenStreetMap base tiles load from the internet, so an internet connection is needed for those resources.

## 3. Required software for creating new viewer datasets

For raster conversion and validation JSON preparation (not for viewing the online example):

- **Python 3.10 or newer**; `python --version` (on Windows, `py --version` is an alternative).
- Python packages in [`requirements.txt`](requirements.txt): **NumPy, Rasterio, Affine, Matplotlib, Pillow**. The CSV→EC converter and the data checker only use Python's standard library.
- Three **georeferenced multiband GeoTIFFs per flight**: one PT, one PM, and one SW, with the four bands corresponding to **Rn, H, LE, G** in W m⁻². These must already be computed by your TSEB workflow.
- A browser and internet connection for CDN libraries/base map; Git/GitHub account only if you wish to publish or maintain your own repo.

Recommended virtual environment (run from the repository root):

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS / Linux:    source .venv/bin/activate
python -m pip install -r requirements.txt
```

If PowerShell does not allow activation, use `.venv\Scripts\python.exe` in place of `python` in subsequent commands. **Python/GDAL installation for your TSEB scientific model is a separate task; this website does not require pyTSEB.**

## 4. Fully reproducible practice example (no research data needed)

This release includes three small, **synthetic—not measured—GeoTIFFs** under `examples/sample_tifs/`. They allow anyone to generate a completely new viewer before substituting their own data.

From the downloaded repository root, after the package installation above:

```bash
# 1. Make a separate project; existing 42-flight demo is never overwritten
python scripts/create_starter.py --output my-viewer

# 2. Convert synthetic GeoTIFFs into map overlays, statistics, and JSON
python my-viewer/scripts/build_viewer_data.py --input my-viewer/examples/sample_tifs

# 3. Verify every referenced file (no third-party dependencies)
python my-viewer/scripts/validate_viewer.py

# 4. Start a local web server from the current directory
python -m http.server 8000
```

Open **`http://localhost:8000/my-viewer/`**. Select `DEMO` → `2024-06-19` → `13:00`. Check the three model panels, switch Rn/H/LE/G, inspect histograms, and confirm no missing-image errors.

To exercise the optional validation tab with *synthetic* points, stop the server or use another terminal and run:

```bash
python my-viewer/scripts/build_validation_json.py --csv my-viewer/examples/validation_points_template.csv
python my-viewer/scripts/validate_viewer.py
```

Refresh the viewer. **These demonstration values are invented**; they must never be reported as scientific measurements or model validation. `examples/advection_template.json` is only a JSON structure example and is not enabled automatically.

## 5. Replace the example with YOUR TSEB outputs

Put **all the flights you want to publish** in a folder such as `my-viewer/input_tifs/` (do not commit original large rasters unless you have permission and an explicit data-sharing reason):

```text
my-viewer/input_tifs/
  OLA_20240723_1100_PT.tif
  OLA_20240723_1100_PM.tif
  OLA_20240723_1100_SW.tif
  OLA_20240723_1300_PT.tif
  OLA_20240723_1300_PM.tif
  OLA_20240723_1300_SW.tif
  ...
```

**Strict naming format:** `SITE_YYYYMMDD_HHMM_PT.tif`, `_PM.tif`, or `_SW.tif`. The site name may contain letters/underscores, but each flight ID must have a unique site/date/time and all **three** TSEB models. The builder skips TIFFs whose filenames do not match and fails if any model is missing.

**Required GeoTIFF properties:**

1. **Four numeric bands** (default 1-based order: `Rn=1, H=2, LE=3, G=4`). If the order is different, use `--bands RN H LE G` with your four band numbers.
2. **Same CRS, transform, width and height** for PT/PM/SW within a flight; valid GeoTIFF georeferencing and defined NoData/mask. Different flights may have different extents.
3. **W m⁻²**, with scientifically consistent signs. Input data are not calibrated, converted between units, or processed by the TSEB model here.
4. Check the study-specific **`QA_RANGES`** and **`DISPLAY`** dictionaries near the top of `scripts/build_viewer_data.py` before generating. Values outside `QA_RANGES` are excluded; display limits affect image colors, **not** the raw GeoTIFFs.

Now **explicitly replace** the synthetic demo data inside your new `my-viewer` folder:

```bash
python my-viewer/scripts/build_viewer_data.py --input my-viewer/input_tifs --reset-data
python my-viewer/scripts/validate_viewer.py
```

**Caution:** `--reset-data` deletes **the target project's entire `data/` folder**, including its EC/advection JSON. It does **not** touch the original TSEB GeoTIFF inputs. The script refuses to combine new rasters silently with an existing viewer unless you specify `--reset-data`. Use a new starter folder for practice and do not run the reset against your original research repo inadvertently.

The script renders transparent raster PNGs reprojected to **EPSG:4326**, with matched geographic bounds for Leaflet, and computes per-flight histograms and pixel statistics from screened source values. PNGs are **visualization only**, not quantitative model results. Typical output:

```text
my-viewer/
  index.html
  data/
    index.json
    flights/SITE_YYYYMMDD_HHMM/
      metadata.json
      histograms.json
    rasters/SITE_YYYYMMDD_HHMM_PT_Rn.png
    rasters/...                             # 12 map PNGs per flight
  scripts/
    create_starter.py
    build_viewer_data.py
    build_validation_json.py
    validate_viewer.py
  examples/
  requirements.txt
  README.md
  WORKSHOP.md
```

## 6. EC validation: optional, and processed upstream

**Input:** a CSV with **one record per site × date × time × model × component**, already spatially and temporally matched to the EC tower. Required columns:

```csv
site,date,time,model,component,modeled,tower_corrected
OLA,20240723,1300,PT,LE,410.5,392.2
```

Additional optional columns: `tower_raw`, `EBR`, `closure_error`, `closure_residual_wm2`. See the complete synthetic file `examples/validation_points_template.csv`. Prepare a real `my-viewer/validation.csv` and run:

```bash
python my-viewer/scripts/build_validation_json.py --csv my-viewer/validation.csv
python my-viewer/scripts/validate_viewer.py
```

This writes `data/closure_data_components.json` so the chart can calculate N, RMSE, MAE, mean bias, Pearson *r* and correlation *r²*. For the original demo, the provenance describes a Bowen-ratio-preserving closure adjustment of **H and LE**; the web page does **not** carry it out. `modeled` must be the modeled value for the **relevant footprint**, not a full-image mean. Document the footprint method, tower QA/QC, temporal windows, sign conventions and closure treatment separately.

**Reusing this template does not reproduce the original footprint/closure calculation.** If those processing scripts belong to another project, they must be provided or cited independently.

## 7. Daily tower/advection panel: optional

If you have already analyzed daily tower conditions, prepare `data/advection_data.json` following `examples/advection_template.json`. It is indexed by **site → `YYYY-MM-DD` → `summary` and `timeseries`**, unlike flight dates (`YYYYMMDD`) in `data/index.json`. It displays EC H/LE, available energy, VPD, wind, and your existing advection-classification fields. This viewer **does not estimate advection** or calculate `ADV_SCORE` automatically. Do not reuse the real demo's tower JSON with someone else's fields.

The adapted HTML tolerates missing optional tower/validation JSON and displays a no-data message.

## 8. Publish on GitHub Pages

1. In your own GitHub account, create a **new repository** (or fork this repo) and upload the **contents of your completed `my-viewer/` folder** to its root: `index.html`, `data/`, scripts, examples, README and `requirements.txt`.
2. Verify the repository contains the entire generated `data/` directory—**all `data/rasters/*.png`** and both JSONs per flight—not just `index.html` or `data/index.json`.
3. Go to **Settings → Pages → Build and deployment → Deploy from a branch → `main` → `/ (root)`**; save. Open `https://YOUR_USERNAME.github.io/YOUR_REPOSITORY/`.
4. Verify site/date/time options, map overlays, histograms, both tabs and browser Console/Network for any `404` files. GitHub paths are case sensitive.

The website needs only `index.html` and the generated `data/` folder to be **displayed**. To let colleagues **rebuild or adapt it**, also publish `scripts/`, `requirements.txt`, `examples/`, and this README. The large original GeoTIFFs and sensitive raw tower data can be shared separately by an appropriate research-data mechanism.

## 9. Design, limitations and attribution

**Design:** one static HTML/CSS/JavaScript file, no build system, Leaflet synchronized map views, Chart.js plots and local JSON/PNG assets. A deliberate constraint is **3 fixed model panels and 4 fixed flux components**. Adding other models/variables requires changing the HTML/JavaScript and the preprocessing script, not JSON alone.

**Interpretation:** common color scales improve comparison but can visually saturate values outside their limits. Pixels are summarized after the simple configured range screen. EC model comparisons use **previously computed footprint-matched pairs** and should not be confused with map-wide pixel statistics. Research datasets are public if committed to GitHub Pages.

**Scientific model attribution:** TSEB and implementation background: [Héctor Nieto's pyTSEB](https://github.com/hectornieto/pyTSEB) (not bundled or executed here). If reusing upstream flux-footprint code by [Karem Meza Capcha](https://github.com/KaremMezaCapcha), attribute that original work separately; footprint code is **not** distributed in this viewer.

**License:** A public repository alone does not grant permission to redistribute its code. The repository owner should choose and add a `LICENSE` file before inviting outside redistribution/adaptation.

