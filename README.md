# World Bank Challenge

This repo provides a local pipeline that retrieves yearly demographic indicators for a set of countries using the World Bank API, prepares it for analytics, and produces a small set of reporting outputs.

## Prerequisites

Before you begin, ensure you have installed `Python 3.14`.

  
## Using the pipeline

Install packages found in `requirements.txt`:
```
pip install -r requirements.txt
```

Main program execution:
```
python worldbankchallenge/scripts/main.py
```

## Pipeline logic and outcome

* Permanent configuration for contries, indicators and years is configured in `\worldbankchallenge\utils\config.py`.
* User can add temporary configuration at runtime (another country/indicator/year).
* Each runtime produces a source data CSV (together with API logs) and a set of analytics outputs: 
    * Missing data: a CSV with records that have `null` for `value` column in the source CSV. 
    * Indicators yearly evolution: A Line chart for each indicator, based on the source CSV, showing year over year evolution for each country.
    * Last year indicators values: A scatterplot for each indicator, based on the source CSV, showing how countries compare for the latest available year.
* The identifier of each pipeline execution is the execution timestamp that can be found in both the source and output corresponding to the same session.
* In case of timeout in API request or data missing for a particular combination, cells is CSV are filled with `null` and `N/A` is shown in plots. 
* Sample source and output data can be found in `\sample_data`. The countries + indicators + years combination was the following:
    * countries: `BRA, CAN`
    * indicators: `NY.GDP.MKTP.CD (GDP, current US dollars), NY.GDP.PCAP.CD (GDP per capita, current US dollars)`
    * years: `2023, 2024`
    * At runtime, I added the non-existent country `ABC`

## Notes
 
* I used GitHub Copilot to create this solution in the recommended time limit.
* I had no time left for the last Analytics task: "How do the indicators compare across income groups, by year?" - If income groups are receivable via API, I would have built a stacked bar chart for each indicator: 1 bar per year and inside the bar, stack the income groups.
* I had no time for building unit tests - e.g.: test the API connection, test the analytics generation on a  fixture dataset etc.

## Production design note
This section explains how the local pipeline could be productionized.

### Scheduling and incremental refreshes

* Implement a schedule for the pipeline execution using a tool like Airflow.
* Schedule can be daily/weekly/monthly depending on the used keys and desired granularity for the final reports.
* Avoid duplicate entries during refresh by generatig a unique hash for records based on multiple keys.

### Handling late, corrected, or changed source data

* In case of late data: Configure an on-demand refresh pipeline that can be used immediately when data is available (instead of waiting for the schedule).
* In case of data correction: Avoid direct data deletion and use an exclusions table to point out what records need to be excluded from full refreshes.
* In case of changed source data: Have a tests suite that validates the new source data against main constraints and features.

### Monitoring, alerting, and data-quality failures

* Export pipeline execution metrics: start/end time, duration, combinations requested, rows read, rows inserted/updated, null count, API status, retry count, and failure reason.
* Create monitors on HTTP/timeout failures, schema changes, unexpected counts and late data. Datadog can be used as a tool.

### Backfills and replay-ability

* Use the timestamp in source/output data so a rerun does not overwrite an earlier snapshot. 
* Use full refreshes to replace corrections and rebuild CSVs or charts.

### Snowflake + AWS usage

* AWS MWAA can be used to design the pipeline steps as DAG tasks and to schedule the pipeline execution. DAG tasks may be mainly Python operators that leverage the Python functions from this repo.
* Final CSV files can be exported into Snowflake fact/dim tables OR into S3.
* Visual analytics reports can be configured in Tableau.
