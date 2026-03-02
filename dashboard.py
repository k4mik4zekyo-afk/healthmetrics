import json
import os
import subprocess
import pandas as pd
import numpy as np
import streamlit as st

DATA_DIR = os.path.join(os.path.dirname(__file__), "garmin_exports")

st.set_page_config(page_title="Health Metrics", layout="wide")

# ── helpers ──────────────────────────────────────────────────────────────────


def _period_col(df, date_col, period):
    """Add a 'period' column based on a date column."""
    dates = pd.to_datetime(df[date_col])
    if period == "Weekly":
        df = df.copy()
        df["period"] = dates.dt.isocalendar().year.astype(str) + "-W" + dates.dt.isocalendar().week.astype(str).str.zfill(2)
    else:
        df = df.copy()
        df["period"] = dates.dt.to_period("M").astype(str)
    return df


def _desc_stats(series):
    """Return a dict of descriptive stats for a numeric series (in minutes)."""
    if series.empty:
        return {
            "count": 0, "total_hrs": 0, "mean_min": 0, "median_min": 0,
            "min_min": 0, "max_min": 0, "std_min": 0,
        }
    return {
        "count": int(series.count()),
        "total_hrs": round(series.sum() / 60, 2),
        "mean_min": round(series.mean(), 1),
        "median_min": round(series.median(), 1),
        "min_min": round(series.min(), 1),
        "max_min": round(series.max(), 1),
        "std_min": round(series.std(), 1) if len(series) > 1 else 0.0,
    }


# ── data loading ─────────────────────────────────────────────────────────────


@st.cache_data
def load_activities():
    path = os.path.join(DATA_DIR, "activities.csv")
    if not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_csv(path)
    if "date_assigned" in df.columns:
        df["date_assigned"] = pd.to_datetime(df["date_assigned"])
    return df


@st.cache_data
def load_sleep():
    path = os.path.join(DATA_DIR, "sleep_events.csv")
    if not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_csv(path)
    if "date_assigned" in df.columns:
        df["date_assigned"] = pd.to_datetime(df["date_assigned"])
    return df


@st.cache_data
def load_naps():
    path = os.path.join(DATA_DIR, "nap_events.csv")
    if not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_csv(path)
    if "date_assigned" in df.columns:
        df["date_assigned"] = pd.to_datetime(df["date_assigned"])
    return df


# ── sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("Controls")

    if st.button("Refresh Data"):
        with st.spinner("Fetching data from Garmin..."):
            result = subprocess.run(
                ["python", os.path.join(os.path.dirname(__file__), "body battery.py")],
                capture_output=True, text=True, cwd=os.path.dirname(__file__),
            )
        if result.returncode == 0:
            st.success("Data refreshed!")
            st.cache_data.clear()
        else:
            st.error("Refresh failed. Check credentials / connectivity.")
            st.code(result.stderr[-2000:] if result.stderr else result.stdout[-2000:])

    st.divider()
    period = st.radio("Aggregate by", ["Weekly", "Monthly"])

# ── load data ────────────────────────────────────────────────────────────────

activities = load_activities()
sleep = load_sleep()
naps = load_naps()

# ── activity type filter (sidebar, after data is loaded) ─────────────────────

with st.sidebar:
    if not activities.empty and "activity_type" in activities.columns:
        all_types = sorted(activities["activity_type"].dropna().unique().tolist())
        selected_types = st.multiselect(
            "Activity types",
            options=all_types,
            default=all_types,
        )
    else:
        selected_types = []

# ── tabs ─────────────────────────────────────────────────────────────────────

tab_act, tab_sleep, tab_model = st.tabs(["Activities", "Sleep & Rest", "Sleep Model"])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 – ACTIVITIES
# ═══════════════════════════════════════════════════════════════════════════════

with tab_act:
    st.header("Activity Report")

    if activities.empty or "activity_type" not in activities.columns:
        st.info("No activity data found. Click **Refresh Data** to fetch from Garmin.")
    else:
        filtered = activities[activities["activity_type"].isin(selected_types)].copy()

        if filtered.empty:
            st.warning("No activities match the selected types.")
        else:
            # KPIs
            total_hrs = filtered["duration_minutes"].sum() / 60
            total_count = len(filtered)
            avg_dur = filtered["duration_minutes"].mean()

            c1, c2, c3 = st.columns(3)
            c1.metric("Total Activity Time", f"{total_hrs:.1f} hrs")
            c2.metric("Total Activities", total_count)
            c3.metric("Avg Duration", f"{avg_dur:.0f} min")

            # Bar chart – total hours per period, stacked by activity type
            st.subheader(f"Activity Time by {period.rstrip('ly')} & Type")
            chart_df = _period_col(filtered, "date_assigned", period)
            pivot = (
                chart_df
                .groupby(["period", "activity_type"])["duration_minutes"]
                .sum()
                .div(60)
                .reset_index()
                .pivot(index="period", columns="activity_type", values="duration_minutes")
                .fillna(0)
                .sort_index()
            )
            st.bar_chart(pivot)

            # Descriptive stats table per period
            st.subheader(f"Descriptive Stats by {period.rstrip('ly')}")
            stats_rows = []
            for p, grp in chart_df.groupby("period"):
                s = _desc_stats(grp["duration_minutes"])
                s["period"] = p
                stats_rows.append(s)
            stats_df = pd.DataFrame(stats_rows)[
                ["period", "count", "total_hrs", "mean_min", "median_min",
                 "min_min", "max_min", "std_min"]
            ]
            st.dataframe(stats_df, use_container_width=True, hide_index=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 – SLEEP & REST
# ═══════════════════════════════════════════════════════════════════════════════

with tab_sleep:
    st.header("Sleep & Rest Report")

    has_sleep = not sleep.empty and "duration_minutes" in sleep.columns
    has_naps = not naps.empty and "duration_minutes" in naps.columns

    if not has_sleep and not has_naps:
        st.info("No sleep/nap data found. Click **Refresh Data** to fetch from Garmin.")
    else:
        # KPIs
        avg_sleep = sleep["duration_minutes"].mean() / 60 if has_sleep else 0
        avg_nap = naps["duration_minutes"].mean() if has_naps else 0
        avg_rest = avg_sleep + (avg_nap / 60)

        c1, c2, c3 = st.columns(3)
        c1.metric("Avg Nightly Sleep", f"{avg_sleep:.1f} hrs")
        c2.metric("Avg Nap Duration", f"{avg_nap:.0f} min")
        c3.metric("Avg Total Rest", f"{avg_rest:.1f} hrs")

        # Stacked bar chart – sleep + nap hours per period
        st.subheader(f"Rest Breakdown by {period.rstrip('ly')}")

        # Build a combined dataframe with sleep and nap hours per period per date
        rest_frames = []
        if has_sleep:
            s_df = _period_col(sleep, "date_assigned", period)
            sleep_per_period = (
                s_df.groupby("period")["duration_minutes"]
                .sum().div(60).rename("Sleep (hrs)")
            )
            rest_frames.append(sleep_per_period)
        if has_naps:
            n_df = _period_col(naps, "date_assigned", period)
            nap_per_period = (
                n_df.groupby("period")["duration_minutes"]
                .sum().div(60).rename("Naps (hrs)")
            )
            rest_frames.append(nap_per_period)

        if rest_frames:
            rest_chart = pd.concat(rest_frames, axis=1).fillna(0).sort_index()
            st.bar_chart(rest_chart)

        # Sleep stats
        if has_sleep:
            st.subheader(f"Sleep Stats by {period.rstrip('ly')}")
            s_df = _period_col(sleep, "date_assigned", period)
            sleep_stats = []
            for p, grp in s_df.groupby("period"):
                s = _desc_stats(grp["duration_minutes"])
                s["period"] = p
                sleep_stats.append(s)
            sleep_stats_df = pd.DataFrame(sleep_stats)[
                ["period", "count", "total_hrs", "mean_min", "median_min",
                 "min_min", "max_min", "std_min"]
            ]
            st.dataframe(sleep_stats_df, use_container_width=True, hide_index=True)

        # Nap stats
        if has_naps:
            st.subheader(f"Nap Stats by {period.rstrip('ly')}")
            n_df = _period_col(naps, "date_assigned", period)
            nap_stats = []
            for p, grp in n_df.groupby("period"):
                s = _desc_stats(grp["duration_minutes"])
                s["period"] = p
                nap_stats.append(s)
            nap_stats_df = pd.DataFrame(nap_stats)[
                ["period", "count", "total_hrs", "mean_min", "median_min",
                 "min_min", "max_min", "std_min"]
            ]
            st.dataframe(nap_stats_df, use_container_width=True, hide_index=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 – SLEEP MODEL
# ═══════════════════════════════════════════════════════════════════════════════


@st.cache_data
def load_model_features():
    path = os.path.join(DATA_DIR, "model_features.csv")
    if not os.path.exists(path):
        return pd.DataFrame()
    return pd.read_csv(path)


@st.cache_data
def load_model_results():
    path = os.path.join(DATA_DIR, "model_results.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


with tab_model:
    st.header("Sleep Prediction Model")

    if st.button("Build Model"):
        with st.spinner("Building features and training models..."):
            result = subprocess.run(
                ["python", os.path.join(os.path.dirname(__file__), "sleep_model.py")],
                capture_output=True, text=True,
                cwd=os.path.dirname(__file__),
            )
        if result.returncode == 0:
            st.success("Model built successfully!")
            st.cache_data.clear()
        else:
            st.error("Model build failed.")
            st.code(result.stderr[-2000:] if result.stderr else result.stdout[-2000:])

    features = load_model_features()
    model_results = load_model_results()

    if features.empty and model_results is None:
        st.info(
            "No model results yet. Click **Build Model** to generate features "
            "and train the sleep prediction models.\n\n"
            "**Prerequisites:** Run **Refresh Data** first to ensure Garmin "
            "data is available. Optionally place a `caffeine.csv` in "
            "`garmin_exports/` for caffeine features."
        )
    else:
        # Feature table
        if not features.empty:
            st.subheader("Feature Table")
            st.dataframe(features, use_container_width=True, hide_index=True)

        # Model results
        if model_results and "models" in model_results:
            feature_cols = model_results.get("feature_columns", [])

            for model_key, label in [
                ("sleep_score", "Sleep Score (Linear Regression)"),
                ("sleep_hrs", "Sleep Hours (Linear Regression)"),
                ("sleep_gt_7hrs", "Sleep > 7 Hours (Logistic Regression)"),
            ]:
                m = model_results["models"].get(model_key, {})
                if m.get("skipped"):
                    st.subheader(label)
                    st.warning(f"Skipped: {m.get('reason', 'insufficient data')}")
                    continue

                if "coefficients" not in m:
                    continue

                st.subheader(label)

                # Metrics row
                if "r2" in m:
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("R²", f"{m['r2']:.4f}")
                    c2.metric("Adj R²", f"{m.get('r2_adj', 0):.4f}")
                    fp = m.get("f_pvalue")
                    c3.metric("F p-value", f"{fp:.4f}" if fp is not None else "N/A")
                    c4.metric("Samples", m.get("n_samples", "?"))
                elif "accuracy" in m:
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Accuracy", f"{m['accuracy']:.4f}")
                    c2.metric("Pseudo R²", f"{m.get('pseudo_r2', 0):.4f}")
                    c3.metric("Samples", m.get("n_samples", "?"))

                # Coefficients table with p-values and confidence intervals
                coef_rows = []
                for f, v in m["coefficients"].items():
                    if isinstance(v, dict):
                        coef_rows.append({
                            "Feature": f,
                            "Coefficient": v["coef"],
                            "p-value": v["p_value"],
                            "CI Low": v["ci_low"],
                            "CI High": v["ci_high"],
                            "Significant": "Yes" if v["p_value"] < 0.05 else "",
                        })
                    else:
                        coef_rows.append({"Feature": f, "Coefficient": v})
                coef_df = pd.DataFrame(coef_rows)
                st.dataframe(coef_df, use_container_width=True, hide_index=True)

                # Bar chart of coefficient values
                if coef_rows and "Coefficient" in coef_rows[0]:
                    chart_data = pd.DataFrame({
                        "Coefficient": {r["Feature"]: r["Coefficient"] for r in coef_rows}
                    })
                    st.bar_chart(chart_data)
