"""
Sleep Prediction Model
======================
Builds a daily feature table from Garmin stress, activity, and optional
caffeine data, then trains three models to predict sleep outcomes:

    1. Linear regression  → Garmin sleep score (0-100)
    2. Linear regression  → sleep duration (hours)
    3. Logistic regression → slept more than 7 hours (binary)

Usage:
    python sleep_model.py

Reads CSVs from garmin_exports/ and writes:
    - garmin_exports/model_features.csv   (daily feature table)
    - garmin_exports/model_results.json   (trained model coefficients & metrics)
"""

import json
import os
import sys

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import accuracy_score, r2_score

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "garmin_exports")

MINUTES_PER_READING = 3  # stress timeseries is sampled every 3 minutes

# ── data loading ─────────────────────────────────────────────────────────────


def load_stress():
    df = pd.read_csv(os.path.join(DATA_DIR, "stress_timeseries.csv"))
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df["date_assigned"] = pd.to_datetime(df["date_assigned"]).dt.date
    return df


def load_sleep():
    df = pd.read_csv(os.path.join(DATA_DIR, "sleep_events.csv"))
    for col in ("sleep_start", "sleep_end"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], utc=True)
    df["date_assigned"] = pd.to_datetime(df["date_assigned"]).dt.date
    return df


def load_activities():
    path = os.path.join(DATA_DIR, "activities.csv")
    if not os.path.exists(path):
        return pd.DataFrame(columns=["start_time", "duration_minutes", "date_assigned"])
    df = pd.read_csv(path)
    if "start_time" in df.columns:
        df["start_time"] = pd.to_datetime(df["start_time"], utc=True)
        df["end_time"] = df["start_time"] + pd.to_timedelta(df["duration_minutes"], unit="m")
    df["date_assigned"] = pd.to_datetime(df["date_assigned"]).dt.date
    return df


def load_caffeine():
    path = os.path.join(DATA_DIR, "caffeine.csv")
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path)
    # Normalise column names (handle case / spacing variations)
    df.columns = df.columns.str.strip().str.lower()
    df.rename(columns={
        "estimated mg": "estimated_mg",
        "last drink time": "last_drink_time",
    }, inplace=True)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"]).dt.date
    return df


# ── helpers ──────────────────────────────────────────────────────────────────


def _in_any_window(ts, windows):
    """Return True if timestamp falls inside any (start, end) window."""
    for ws, we in windows:
        if ws <= ts <= we:
            return True
    return False


# ── feature engineering ──────────────────────────────────────────────────────


def build_features(stress_df, sleep_df, act_df, caffeine_df):
    """Build one row per date with stress-bucket hours, activity flag, caffeine,
    and next-night sleep targets."""

    # Pre-compute sleep and activity windows for fast lookup
    sleep_windows = []
    for _, r in sleep_df.iterrows():
        if pd.notna(r.get("sleep_start")) and pd.notna(r.get("sleep_end")):
            sleep_windows.append((r["sleep_start"], r["sleep_end"]))

    act_windows_by_date = {}
    if not act_df.empty and "start_time" in act_df.columns:
        for _, r in act_df.iterrows():
            if pd.notna(r.get("start_time")) and pd.notna(r.get("end_time")):
                d = r["date_assigned"]
                act_windows_by_date.setdefault(d, []).append(
                    (r["start_time"], r["end_time"])
                )

    # Map sleep by date_assigned for target join (features from D → sleep D+1)
    sleep_by_date = {}
    for _, r in sleep_df.iterrows():
        sleep_by_date[r["date_assigned"]] = r

    # Caffeine by date
    caffeine_by_date = {}
    has_caffeine = caffeine_df is not None and not caffeine_df.empty
    if has_caffeine:
        for d, grp in caffeine_df.groupby("date"):
            mg_col = "estimated_mg" if "estimated_mg" in grp.columns else None
            total_mg = grp[mg_col].sum() if mg_col and mg_col in grp.columns else 0
            # Last drink time — try to parse
            last_time = None
            if "last_drink_time" in grp.columns:
                times = grp["last_drink_time"].dropna()
                if not times.empty:
                    try:
                        parsed = pd.to_datetime(times, format="mixed")
                        last_time = parsed.max()
                    except Exception:
                        pass
            caffeine_by_date[d] = {"mg": total_mg, "last_time": last_time}

    dates = sorted(stress_df["date_assigned"].unique())
    rows = []

    for date in dates:
        day_stress = stress_df[stress_df["date_assigned"] == date].copy()

        # Filter to waking hours: exclude timestamps inside sleep windows
        mask_awake = ~day_stress["timestamp"].apply(
            lambda ts: _in_any_window(ts, sleep_windows)
        )
        awake_stress = day_stress[mask_awake]

        # Filter out unmeasured/rest markers: stress_level in {-2, -1, 0}
        measured = awake_stress[awake_stress["stress_level"] > 0]

        # Activity windows for this date
        act_wins = act_windows_by_date.get(date, [])

        # Classify each reading
        counts = {"rest": 0, "low": 0, "medium": 0, "high": 0, "in_activity": 0}
        for _, r in measured.iterrows():
            if _in_any_window(r["timestamp"], act_wins):
                counts["in_activity"] += 1
            elif r["stress_level"] < 15:
                counts["rest"] += 1
            elif r["stress_level"] < 30:
                counts["low"] += 1
            elif r["stress_level"] < 50:
                counts["medium"] += 1
            else:
                counts["high"] += 1

        # Convert counts to hours
        row = {
            "date": date,
            "rest_hrs": round(counts["rest"] * MINUTES_PER_READING / 60, 2),
            "low_stress_hrs": round(counts["low"] * MINUTES_PER_READING / 60, 2),
            "med_stress_hrs": round(counts["medium"] * MINUTES_PER_READING / 60, 2),
            "high_stress_hrs": round(counts["high"] * MINUTES_PER_READING / 60, 2),
            "in_activity_hrs": round(counts["in_activity"] * MINUTES_PER_READING / 60, 2),
            "had_activity": 1 if date in act_windows_by_date else 0,
        }

        # Caffeine (optional)
        if has_caffeine:
            caf = caffeine_by_date.get(date, {})
            row["caffeine_mg"] = caf.get("mg", 0)
            # Hours between last caffeine and sleep start
            from datetime import timedelta
            next_date = date + timedelta(days=1)
            next_sleep = sleep_by_date.get(next_date)
            if caf.get("last_time") is not None and next_sleep is not None and pd.notna(next_sleep.get("sleep_start")):
                delta = (next_sleep["sleep_start"] - caf["last_time"]).total_seconds() / 3600
                row["last_caffeine_hrs_before_sleep"] = round(max(delta, 0), 2)
            else:
                row["last_caffeine_hrs_before_sleep"] = np.nan

        # Targets: sleep that STARTS evening of this date → assigned to next day
        from datetime import timedelta
        next_date = date + timedelta(days=1)
        next_sleep = sleep_by_date.get(next_date)
        if next_sleep is not None:
            row["sleep_score"] = next_sleep.get("sleep_score")
            row["sleep_hrs"] = round(next_sleep["duration_minutes"] / 60, 2)
            row["sleep_gt_7hrs"] = 1 if row["sleep_hrs"] >= 7 else 0
        else:
            row["sleep_score"] = np.nan
            row["sleep_hrs"] = np.nan
            row["sleep_gt_7hrs"] = np.nan

        rows.append(row)

    return pd.DataFrame(rows)


# ── model training ───────────────────────────────────────────────────────────


def train_models(features_df):
    """Train three models and return a results dict."""

    # Determine feature columns
    base_features = [
        "rest_hrs", "low_stress_hrs", "med_stress_hrs",
        "high_stress_hrs", "in_activity_hrs", "had_activity",
    ]
    caffeine_features = []
    if "caffeine_mg" in features_df.columns:
        caffeine_features = ["caffeine_mg", "last_caffeine_hrs_before_sleep"]
    feature_cols = base_features + caffeine_features

    results = {"feature_columns": feature_cols, "models": {}}

    # ── Model 1: Linear regression → sleep_score ──
    target = "sleep_score"
    df_m = features_df.dropna(subset=[target] + feature_cols)
    if len(df_m) >= 5:
        X, y = df_m[feature_cols].values, df_m[target].values
        model = LinearRegression().fit(X, y)
        y_pred = model.predict(X)
        r2 = r2_score(y, y_pred)
        results["models"]["sleep_score"] = {
            "type": "linear_regression",
            "target": target,
            "r2": round(r2, 4),
            "intercept": round(model.intercept_, 4),
            "coefficients": {f: round(c, 4) for f, c in zip(feature_cols, model.coef_)},
            "n_samples": len(df_m),
        }
        print(f"\n{'='*60}")
        print(f"Model 1: Linear Regression → {target}")
        print(f"{'='*60}")
        print(f"  Samples: {len(df_m)}")
        print(f"  R²:      {r2:.4f}")
        print(f"  Intercept: {model.intercept_:.4f}")
        for f, c in zip(feature_cols, model.coef_):
            print(f"  {f:40s} {c:+.4f}")
    else:
        print(f"\n⚠️  Skipping sleep_score model: only {len(df_m)} samples (need ≥5)")
        results["models"]["sleep_score"] = {"skipped": True, "reason": f"only {len(df_m)} valid samples"}

    # ── Model 2: Linear regression → sleep_hrs ──
    target = "sleep_hrs"
    df_m = features_df.dropna(subset=[target] + feature_cols)
    if len(df_m) >= 5:
        X, y = df_m[feature_cols].values, df_m[target].values
        model = LinearRegression().fit(X, y)
        y_pred = model.predict(X)
        r2 = r2_score(y, y_pred)
        results["models"]["sleep_hrs"] = {
            "type": "linear_regression",
            "target": target,
            "r2": round(r2, 4),
            "intercept": round(model.intercept_, 4),
            "coefficients": {f: round(c, 4) for f, c in zip(feature_cols, model.coef_)},
            "n_samples": len(df_m),
        }
        print(f"\n{'='*60}")
        print(f"Model 2: Linear Regression → {target}")
        print(f"{'='*60}")
        print(f"  Samples: {len(df_m)}")
        print(f"  R²:      {r2:.4f}")
        print(f"  Intercept: {model.intercept_:.4f}")
        for f, c in zip(feature_cols, model.coef_):
            print(f"  {f:40s} {c:+.4f}")
    else:
        print(f"\n⚠️  Skipping sleep_hrs model: only {len(df_m)} samples (need ≥5)")
        results["models"]["sleep_hrs"] = {"skipped": True, "reason": f"only {len(df_m)} valid samples"}

    # ── Model 3: Logistic regression → sleep_gt_7hrs ──
    target = "sleep_gt_7hrs"
    df_m = features_df.dropna(subset=[target] + feature_cols)
    if len(df_m) >= 5 and df_m[target].nunique() > 1:
        X, y = df_m[feature_cols].values, df_m[target].astype(int).values
        model = LogisticRegression(max_iter=1000).fit(X, y)
        y_pred = model.predict(X)
        acc = accuracy_score(y, y_pred)
        results["models"]["sleep_gt_7hrs"] = {
            "type": "logistic_regression",
            "target": target,
            "accuracy": round(acc, 4),
            "intercept": round(model.intercept_[0], 4),
            "coefficients": {f: round(c, 4) for f, c in zip(feature_cols, model.coef_[0])},
            "n_samples": len(df_m),
            "class_distribution": {str(k): int(v) for k, v in zip(*np.unique(y, return_counts=True))},
        }
        print(f"\n{'='*60}")
        print(f"Model 3: Logistic Regression → {target}")
        print(f"{'='*60}")
        print(f"  Samples:  {len(df_m)}")
        print(f"  Accuracy: {acc:.4f}")
        dist = dict(zip(*np.unique(y, return_counts=True)))
        print(f"  Classes:  0={dist.get(0,0)}, 1={dist.get(1,0)}")
        print(f"  Intercept: {model.intercept_[0]:.4f}")
        for f, c in zip(feature_cols, model.coef_[0]):
            print(f"  {f:40s} {c:+.4f}")
    else:
        reason = f"only {len(df_m)} samples" if len(df_m) < 5 else "only one class present"
        print(f"\n⚠️  Skipping sleep_gt_7hrs model: {reason}")
        results["models"]["sleep_gt_7hrs"] = {"skipped": True, "reason": reason}

    return results


# ── main ─────────────────────────────────────────────────────────────────────


def main():
    print("Loading data...")
    stress_df = load_stress()
    sleep_df = load_sleep()
    act_df = load_activities()
    caffeine_df = load_caffeine()

    if caffeine_df is not None:
        print(f"  Caffeine data: {len(caffeine_df)} rows")
    else:
        print("  No caffeine.csv found — caffeine features will be omitted.")

    print(f"  Stress readings: {len(stress_df)}")
    print(f"  Sleep events:    {len(sleep_df)}")
    print(f"  Activities:      {len(act_df)}")

    print("\nBuilding features...")
    features_df = build_features(stress_df, sleep_df, act_df, caffeine_df)

    # Save feature table
    out_path = os.path.join(DATA_DIR, "model_features.csv")
    features_df.to_csv(out_path, index=False)
    print(f"  Feature table saved: {out_path} ({len(features_df)} rows)")

    # How many complete rows (have at least sleep_hrs target)?
    complete = features_df.dropna(subset=["sleep_hrs"])
    print(f"  Complete rows (with sleep target): {len(complete)}")

    if len(complete) < 5:
        print("\n⚠️  Not enough data to train models (need ≥5 complete rows).")
        print("    Run 'body battery.py' with a wider date range and try again.")
        sys.exit(0)

    print("\nTraining models...")
    results = train_models(features_df)

    # Save results
    results_path = os.path.join(DATA_DIR, "model_results.json")
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n✅ Model results saved: {results_path}")


if __name__ == "__main__":
    main()
