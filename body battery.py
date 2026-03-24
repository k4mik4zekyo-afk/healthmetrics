import os
import pandas as pd
import pytz
from datetime import datetime, timedelta
from dateutil import parser
from garminconnect import Garmin
from dotenv import load_dotenv

load_dotenv()  # looks for .env in current & parent dirs

# -----------------------------
# CONFIG
# -----------------------------
START_DATE = "2026-01-01"
END_DATE   = "2026-03-01"
TIMEZONE   = "America/Los_Angeles"

BB_MIN_GAIN_NAP = 5          # body battery points
NAP_MIN_MINUTES = 20
NAP_MAX_MINUTES = 120
SLEEP_MIN_MINUTES = 180
STRESS_REST_THRESHOLD = 15   # stress level below this = resting/sleeping

OUTPUT_DIR = "./garmin_exports"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# -----------------------------
# AUTH
# -----------------------------
email = os.getenv("GARMIN_EMAIL")
password = os.getenv("GARMIN_PASSWORD")

if not email or not password:
    raise RuntimeError("Missing Garmin credentials")

client = Garmin(email, password)
client.login()

tz = pytz.timezone(TIMEZONE)

# -----------------------------
# STRESS DATA (for rest detection)
# Use stress levels to identify rest periods
stress_rows = []

start = parser.parse(START_DATE)
end   = parser.parse(END_DATE)

current = start
while current <= end:
    data = client.get_stress_data(current.strftime("%Y-%m-%d"))
    if data and "stressValuesArray" in data:
        values_array = data.get("stressValuesArray", [])
        for value_pair in values_array:
            timestamp_ms = value_pair[0]
            stress_level = value_pair[1]
            
            if stress_level is None:
                continue
            # Filter out stress=0 (treat as not resting/unmeasured)
            if stress_level == 0:
                continue
            
            ts = datetime.fromtimestamp(
                timestamp_ms / 1000,
                tz=pytz.UTC
            ).astimezone(tz)
            
            stress_rows.append({
                "timestamp": ts,
                "date_assigned": ts.date(),
                "stress_level": stress_level
            })
    current += timedelta(days=1)

if stress_rows:
    stress_df = pd.DataFrame(stress_rows).sort_values("timestamp")
    stress_df["is_resting"] = stress_df["stress_level"] < STRESS_REST_THRESHOLD
else:
    print("⚠️  No stress data found. Creating empty DataFrame.")
    stress_df = pd.DataFrame(columns=["timestamp", "date_assigned", "stress_level", "is_resting"])

stress_df.to_csv(f"{OUTPUT_DIR}/stress_timeseries.csv", index=False)

# Keep body battery for reference but don't use for nap detection
bb_rows = []
bb_df = pd.DataFrame(columns=["timestamp", "date_assigned", "body_battery"])

# -----------------------------
# ACTIVITIES
# -----------------------------
print("Fetching activities...")
raw_activities = client.get_activities_by_date(START_DATE, END_DATE, sortorder="asc")
activity_rows = []
for act in raw_activities:
    act_type = act.get("activityType", {})
    start_local = act.get("startTimeLocal", "")
    date_assigned = start_local[:10] if len(start_local) >= 10 else None
    duration_sec = act.get("duration")
    activity_rows.append({
        "activity_id": act.get("activityId"),
        "activity_name": act.get("activityName"),
        "activity_type": act_type.get("typeKey", "unknown"),
        "start_time": start_local,
        "duration_minutes": round(duration_sec / 60, 2) if duration_sec else None,
        "distance_meters": act.get("distance"),
        "calories": act.get("calories"),
        "average_hr": act.get("averageHR"),
        "max_hr": act.get("maxHR"),
        "date_assigned": date_assigned,
    })

activity_df = pd.DataFrame(activity_rows)
activity_df.to_csv(f"{OUTPUT_DIR}/activities.csv", index=False)
print(f"  Found {len(activity_rows)} activities.")

# -----------------------------
# SLEEP EVENTS
# -----------------------------
sleep_rows = []

current = start
while current <= end:

    date_str = current.strftime("%Y-%m-%d")
    sleep_data = client.get_sleep_data(date_str)
    duration_minutes = None
    start_ts = None
    end_ts = None
    # Use Garmin's reported sleep duration if available
    if sleep_data and "dailySleepDTO" in sleep_data:
        dto = sleep_data["dailySleepDTO"]
        # Prefer Garmin's reported sleepTimeSeconds
        sleep_seconds = dto.get("sleepTimeSeconds")
        if sleep_seconds is not None:
            duration_minutes = sleep_seconds / 60
        # Fallback: calculate from timestamps if needed
        if duration_minutes is None or duration_minutes == 0:
            if dto.get("sleepStartTimestampGMT") and dto.get("sleepEndTimestampGMT"):
                start_ts = datetime.fromtimestamp(
                    dto["sleepStartTimestampGMT"] / 1000, tz=pytz.UTC
                ).astimezone(tz)
                end_ts = datetime.fromtimestamp(
                    dto["sleepEndTimestampGMT"] / 1000, tz=pytz.UTC
                ).astimezone(tz)
                duration_minutes = (end_ts - start_ts).total_seconds() / 60
        else:
            # If we have timestamps, keep them for reference
            if dto.get("sleepStartTimestampGMT") and dto.get("sleepEndTimestampGMT"):
                start_ts = datetime.fromtimestamp(
                    dto["sleepStartTimestampGMT"] / 1000, tz=pytz.UTC
                ).astimezone(tz)
                end_ts = datetime.fromtimestamp(
                    dto["sleepEndTimestampGMT"] / 1000, tz=pytz.UTC
                ).astimezone(tz)

        # Only add if duration meets threshold
        if duration_minutes is not None and duration_minutes >= SLEEP_MIN_MINUTES:
            bb_gain = None
            if not bb_df.empty and start_ts and end_ts:
                bb_start_rows = bb_df.loc[bb_df["timestamp"] >= start_ts, "body_battery"]
                bb_end_rows = bb_df.loc[bb_df["timestamp"] <= end_ts, "body_battery"]
                if not bb_start_rows.empty and not bb_end_rows.empty:
                    bb_gain = bb_end_rows.iloc[-1] - bb_start_rows.iloc[0]
            # Assign to local date of sleep_end (wake-up date), matching Garmin Connect
            if end_ts:
                date_assigned = end_ts.date()
            else:
                date_assigned = current.date()
            # Extract sleep score from Garmin's sleepScores object
            sleep_score = dto.get("sleepScores", {}).get("overall", {}).get("value")
            sleep_rows.append({
                "sleep_start": start_ts,
                "sleep_end": end_ts,
                "duration_minutes": duration_minutes,
                "bb_gain": bb_gain,
                "sleep_score": sleep_score,
                "date_assigned": date_assigned
            })
        elif duration_minutes is not None and duration_minutes > 0:
            # If duration is below threshold, still warn
            print(f"⚠️  {date_str}: Sleep duration {duration_minutes:.1f} min (below threshold)")
        elif duration_minutes == 0 or duration_minutes is None:
            print(f"⚠️  {date_str}: No sleep recorded or sleep duration is 0")
    else:
        print(f"⚠️  {date_str}: No sleep data from Garmin API")
    current += timedelta(days=1)

sleep_df = pd.DataFrame(sleep_rows)
sleep_df.to_csv(f"{OUTPUT_DIR}/sleep_events.csv", index=False)

# -----------------------------
# NAP DETECTION FROM STRESS
# Find periods where stress is below threshold (resting) during waking hours
# Exclude any periods that overlap with detected sleep
nap_rows = []

# Group by date to find intra-day rest periods (avoid crossing midnight)
for date in stress_df["date_assigned"].unique():
    day_df = stress_df[stress_df["date_assigned"] == date].sort_values("timestamp")
    
    if len(day_df) < 2:
        continue
    
    # Find continuous periods where stress is below threshold (resting)
    rest_start = None
    rest_start_stress = None
    
    for idx, (_, row) in enumerate(day_df.iterrows()):
        current_stress = row["stress_level"]
        
        # Start a rest period if stress drops below threshold and we haven't started yet
        if row["is_resting"] and rest_start is None:
            rest_start = row["timestamp"]
            rest_start_stress = current_stress
        
        # Continue rest if still below threshold
        elif row["is_resting"] and rest_start is not None:
            continue
        
        # Rest period ended (stress >= threshold)
        elif not row["is_resting"] and rest_start is not None:
            rest_end = day_df.iloc[idx-1]["timestamp"] if idx > 0 else row["timestamp"]
            rest_end_stress = day_df.iloc[idx-1]["stress_level"] if idx > 0 else current_stress
            
            duration = (rest_end - rest_start).total_seconds() / 60
            
            # Only consider as nap if it doesn't overlap with sleep and is 20-120 minutes
            if NAP_MIN_MINUTES <= duration <= NAP_MAX_MINUTES:
                # Check if this overlaps with sleep
                overlaps_sleep = any(
                    (rest_start < s["sleep_end"] and rest_end > s["sleep_start"])
                    for s in sleep_rows
                )
                
                if not overlaps_sleep:
                    nap_rows.append({
                        "nap_start": rest_start,
                        "nap_end": rest_end,
                        "duration_minutes": duration,
                        "stress_start": rest_start_stress,
                        "stress_end": rest_end_stress,
                        "date_assigned": date
                    })
            
            rest_start = None
            rest_start_stress = None

nap_df = pd.DataFrame(nap_rows)
nap_df.to_csv(f"{OUTPUT_DIR}/nap_events.csv", index=False)

# -----------------------------
# DAILY SUMMARY
# -----------------------------
summary = []

# Get dates from sleep data if body battery is empty
if not stress_df.empty:
    dates = sorted(set(stress_df["date_assigned"]))
elif not sleep_df.empty:
    dates = sorted(set(sleep_df["date_assigned"]))
else:
    dates = []

for d in dates:
    # Debug: print all sleep events for this date
    print(f"\nSummary for {d}:")
    sleep_events = sleep_df.loc[sleep_df["date_assigned"] == d]
    if not sleep_events.empty:
        print(f"  Sleep events: {sleep_events[['sleep_start','sleep_end','duration_minutes','date_assigned']].to_dict('records')}")
        sleep_minutes = sleep_events["duration_minutes"].max()
        print(f"  Selected sleep_minutes: {sleep_minutes}")
    else:
        print("  No sleep events found for this date.")
        sleep_minutes = 0.0
    nap_minutes   = nap_df.loc[nap_df["date_assigned"] == d, "duration_minutes"].sum() if not nap_df.empty else 0
    print(f"  Nap minutes: {nap_minutes}")
    summary.append({
        "date": d,
        "total_sleep_minutes": round(sleep_minutes),
        "total_nap_minutes": round(nap_minutes),
        "total_rest_minutes": round(sleep_minutes + nap_minutes)
    })

summary_df = pd.DataFrame(summary)
summary_df.to_csv(f"{OUTPUT_DIR}/daily_rest_summary.csv", index=False)

print("✅ Garmin rest analysis export complete.")
