from pathlib import Path
import json
import math

import numpy as np
import pandas as pd
import rasterio
from rasterio.warp import transform_bounds

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


# ============================================================
# PATHS
# ============================================================

SCRIPT_DIR = Path(__file__).resolve().parent

MANIFEST_CSV = (
    SCRIPT_DIR
    / "tseb_manifest.csv"
)

WEB_DIR = (
    SCRIPT_DIR
    / "web"
)

DATA_DIR = (
    WEB_DIR
    / "data"
)

RASTER_DIR = (
    DATA_DIR
    / "rasters"
)

FLIGHTS_DIR = (
    DATA_DIR
    / "flights"
)

INDEX_JSON = (
    DATA_DIR
    / "index.json"
)


# ============================================================
# SETTINGS
# ============================================================

MODELS = ["PT", "PM", "SW"]

VARIABLES = {
    "Rn": {
        "band": 1,
        "vmin": 0.0,
        "vmax": 850.0,
        "cmap": "viridis",
        "units": "W m-2",
    },
    "H": {
        "band": 2,
        "vmin": -500.0,
        "vmax": 550.0,
        "cmap": "coolwarm",
        "units": "W m-2",
    },
    "LE": {
        "band": 3,
        "vmin": -200.0,
        "vmax": 1100.0,
        "cmap": "turbo",
        "units": "W m-2",
    },
    "G": {
        "band": 4,
        "vmin": -100.0,
        "vmax": 250.0,
        "cmap": "coolwarm",
        "units": "W m-2",
    },
}

HISTOGRAM_BINS = 60

# Broad QA/QC screening limits used consistently with validation.
# These are screening limits, not theoretical physical bounds.
QA_RANGES = {
    "Rn": (-200.0, 1200.0),
    "H":  (-700.0, 1000.0),
    "LE": (-300.0, 1500.0),
    "G":  (-300.0, 600.0),
}

# Expected site CRS used only as QA warning.
# Raster bounds are always calculated from the actual src.crs.
EXPECTED_SITE_EPSG = {
    "OLA": 6419,
    "VAC": 6417,
    "WWF": 6417,
}


# ============================================================
# HELPERS
# ============================================================

def json_safe_number(value):
    """Convert numpy numbers to normal JSON-safe Python numbers."""
    if value is None:
        return None

    value = float(value)

    if not math.isfinite(value):
        return None

    return value


def apply_qaqc(data, variable):
    """
    Apply finite/NoData + variable-specific QA/QC screening.
    Returns:
      filtered_data,
      n_finite_before,
      n_valid_after,
      n_range_rejected
    """

    arr = np.asarray(data, dtype=np.float32)

    finite_mask = np.isfinite(arr)
    n_finite_before = int(finite_mask.sum())

    qmin, qmax = QA_RANGES[variable]

    range_mask = (
        finite_mask
        & (arr >= qmin)
        & (arr <= qmax)
    )

    n_valid_after = int(range_mask.sum())
    n_range_rejected = int(
        n_finite_before - n_valid_after
    )

    filtered = np.where(
        range_mask,
        arr,
        np.nan
    ).astype(np.float32)

    return (
        filtered,
        n_finite_before,
        n_valid_after,
        n_range_rejected,
    )


def calculate_stats(values):
    """
    Statistics for valid finite raster pixels.
    """

    values = np.asarray(values, dtype=np.float64)
    values = values[np.isfinite(values)]

    if values.size == 0:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "std": None,
            "min": None,
            "max": None,
            "p01": None,
            "p05": None,
            "p95": None,
            "p99": None,
        }

    return {
        "count": int(values.size),
        "mean": json_safe_number(np.mean(values)),
        "median": json_safe_number(np.median(values)),
        "std": json_safe_number(np.std(values)),
        "min": json_safe_number(np.min(values)),
        "max": json_safe_number(np.max(values)),
        "p01": json_safe_number(np.percentile(values, 1)),
        "p05": json_safe_number(np.percentile(values, 5)),
        "p95": json_safe_number(np.percentile(values, 95)),
        "p99": json_safe_number(np.percentile(values, 99)),
    }


def calculate_histogram(values, bins=HISTOGRAM_BINS):
    """
    Histogram for frontend plots.
    """

    values = np.asarray(values, dtype=np.float64)
    values = values[np.isfinite(values)]

    if values.size == 0:
        return {
            "bin_edges": [],
            "bin_centers": [],
            "counts": [],
        }

    counts, edges = np.histogram(
        values,
        bins=bins
    )

    centers = (
        edges[:-1]
        + edges[1:]
    ) / 2.0

    return {
        "bin_edges": [
            json_safe_number(x)
            for x in edges
        ],
        "bin_centers": [
            json_safe_number(x)
            for x in centers
        ],
        "counts": [
            int(x)
            for x in counts
        ],
    }


def raster_bounds_wgs84(src):
    """
    Return Leaflet bounds from actual raster CRS.

    Output order:
    [[south, west], [north, east]]
    """

    if src.crs is None:
        raise ValueError(
            "Raster has no CRS."
        )

    left, bottom, right, top = transform_bounds(
        src.crs,
        "EPSG:4326",
        *src.bounds,
        densify_pts=21
    )

    return [
        [float(bottom), float(left)],
        [float(top), float(right)],
    ]


def save_transparent_png(
    data,
    output_path,
    vmin,
    vmax,
    cmap_name
):
    """
    Save a georeferenced raster band as transparent PNG.

    Invalid pixels are fully transparent.
    Valid pixels are colorized using fixed display limits.
    """

    data = np.asarray(
        data,
        dtype=np.float32
    )

    valid = np.isfinite(data)

    clipped = np.clip(
        data,
        vmin,
        vmax
    )

    normalized = (
        clipped - vmin
    ) / (
        vmax - vmin
    )

    cmap = matplotlib.colormaps[
        cmap_name
    ]

    rgba = cmap(normalized)

    # Alpha = 0 for invalid pixels
    rgba[..., 3] = valid.astype(float)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    plt.imsave(
        output_path,
        rgba
    )


def validate_model_paths(row):
    """
    Return model -> TIFF path.
    """

    paths = {
        "PT": Path(row["pt_path"]),
        "PM": Path(row["pm_path"]),
        "SW": Path(row["sw_path"]),
    }

    missing = [
        f"{model}: {path}"
        for model, path in paths.items()
        if not path.exists()
    ]

    if missing:
        raise FileNotFoundError(
            "Missing TSEB files:\n"
            + "\n".join(missing)
        )

    return paths


# ============================================================
# INITIALIZE
# ============================================================

if not MANIFEST_CSV.exists():
    raise FileNotFoundError(
        f"Manifest not found:\n{MANIFEST_CSV}"
    )

RASTER_DIR.mkdir(
    parents=True,
    exist_ok=True
)

FLIGHTS_DIR.mkdir(
    parents=True,
    exist_ok=True
)

manifest = pd.read_csv(
    MANIFEST_CSV,
    dtype={
        "flight_id": str,
        "site": str,
        "date": str,
        "time": str,
    }
)

required_columns = {
    "flight_id",
    "site",
    "date",
    "time",
    "pt_path",
    "pm_path",
    "sw_path",
}

missing_columns = (
    required_columns
    - set(manifest.columns)
)

if missing_columns:
    raise ValueError(
        "Manifest is missing columns: "
        + ", ".join(
            sorted(missing_columns)
        )
    )


# ============================================================
# PROCESS FLIGHTS
# ============================================================

index = {
    "version": 1,
    "variables": {
        variable: {
            "units": settings["units"],
            "display_min": settings["vmin"],
            "display_max": settings["vmax"],
            "colormap": settings["cmap"],
        }
        for variable, settings
        in VARIABLES.items()
    },
    "models": MODELS,
    "qa_qc_ranges": {
        variable: {
            "min": limits[0],
            "max": limits[1],
        }
        for variable, limits in QA_RANGES.items()
    },
    "sites": {},
    "flights": [],
}

processed = 0
failed = 0


for _, row in manifest.iterrows():

    flight_id = str(
        row["flight_id"]
    )

    site = str(
        row["site"]
    ).upper()

    date = str(
        row["date"]
    )

    time = str(
        row["time"]
    ).zfill(4)

    print(
        "\n===================================="
    )

    print(
        f"{flight_id}"
    )

    print(
        "===================================="
    )

    try:

        model_paths = validate_model_paths(
            row
        )

        flight_metadata = {
            "flight_id": flight_id,
            "site": site,
            "date": date,
            "time": time,
            "models": {},
        }

        flight_histograms = {
            "flight_id": flight_id,
            "site": site,
            "date": date,
            "time": time,
            "models": {},
        }

        reference_shape = None
        reference_transform = None
        reference_crs = None
        reference_bounds = None

        for model in MODELS:

            tif_path = model_paths[
                model
            ]

            print(
                f"{model}: {tif_path.name}"
            )

            model_metadata = {
                "source_file": tif_path.name,
                "source_path": str(tif_path),
                "variables": {},
            }

            model_histograms = {}

            with rasterio.open(
                tif_path
            ) as src:

                # --------------------------------------------
                # Basic raster QA
                # --------------------------------------------

                if src.count < 4:
                    raise ValueError(
                        f"{tif_path.name} has "
                        f"{src.count} bands; "
                        "at least 4 are required."
                    )

                bounds = raster_bounds_wgs84(
                    src
                )

                epsg = (
                    src.crs.to_epsg()
                    if src.crs is not None
                    else None
                )

                expected_epsg = (
                    EXPECTED_SITE_EPSG.get(
                        site
                    )
                )

                if (
                    expected_epsg is not None
                    and epsg is not None
                    and epsg != expected_epsg
                ):
                    print(
                        f"  WARNING CRS: "
                        f"expected EPSG:{expected_epsg}, "
                        f"found EPSG:{epsg}"
                    )

                if reference_shape is None:

                    reference_shape = (
                        src.height,
                        src.width,
                    )

                    reference_transform = (
                        src.transform
                    )

                    reference_crs = (
                        src.crs
                    )

                    reference_bounds = (
                        bounds
                    )

                else:

                    if (
                        src.height,
                        src.width,
                    ) != reference_shape:
                        raise ValueError(
                            f"Grid shape mismatch in "
                            f"{flight_id}, model {model}."
                        )

                    if not src.transform.almost_equals(
                        reference_transform
                    ):
                        raise ValueError(
                            f"Grid transform mismatch in "
                            f"{flight_id}, model {model}."
                        )

                    if src.crs != reference_crs:
                        raise ValueError(
                            f"CRS mismatch in "
                            f"{flight_id}, model {model}."
                        )

                # --------------------------------------------
                # Variables
                # --------------------------------------------

                for variable, settings in VARIABLES.items():

                    band = settings[
                        "band"
                    ]

                    data = src.read(
                        band,
                        masked=True
                    ).astype(
                        np.float32
                    )

                    # Convert masked array -> NaN
                    data = np.ma.filled(
                        data,
                        np.nan
                    )

                    # Apply the same broad QA/QC logic used in validation.
                    (
                        data,
                        n_finite_before,
                        n_valid_after,
                        n_range_rejected,
                    ) = apply_qaqc(
                        data,
                        variable
                    )

                    valid_values = data[
                        np.isfinite(data)
                    ]

                    stats = calculate_stats(
                        valid_values
                    )

                    histogram = calculate_histogram(
                        valid_values
                    )

                    png_name = (
                        f"{flight_id}_"
                        f"{model}_"
                        f"{variable}.png"
                    )

                    png_path = (
                        RASTER_DIR
                        / png_name
                    )

                    save_transparent_png(
                        data=data,
                        output_path=png_path,
                        vmin=settings["vmin"],
                        vmax=settings["vmax"],
                        cmap_name=settings["cmap"],
                    )

                    model_metadata[
                        "variables"
                    ][variable] = {
                        "band": band,
                        "units": settings["units"],
                        "display_min": settings["vmin"],
                        "display_max": settings["vmax"],
                        "colormap": settings["cmap"],
                        "image": (
                            "data/rasters/"
                            + png_name
                        ),
                        "qa_qc": {
                            "screen_min": QA_RANGES[variable][0],
                            "screen_max": QA_RANGES[variable][1],
                            "finite_pixels_before": n_finite_before,
                            "valid_pixels_after": n_valid_after,
                            "range_rejected_pixels": n_range_rejected,
                        },
                        "stats": stats,
                    }

                    model_histograms[
                        variable
                    ] = histogram

            flight_metadata[
                "models"
            ][model] = model_metadata

            flight_histograms[
                "models"
            ][model] = model_histograms

        # --------------------------------------------
        # Shared flight metadata
        # --------------------------------------------

        flight_metadata[
            "bounds"
        ] = reference_bounds

        flight_metadata[
            "crs"
        ] = (
            reference_crs.to_string()
            if reference_crs is not None
            else None
        )

        flight_metadata[
            "shape"
        ] = [
            int(reference_shape[0]),
            int(reference_shape[1]),
        ]

        # --------------------------------------------
        # Save per-flight JSON
        # --------------------------------------------

        flight_folder = (
            FLIGHTS_DIR
            / flight_id
        )

        flight_folder.mkdir(
            parents=True,
            exist_ok=True
        )

        metadata_path = (
            flight_folder
            / "metadata.json"
        )

        histogram_path = (
            flight_folder
            / "histograms.json"
        )

        with metadata_path.open(
            "w",
            encoding="utf-8"
        ) as f:
            json.dump(
                flight_metadata,
                f,
                indent=2,
                allow_nan=False
            )

        with histogram_path.open(
            "w",
            encoding="utf-8"
        ) as f:
            json.dump(
                flight_histograms,
                f,
                indent=2,
                allow_nan=False
            )

        # --------------------------------------------
        # Add to global index
        # --------------------------------------------

        flight_entry = {
            "flight_id": flight_id,
            "site": site,
            "date": date,
            "time": time,
            "metadata": (
                "data/flights/"
                + flight_id
                + "/metadata.json"
            ),
            "histograms": (
                "data/flights/"
                + flight_id
                + "/histograms.json"
            ),
        }

        index[
            "flights"
        ].append(
            flight_entry
        )

        index[
            "sites"
        ].setdefault(
            site,
            {}
        )

        index[
            "sites"
        ][site].setdefault(
            date,
            []
        )

        index[
            "sites"
        ][site][date].append(
            {
                "time": time,
                "flight_id": flight_id,
            }
        )

        processed += 1

        print(
            "STATUS: OK"
        )

    except Exception as exc:

        failed += 1

        print(
            f"STATUS: ERROR -> {exc}"
        )


# ============================================================
# SORT INDEX
# ============================================================

index["flights"] = sorted(
    index["flights"],
    key=lambda x: (
        x["site"],
        x["date"],
        x["time"],
    )
)

for site in index["sites"]:

    index["sites"][site] = dict(
        sorted(
            index["sites"][
                site
            ].items()
        )
    )

    for date in index["sites"][site]:

        index["sites"][site][date] = sorted(
            index["sites"][site][date],
            key=lambda x: x["time"]
        )


# ============================================================
# SAVE GLOBAL INDEX
# ============================================================

DATA_DIR.mkdir(
    parents=True,
    exist_ok=True
)

with INDEX_JSON.open(
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        index,
        f,
        indent=2,
        allow_nan=False
    )


# ============================================================
# SUMMARY
# ============================================================

print(
    "\n===================================="
)

print(
    "LEAFLET DATA PREPARATION COMPLETE"
)

print(
    "===================================="
)

print(
    f"Flights processed: {processed}"
)

print(
    f"Flights failed: {failed}"
)

print(
    f"\nIndex saved:\n{INDEX_JSON}"
)

print(
    f"\nRaster PNG folder:\n{RASTER_DIR}"
)

print(
    f"\nFlight metadata folder:\n{FLIGHTS_DIR}"
)
