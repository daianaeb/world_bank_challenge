import re
from pathlib import Path

import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


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
        else PROJECT_ROOT / "analytics_outputs" / "missing_data"
    )
    directory.mkdir(parents=True, exist_ok=True)
    output_path = directory / f"missing_data_{match.group(1)}.csv"
    missing_rows.to_csv(output_path, index=False)
    print(f"Saved {len(missing_rows)} null-valued rows to {output_path}")
    return output_path


def create_indicator_linecharts(source_csv, output_directory=None):
    """Create one year-over-year line chart per indicator."""
    source_path = Path(source_csv)
    match = re.fullmatch(r"worldbank_(\d{8}_\d{6}_\d+)\.csv", source_path.name)
    if match is None:
        raise ValueError("Source CSV must be named worldbank_<timestamp>.csv")

    data = pd.read_csv(source_path)
    required_columns = [
        "country",
        "country_code",
        "year",
        "indicator_id",
        "indicator_name",
        "value",
    ]
    missing_columns = set(required_columns).difference(data.columns)
    if missing_columns:
        raise ValueError(
            "Source CSV is missing required columns: "
            + ", ".join(sorted(missing_columns))
        )

    directory = (
        Path(output_directory)
        if output_directory is not None
        else PROJECT_ROOT / "analytics_outputs" / "indicators_yearly_evolution"
    )
    timestamp = match.group(1)
    directory = directory / timestamp
    directory.mkdir(parents=True, exist_ok=True)
    chart_paths = []

    for indicator_id in sorted(data["indicator_id"].dropna().unique()):
        indicator_rows = data.loc[data["indicator_id"] == indicator_id].copy()
        indicator_name = indicator_rows["indicator_name"].dropna().iloc[0]

        fig, ax = plt.subplots(figsize=(12, 7))

        for country_code in sorted(indicator_rows["country_code"].dropna().unique()):
            country_rows = indicator_rows.loc[
                indicator_rows["country_code"] == country_code
            ].sort_values("year")
            country_name = country_rows["country"].dropna().iloc[0]

            years = pd.to_numeric(country_rows["year"], errors="coerce")
            values = pd.to_numeric(country_rows["value"], errors="coerce")
            ax.plot(
                years,
                values,
                marker="o",
                linewidth=1.5,
                label=country_name,
            )

        ax.set_title(f"{indicator_name} - Yearly Evolution")
        ax.set_xlabel("Year")
        ax.set_ylabel(indicator_name)
        ax.grid(True, linestyle="--", alpha=0.35)
        ax.legend(title="Country", bbox_to_anchor=(1.02, 1), loc="upper left")
        fig.tight_layout()

        chart_path = directory / f"{indicator_id}.png"
        fig.savefig(chart_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        chart_paths.append(chart_path)
        print(f"Saved line chart to {chart_path}")

    return chart_paths