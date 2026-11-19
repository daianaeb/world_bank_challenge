import re
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MISSING_DATA_COLUMNS = [
    "country",
    "country_code",
    "year",
    "indicator_id",
    "indicator_name",
]


def create_missing_data_csv(source_csv, output_directory=None):
    """Extract null-valued rows and name the report with the source run timestamp."""
    source_path = Path(source_csv)
    match = re.fullmatch(r"worldbank_(\d{8}_\d{6}_\d+)\.csv", source_path.name)
    if match is None:
        raise ValueError(
            "Source CSV must be named worldbank_<timestamp>.csv"
        )

    data = pd.read_csv(source_path)
    required_columns = MISSING_DATA_COLUMNS + ["value"]
    missing_columns = set(required_columns).difference(data.columns)
    if missing_columns:
        raise ValueError(
            "Source CSV is missing required columns: "
            + ", ".join(sorted(missing_columns))
        )

    missing_rows = data.loc[data["value"].isna(), MISSING_DATA_COLUMNS]
    directory = (
        Path(output_directory)
        if output_directory is not None
        else PROJECT_ROOT / "analytics_outputs"
    )
    directory.mkdir(parents=True, exist_ok=True)
    output_path = directory / f"missing_data_{match.group(1)}.csv"
    missing_rows.to_csv(output_path, index=False)
    print(f"Saved {len(missing_rows)} null-valued rows to {output_path}")
    return output_path