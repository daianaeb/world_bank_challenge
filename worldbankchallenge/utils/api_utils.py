from datetime import datetime
import json
from pathlib import Path

import pandas as pd
import requests

from worldbankchallenge.utils.config import COUNTRIES, INDICATORS, YEARS


countries = list(COUNTRIES)
indicator_codes = dict(INDICATORS)
years = list(YEARS)


def normalize_list_option(value=None, option_name="country", allowed_values=None):
    if option_name == "indicator":
        return ";".join(indicator_codes)
    return ";".join(countries)


def normalize_date_option(value=None):
    ordered_years = sorted(years, key=int)
    return f"{ordered_years[0]}:{ordered_years[-1]}"


def normalize_options(country_option=None, date_option=None, indicator_option=None):
    country_option = normalize_list_option(
        country_option, "country", set(countries)
    )
    indicator_option = normalize_list_option(
        indicator_option, "indicator", set(indicator_codes)
    )
    date_option = normalize_date_option(date_option)
    return country_option, date_option, indicator_option


def build_url(country_option=None, date_option=None, indicator_option=None):
    if country_option is None and date_option is None and indicator_option is None:
        country_option, date_option, indicator_option = normalize_options()
    else:
        if country_option is None:
            country_option, _, _ = normalize_options()
        if date_option is None:
            date_option = normalize_date_option()
        if indicator_option is None:
            _, _, indicator_option = normalize_options()
    return (
        "https://api.worldbank.org/v2/country/"
        f"{country_option}/indicator/{indicator_option}?format=json"
        f"&date={date_option}&per_page=1000"
    )


def write_api_log(log_path, event):
    if log_path is None:
        return
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(event, ensure_ascii=False) + "\n")


def fetch_population_data(country_option=None, date_option=None,
                          indicator_option=None, log_path=None,
                          run_timestamp=None):
    url = build_url(country_option, date_option, indicator_option)

    all_records = []
    page = 1

    while True:
        try:
            response = requests.get(url, params={"page": page}, timeout=30)
            response.raise_for_status()
            payload = response.json()
        except requests.exceptions.Timeout as error:
            write_api_log(log_path, {
                "event": "api_error",
                "type": "timeout",
                "url": url,
                "page": page,
                "country_code": country_option,
                "indicator_id": indicator_option,
                "run_timestamp": run_timestamp,
                "error": str(error),
            })
            break
        except requests.exceptions.HTTPError as error:
            write_api_log(log_path, {
                "event": "api_error",
                "type": "http",
                "status_code": response.status_code,
                "url": url,
                "page": page,
                "run_timestamp": run_timestamp,
            })
            raise RuntimeError(
                f"API returned HTTP {response.status_code}: {url}"
            ) from error
        except requests.exceptions.RequestException as error:
            write_api_log(log_path, {
                "event": "api_error",
                "type": "request",
                "url": url,
                "page": page,
                "run_timestamp": run_timestamp,
                "error": str(error),
            })
            raise RuntimeError(f"API request failed: {url}") from error
        except (ValueError, KeyError, TypeError) as error:
            write_api_log(log_path, {
                "event": "api_error",
                "type": "invalid_response",
                "url": url,
                "page": page,
                "run_timestamp": run_timestamp,
                "error": str(error),
            })
            raise RuntimeError("The World Bank API returned invalid data") from error

        if not isinstance(payload, list) or len(payload) < 2:
            raise RuntimeError("The World Bank API returned an unexpected response")

        metadata, records = payload
        write_api_log(log_path, {
            "event": "api_response",
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "run_timestamp": run_timestamp,
            "status_code": response.status_code,
            "url": response.url,
            "page": page,
            "country_code": country_option,
            "indicator_id": indicator_option,
            "record_count": len(records),
            "records": records,
        })
        all_records.extend(records)
        if page >= metadata["pages"]:
            break
        page += 1

    rows = []
    for record in all_records:
        rows.append({
            "country": record["country"]["value"],
            "country_code": record["countryiso3code"],
            "year": int(record["date"]),
            "indicator_id": record["indicator"]["id"],
            "indicator_name": record["indicator"]["value"],
            "value": record["value"],
        })

    return pd.DataFrame(rows)


def csv_name_for_options(country_option, date_option, indicator_option):
    country_option, date_option, indicator_option = normalize_options(
        country_option, date_option, indicator_option
    )
    country_name = country_option.replace(";", "_")
    date_name = date_option.replace(":", "_")
    indicator_name = indicator_option.replace(";", "_")
    return f"{country_name}__{date_name}__{indicator_name}.csv"


def fetch_worldbank_data(log_path=None, run_timestamp=None):
    date_option = normalize_date_option()
    frames = []

    for country_option in countries:
        for indicator_option in indicator_codes:
            try:
                frame = fetch_population_data(
                    country_option,
                    date_option,
                    indicator_option,
                    log_path=log_path,
                    run_timestamp=run_timestamp,
                )
                if not frame.empty:
                    frames.append(frame)
            except RuntimeError as error:
                print(f"Using null values for {country_option}/{indicator_option}: {error}")
                write_api_log(log_path, {
                    "event": "combination_unavailable",
                    "country_code": country_option,
                    "indicator_id": indicator_option,
                    "run_timestamp": run_timestamp,
                    "error": str(error),
                })

    fetched = (
        pd.concat(frames, ignore_index=True)
        if frames
        else pd.DataFrame(columns=[
            "country", "country_code", "year",
            "indicator_id", "indicator_name", "value",
        ])
    )
    fetched = fetched.drop_duplicates(
        ["country_code", "indicator_id", "year"], keep="last"
    )
    records_by_key = {
        (row["country_code"], row["indicator_id"], str(row["year"])): row
        for row in fetched.to_dict("records")
    }

    complete_rows = []
    for country_code in countries:
        for indicator_id, configured_name in indicator_codes.items():
            matching_rows = [
                row for (record_country, record_indicator, _), row
                in records_by_key.items()
                if record_country == country_code and record_indicator == indicator_id
            ]
            country_name = next(
                (row["country"] for row in matching_rows if row["country"]),
                country_code,
            )
            indicator_name = next(
                (row["indicator_name"] for row in matching_rows
                 if row["indicator_name"]),
                configured_name,
            )

            for year in years:
                record = records_by_key.get(
                    (country_code, indicator_id, str(year))
                )
                complete_rows.append({
                    "country": record["country"] if record else country_name,
                    "country_code": country_code,
                    "year": int(year),
                    "indicator_id": indicator_id,
                    "indicator_name": (
                        record["indicator_name"] if record
                        else indicator_name
                    ),
                    "value": record["value"] if record else None,
                })

    return pd.DataFrame(complete_rows).sort_values(
        ["country_code", "indicator_id", "year"]
    )


def save_worldbank_csv(csv_directory="raw_data"):
    output_directory = Path(csv_directory)
    output_directory.mkdir(parents=True, exist_ok=True)

    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    output_path = output_directory / f"worldbank_{run_timestamp}.csv"
    log_path = output_directory / "logs" / f"api_log_{run_timestamp}.log"

    try:
        data = fetch_worldbank_data(
            log_path=log_path,
            run_timestamp=run_timestamp,
        )
    except RuntimeError as error:
        write_api_log(log_path, {
            "event": "fatal_error",
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "run_timestamp": run_timestamp,
            "error": str(error),
        })
        print(f"Could not create CSV: {error}")
        return output_path, False

    data.to_csv(output_path, index=False)
    write_api_log(log_path, {
        "event": "csv_created",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "run_timestamp": run_timestamp,
        "csv_path": str(output_path),
        "row_count": len(data),
    })
    print(f"Saved {len(data)} rows to {output_path}")
    print(f"API trace log: {log_path}")
    return output_path, True


def save_query_csv(df, country_option, date_option, indicator_option,
                   csv_directory="."):
    normalized = normalize_options(country_option, date_option, indicator_option)
    csv_name = csv_name_for_options(*normalized)
    output_path = Path(csv_directory) / csv_name

    if output_path.exists():
        return output_path, False

    df.to_csv(output_path, index=False)
    return output_path, True




def prompt_for_additions():
    """Prompt for optional additions that apply only during this run."""
    print("World Bank Data Query")
    print("Existing countries:", ", ".join(sorted(countries)))
    print("Existing years:", ", ".join(sorted(years, key=int)))
    print("Existing indicators:")
    for code, name in sorted(indicator_codes.items()):
        print(f"  {code}: {name}")

    while input("Add a country? (y/N): ").strip().lower() == "y":
        code = input("Enter the 3-letter country code: ").strip().upper()
        if len(code) != 3 or not code.isalpha():
            print("Invalid country code. Use exactly 3 letters.")
            continue
        if code in countries:
            print(f"{code} is already in the country list.")
            continue
        countries.append(code)
        print(f"Added country {code}.")

    while input("Add a year? (y/N): ").strip().lower() == "y":
        year = input("Enter a year (for example 2025): ").strip()
        if len(year) != 4 or not year.isdigit():
            print("Invalid year. Use four digits.")
            continue
        if year in years:
            print(f"{year} is already in the year list.")
            continue
        years.append(year)
        print(f"Added year {year}.")

    while input("Add an indicator? (y/N): ").strip().lower() == "y":
        code = input("Enter the indicator code: ").strip().upper()
        name = input("Enter the indicator name: ").strip()
        if not code or not name:
            print("Both indicator code and name are required.")
            continue
        if code in indicator_codes:
            print(f"{code} is already in the indicator list.")
            continue
        indicator_codes[code] = name
        print(f"Added indicator {code}: {name}")

def prompt_user_options():
    prompt_for_additions()
    print("Countries:", ", ".join(countries))
    print("Indicators:", ", ".join(indicator_codes))
    print("Years:", normalize_date_option())
    return normalize_options()
