from pathlib import Path
import json
import math
import pandas as pd
import numpy as np

# ============================================================
# PATHS
# ============================================================

PROJECT_DIR = Path(
    r"C:\Users\mdura\OneDrive\Desktop\PHD_PAPER1_PROCESSING_v2"
)

SOURCE_XLSX = (
    PROJECT_DIR
    / "3_footprint_validation"
    / "validation"
    / "TSEB_EC_hourly_validation.xlsx"
)

OUTPUT_JSON = (
    PROJECT_DIR
    / "5_leaflet"
    / "web"
    / "data"
    / "closure_data_components.json"
)

SHEET_NAME = "Validation"

MODELS = ["PT", "PM", "SW"]
COMPONENTS = ["Rn", "H", "LE", "G"]


# ============================================================
# HELPERS
# ============================================================

def safe_float(value):
    if pd.isna(value):
        return None

    value = float(value)

    if not math.isfinite(value):
        return None

    return value


def fmt_date(value):
    return str(int(value)).zfill(8)


def fmt_time(value):
    return str(int(value)).zfill(4)


# ============================================================
# READ CURRENT VALIDATION TABLE
# ============================================================

if not SOURCE_XLSX.exists():
    raise FileNotFoundError(
        f"Validation workbook not found:\n{SOURCE_XLSX}"
    )

df = pd.read_excel(
    SOURCE_XLSX,
    sheet_name=SHEET_NAME
)

required = {
    "SITE",
    "DATE",
    "TIME",
    "MODEL",
    "STATUS",
    "MATCH_STATUS",
    "TSEB_FILE",
    "TSEB_Rn",
    "TSEB_H",
    "TSEB_LE",
    "TSEB_G",
    "EC_Rn",
    "EC_H",
    "EC_LE",
    "EC_G",
    "EC_EBR",
    "EC_RESIDUAL",
}

missing = required - set(df.columns)

if missing:
    raise ValueError(
        "Missing required columns: "
        + ", ".join(sorted(missing))
    )


# ============================================================
# STRICT AUDIT
# ============================================================

if len(df) != 126:
    raise ValueError(
        f"Expected 126 validation rows, found {len(df)}."
    )

model_counts = df["MODEL"].value_counts().to_dict()

for model in MODELS:
    if model_counts.get(model, 0) != 42:
        raise ValueError(
            f"Expected 42 rows for {model}, "
            f"found {model_counts.get(model, 0)}."
        )

if not (df["STATUS"] == "OK").all():
    bad = df.loc[df["STATUS"] != "OK"]
    raise ValueError(
        f"{len(bad)} rows have STATUS != OK."
    )

if not (df["MATCH_STATUS"] == "MATCHED").all():
    bad = df.loc[df["MATCH_STATUS"] != "MATCHED"]
    raise ValueError(
        f"{len(bad)} rows have MATCH_STATUS != MATCHED."
    )

duplicates = df.duplicated(
    ["SITE", "DATE", "TIME", "MODEL"]
)

if duplicates.any():
    raise ValueError(
        f"Found {int(duplicates.sum())} duplicated "
        "SITE/DATE/TIME/MODEL rows."
    )

core_columns = [
    "TSEB_Rn", "TSEB_H", "TSEB_LE", "TSEB_G",
    "EC_Rn", "EC_H", "EC_LE", "EC_G",
]

if df[core_columns].isna().any().any():
    raise ValueError(
        "NaN values found in required TSEB/EC flux columns."
    )

# Verify TSEB_FILE agrees with SITE + DATE + TIME + MODEL
for _, row in df.iterrows():

    site = str(row["SITE"]).upper()
    date = fmt_date(row["DATE"])
    time = fmt_time(row["TIME"])
    model = str(row["MODEL"]).upper()

    expected_file = (
        f"{site}_{date}_{time}_{model}.tif"
    )

    actual_file = str(row["TSEB_FILE"])

    if actual_file != expected_file:
        raise ValueError(
            "Timestamp/model mismatch:\n"
            f"expected: {expected_file}\n"
            f"found:    {actual_file}"
        )


# ============================================================
# BUILD JSON DIRECTLY FROM CURRENT TABLE
# ============================================================

points = []

for _, row in df.iterrows():

    site = str(row["SITE"]).upper()
    date = fmt_date(row["DATE"])
    time = fmt_time(row["TIME"])
    model = str(row["MODEL"]).upper()

    ec_rn = float(row["EC_Rn"])
    ec_h = float(row["EC_H"])
    ec_le = float(row["EC_LE"])
    ec_g = float(row["EC_G"])

    available_energy = ec_rn - ec_g
    turbulent_flux = ec_h + ec_le

    if (
        not np.isfinite(available_energy)
        or not np.isfinite(turbulent_flux)
        or turbulent_flux == 0
    ):
        raise ValueError(
            f"Cannot closure-correct tower data for "
            f"{site} {date} {time} {model}."
        )

    # Bowen-ratio-preserving energy-balance closure correction
    ec_h_corr = (
        available_energy
        * ec_h
        / turbulent_flux
    )

    ec_le_corr = (
        available_energy
        * ec_le
        / turbulent_flux
    )

    corrected = {
        "Rn": ec_rn,
        "H": ec_h_corr,
        "LE": ec_le_corr,
        "G": ec_g,
    }

    raw_ec = {
        "Rn": ec_rn,
        "H": ec_h,
        "LE": ec_le,
        "G": ec_g,
    }

    modeled = {
        "Rn": float(row["TSEB_Rn"]),
        "H": float(row["TSEB_H"]),
        "LE": float(row["TSEB_LE"]),
        "G": float(row["TSEB_G"]),
    }

    ebr = safe_float(row["EC_EBR"])

    closure_fraction = (
        None
        if ebr is None
        else 1.0 - ebr
    )

    for component in COMPONENTS:

        points.append(
            {
                "site": site,
                "date": date,
                "time": time,
                "model": model,
                "component": component,

                "modeled": safe_float(
                    modeled[component]
                ),

                "tower_corrected": safe_float(
                    corrected[component]
                ),

                "tower_raw": safe_float(
                    raw_ec[component]
                ),

                "EBR": ebr,

                # dimensionless closure deficit = 1 - EBR
                "closure_error": safe_float(
                    closure_fraction
                ),

                # raw energy residual from source workbook, W m-2
                "closure_residual_wm2": safe_float(
                    row["EC_RESIDUAL"]
                ),

                "source_tseb_file": str(
                    row["TSEB_FILE"]
                ),
            }
        )


# ============================================================
# FINAL QA
# ============================================================

expected_points = (
    42
    * len(MODELS)
    * len(COMPONENTS)
)

if len(points) != expected_points:
    raise ValueError(
        f"Expected {expected_points} component points, "
        f"generated {len(points)}."
    )

payload = {
    "version": 2,

    "provenance": {
        "source_workbook":
            str(SOURCE_XLSX),

        "sheet":
            SHEET_NAME,

        "source_rows":
            int(len(df)),

        "unique_flights":
            int(
                df[
                    ["SITE", "DATE", "TIME"]
                ]
                .drop_duplicates()
                .shape[0]
            ),

        "models":
            MODELS,

        "components":
            COMPONENTS,

        "tower_closure_method":
            "Bowen-ratio-preserving correction: "
            "Hcorr=(Rn-G)*H/(H+LE); "
            "LEcorr=(Rn-G)*LE/(H+LE); "
            "Rn and G unchanged"
    },

    "points": points
}

OUTPUT_JSON.parent.mkdir(
    parents=True,
    exist_ok=True
)

with OUTPUT_JSON.open(
    "w",
    encoding="utf-8"
) as f:
    json.dump(
        payload,
        f,
        indent=2,
        allow_nan=False
    )


# ============================================================
# CONSOLE SUMMARY
# ============================================================

flight_table = (
    df[
        ["SITE", "DATE", "TIME"]
    ]
    .drop_duplicates()
    .copy()
)

flight_table["DATE"] = (
    flight_table["DATE"]
    .map(fmt_date)
)

flight_table["TIME"] = (
    flight_table["TIME"]
    .map(fmt_time)
)

print(
    "===================================="
)

print(
    "VALIDATION -> LEAFLET COMPLETE"
)

print(
    "===================================="
)

print(
    f"Source rows: {len(df)}"
)

print(
    f"Unique flights: {len(flight_table)}"
)

print(
    f"PT rows: {model_counts.get('PT', 0)}"
)

print(
    f"PM rows: {model_counts.get('PM', 0)}"
)

print(
    f"SW rows: {model_counts.get('SW', 0)}"
)

print(
    f"JSON points: {len(points)}"
)

print(
    "\nTimes present:"
)

print(
    sorted(
        flight_table["TIME"].unique().tolist()
    )
)

print(
    f"\nSaved:\n{OUTPUT_JSON}"
)
