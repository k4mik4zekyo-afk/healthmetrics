# Health Metrics

Garmin health data export and interactive dashboard. Pulls activity, sleep, stress, and nap data from your Garmin Connect account and visualizes it in a Streamlit web app.

## Prerequisites

- Python 3.10+
- A Garmin Connect account with a paired device

## Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/k4mik4zekyo-afk/healthmetrics.git
   cd healthmetrics
   ```

2. Install dependencies:
   ```bash
   pip install streamlit pandas pytz python-dotenv garminconnect python-dateutil statsmodels
   ```

3. Create a `.env` file in the project root with your Garmin credentials:
   ```
   GARMIN_EMAIL=your_email@example.com
   GARMIN_PASSWORD=your_password
   ```

## Usage

### Fetch data from Garmin

```bash
python "body battery.py"
```

This connects to the Garmin API and exports CSV files to `garmin_exports/`. Edit `START_DATE` and `END_DATE` at the top of the script to change the date range.

### Launch the dashboard

```bash
streamlit run dashboard.py
```

A browser tab opens with the interactive dashboard. You can also click **Refresh Data** in the sidebar to re-fetch from Garmin without leaving the dashboard.

## Dashboard

### Activities tab
- **KPI row** — total activity time, activity count, average duration
- **Stacked bar chart** — activity hours per week or month, broken down by type (running, walking, cycling, etc.)
- **Descriptive stats table** — count, total hours, mean, median, min, max, and standard deviation per period

Use the **Activity types** multiselect in the sidebar to filter which activities appear.

### Sleep & Rest tab
- **KPI row** — average nightly sleep, average nap duration, average total rest
- **Stacked bar chart** — sleep and nap hours per week or month
- **Sleep stats table** — per-period descriptive statistics for nightly sleep
- **Nap stats table** — per-period descriptive statistics for naps (rest events, 20-120 min)

Toggle between **Weekly** and **Monthly** aggregation using the sidebar radio button.

### Sleep Model tab

Uses daytime stress patterns, activity, and optional caffeine intake to predict sleep outcomes via three models:

- **Linear regression** → Garmin sleep score (0-100)
- **Linear regression** → sleep duration (hours)
- **Logistic regression** → slept more than 7 hours (yes/no)

Click **Build Model** in the tab to generate the feature table and train the models. The tab shows feature data, model coefficients, R²/accuracy metrics, and a bar chart of coefficient magnitudes.

## Sleep Model

### How it works

The script `sleep_model.py` builds a daily feature table from your Garmin data:

**Stress features (waking hours only, 5 categories matching Garmin UI):**
- `rest_hrs` — stress 1-25
- `low_stress_hrs` — stress 26-50
- `med_stress_hrs` — stress 51-75
- `high_stress_hrs` — stress 76-100 (not during a recorded activity)
- `in_activity_hrs` — any stress reading during a Garmin activity window

**Activity feature:**
- `had_activity` — 1 if any Garmin activity was recorded that day, 0 otherwise

**Caffeine features (optional):**
- `caffeine_mg` — total estimated caffeine (mg) for the day
- `last_caffeine_hrs_before_sleep` — hours between last caffeinated drink and sleep start

Features from day D predict the sleep that starts that evening (assigned to day D+1 in Garmin's date system).

### Running the model

```bash
python sleep_model.py
```

Or click **Build Model** in the dashboard's Sleep Model tab.

### Caffeine data (optional)

Export your caffeine tracking sheet as a CSV and place it at `garmin_exports/caffeine.csv`. Expected columns:

| Column | Example | Used for |
|--------|---------|----------|
| `Date` | `2026-01-15` | Join key |
| `Drink` | `Coffee` | Not used in model |
| `Amount` | `16 oz` | Not used in model |
| `estimated mg` | `200` | Total daily caffeine |
| `last drink time` | `14:30` | Hours before sleep |
| `Comment` | `afternoon pick-me-up` | Not used in model |

If the file is absent, the model runs without caffeine features.

## Data Files

All exported to `garmin_exports/`:

| File | Description |
|------|-------------|
| `activities.csv` | Garmin activities (type, duration, distance, heart rate, calories) |
| `sleep_events.csv` | Nightly sleep events (start, end, duration) |
| `nap_events.csv` | Detected nap/rest events from stress data (20-120 min low-stress periods) |
| `daily_rest_summary.csv` | Aggregated daily sleep + nap totals |
| `stress_timeseries.csv` | Raw 3-minute stress readings used for nap detection |
| `caffeine.csv` | Optional caffeine intake log (exported from Google Sheets) |
| `model_features.csv` | Generated daily feature table for sleep model |
| `model_results.json` | Trained model coefficients and metrics |

## Configuration

Edit the constants at the top of `body battery.py`:

| Variable | Default | Description |
|----------|---------|-------------|
| `START_DATE` | `2026-01-01` | First date to fetch |
| `END_DATE` | `2026-01-22` | Last date to fetch |
| `TIMEZONE` | `America/Los_Angeles` | Local timezone for timestamp conversion |
| `NAP_MIN_MINUTES` | `20` | Minimum duration to classify a rest period as a nap |
| `NAP_MAX_MINUTES` | `120` | Maximum duration for nap classification |
| `SLEEP_MIN_MINUTES` | `180` | Minimum duration to count as sleep |
| `STRESS_REST_THRESHOLD` | `15` | Stress level below which the user is considered resting |

## Project Structure

```
healthmetrics/
├── body battery.py          # Data pipeline — fetches from Garmin API, exports CSVs
├── dashboard.py             # Streamlit interactive dashboard
├── sleep_model.py           # Feature engineering + model training for sleep prediction
├── plot_daily_rest_barchart.py  # Standalone matplotlib bar chart
├── streamlit_tutorial.md    # Streamlit beginner tutorial
├── streamlit_demo.py        # Runnable Streamlit demo (no credentials needed)
├── .env                     # Garmin credentials (not committed)
├── .gitignore
└── garmin_exports/          # Generated data files
    ├── activities.csv
    ├── sleep_events.csv
    ├── nap_events.csv
    ├── daily_rest_summary.csv
    ├── stress_timeseries.csv
    ├── caffeine.csv         # Optional — user-provided
    ├── model_features.csv   # Generated by sleep_model.py
    ├── model_results.json   # Generated by sleep_model.py
    └── daily_rest_barchart.png
```

## Learning Streamlit

New to Streamlit? This repo includes learning materials:

- **`streamlit_tutorial.md`** — Written guide covering every concept from scratch
- **`streamlit_demo.py`** — Runnable demo app (`streamlit run streamlit_demo.py`) that shows each feature in action with inline explanations
