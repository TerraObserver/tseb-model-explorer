from pathlib import Path
import re
import pandas as pd


# ============================================================
# SETTINGS
# ============================================================

PROJECT_DIR = Path(
    r"C:\Users\mdura\OneDrive\Desktop\PHD_PAPER1_PROCESSING_v2"
)

TSEB_OUTPUT_DIR = (
    PROJECT_DIR
    / "2_tseb_loop"
    / "outputs"
)

SCRIPT_DIR = Path(__file__).resolve().parent

OUTPUT_CSV = (
    SCRIPT_DIR
    / "tseb_manifest.csv"
)

MODELS = ["PT", "PM", "SW"]


# ============================================================
# FILENAME PARSER
# ============================================================

def parse_tseb_filename(path):
    """
    Expected primary TSEB filenames:

        OLA_20210729_1500_PT.tif
        VAC_20230710_1230_PM.tif
        WWF_20220714_1500_SW.tif

    Ancillary files are ignored automatically because they
    do not match this pattern.
    """

    pattern = re.compile(
        r"^(OLA|VAC|WWF)_"
        r"(\d{8})_"
        r"(\d{4})_"
        r"(PT|PM|SW)\.tif$",
        re.IGNORECASE
    )

    match = pattern.match(path.name)

    if match is None:
        return None

    site, date, time, model = match.groups()

    return {
        "site": site.upper(),
        "date": date,
        "time": time,
        "model": model.upper(),
    }


# ============================================================
# READ TSEB FILES
# ============================================================

records = []

for model in MODELS:

    model_folder = (
        TSEB_OUTPUT_DIR
        / model
    )

    if not model_folder.exists():
        raise FileNotFoundError(
            f"Model folder not found:\n{model_folder}"
        )

    tif_files = sorted(
        model_folder.glob("*.tif")
    )

    primary_count = 0

    for tif_path in tif_files:

        info = parse_tseb_filename(
            tif_path
        )

        if info is None:
            continue

        primary_count += 1

        records.append({
            "site": info["site"],
            "date": info["date"],
            "time": info["time"],
            "model": info["model"],
            "path": str(
                tif_path.resolve()
            ),
        })

    print(
        f"{model}: {primary_count} primary TSEB files"
    )


# ============================================================
# DATAFRAME
# ============================================================

long_df = pd.DataFrame(records)

if long_df.empty:
    raise RuntimeError(
        "No primary TSEB TIFF files were found."
    )


# ============================================================
# DUPLICATE CHECK
# ============================================================

duplicate_mask = long_df.duplicated(
    subset=[
        "site",
        "date",
        "time",
        "model",
    ],
    keep=False,
)

if duplicate_mask.any():

    print(
        "\nWARNING: duplicate TSEB files detected:"
    )

    print(
        long_df.loc[
            duplicate_mask
        ].sort_values(
            [
                "site",
                "date",
                "time",
                "model",
            ]
        ).to_string(index=False)
    )

    raise RuntimeError(
        "Duplicate site/date/time/model combinations found. "
        "Resolve them before building the manifest."
    )


# ============================================================
# CONVERT TO ONE ROW PER FLIGHT
# ============================================================

manifest = (
    long_df
    .pivot(
        index=[
            "site",
            "date",
            "time",
        ],
        columns="model",
        values="path",
    )
    .reset_index()
)

manifest.columns.name = None

manifest = manifest.rename(
    columns={
        "PT": "pt_path",
        "PM": "pm_path",
        "SW": "sw_path",
    }
)


# Ensure all expected columns exist
for column in [
    "pt_path",
    "pm_path",
    "sw_path",
]:
    if column not in manifest.columns:
        manifest[column] = pd.NA


# ============================================================
# COMPLETE TRIPLET CHECK
# ============================================================

model_columns = [
    "pt_path",
    "pm_path",
    "sw_path",
]

manifest["complete_triplet"] = (
    manifest[model_columns]
    .notna()
    .all(axis=1)
)

incomplete = manifest[
    ~manifest["complete_triplet"]
].copy()

if not incomplete.empty:

    print(
        "\nWARNING: incomplete PT/PM/SW flights:"
    )

    for _, row in incomplete.iterrows():

        missing = [
            model.upper()
            for model in ["pt", "pm", "sw"]
            if pd.isna(
                row[f"{model}_path"]
            )
        ]

        print(
            f"{row['site']} "
            f"{row['date']} "
            f"{row['time']} "
            f"-> missing: {', '.join(missing)}"
        )


# ============================================================
# KEEP ONLY COMPLETE FLIGHTS
# ============================================================

manifest_complete = (
    manifest[
        manifest["complete_triplet"]
    ]
    .copy()
)

manifest_complete = (
    manifest_complete
    .sort_values(
        [
            "site",
            "date",
            "time",
        ]
    )
    .reset_index(drop=True)
)


# ============================================================
# FLIGHT ID
# ============================================================

manifest_complete.insert(
    0,
    "flight_id",
    (
        manifest_complete["site"]
        + "_"
        + manifest_complete["date"]
        + "_"
        + manifest_complete["time"]
    )
)


# ============================================================
# SAVE
# ============================================================

manifest_complete.to_csv(
    OUTPUT_CSV,
    index=False
)


# ============================================================
# SUMMARY
# ============================================================

print(
    "\n===================================="
)

print(
    "TSEB MANIFEST COMPLETE"
)

print(
    "===================================="
)

print(
    f"Complete flights: {len(manifest_complete)}"
)

print(
    f"Incomplete flights excluded: {len(incomplete)}"
)

print(
    "\nFlights by site:"
)

print(
    manifest_complete["site"]
    .value_counts()
    .sort_index()
)

print(
    f"\nSaved:\n{OUTPUT_CSV}"
)
