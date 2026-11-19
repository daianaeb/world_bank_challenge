from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from worldbankchallenge.utils.api_utils import (
    prompt_user_options,
    save_worldbank_csv,
)
from worldbankchallenge.utils.analytics_utils import create_missing_data_csv


if __name__ == "__main__":
    prompt_user_options()
    csv_path, created = save_worldbank_csv(PROJECT_ROOT / "raw_data")

    if created:
        print(f"Created CSV '{csv_path.name}'.")
        missing_csv_path = create_missing_data_csv(
            csv_path,
            output_directory=PROJECT_ROOT / "analytics_outputs" / "missing_data",
        )
        print(f"Created missing-data report '{missing_csv_path.name}'.")
    else:
        print(f"The existing CSV '{csv_path.name}' was not recreated.")