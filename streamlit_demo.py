"""
Streamlit Feature Demo
======================
Run this app to see every major Streamlit feature in action:

    streamlit run streamlit_demo.py

No Garmin credentials or external data needed — everything uses sample data
generated inside the script.

Read along with streamlit_tutorial.md for explanations of each concept.
"""

import time
import numpy as np
import pandas as pd
import streamlit as st

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG  (must be the first Streamlit call)
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Streamlit Demo", layout="wide")

# ─────────────────────────────────────────────────────────────────────────────
# SAMPLE DATA
# ─────────────────────────────────────────────────────────────────────────────

np.random.seed(42)

dates = pd.date_range("2026-01-01", periods=30, freq="D")
sample_df = pd.DataFrame({
    "date": dates,
    "category": np.random.choice(["Running", "Walking", "Cycling", "Swimming"], size=30),
    "duration_min": np.random.randint(15, 90, size=30),
    "calories": np.random.randint(80, 500, size=30),
    "heart_rate": np.random.randint(90, 175, size=30),
})

# ─────────────────────────────────────────────────────────────────────────────
# 1. TITLE & TEXT
# ─────────────────────────────────────────────────────────────────────────────

st.title("Streamlit Feature Demo")

st.markdown("""
This app demonstrates the core building blocks of Streamlit.  Each section
below corresponds to a chapter in `streamlit_tutorial.md`.  **The code that
produces what you see here lives in `streamlit_demo.py`** — open it in your
editor and follow along.
""")

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# 2. SIDEBAR CONTROLS
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("Controls")

    st.markdown("Widgets placed in `st.sidebar` appear in this collapsible "
                "panel. Their return values work the same as in the main area.")

    period = st.radio("Aggregate by", ["Weekly", "Monthly"],
                      help="Changes how the charts below group data.")

    selected_categories = st.multiselect(
        "Activity types",
        options=sorted(sample_df["category"].unique()),
        default=sorted(sample_df["category"].unique()),
        help="Deselect a type to remove it from charts and stats.",
    )

    slider_val = st.slider("Min duration (minutes)", 0, 90, 0,
                           help="Filters out activities shorter than this.")

    text_val = st.text_input("Your name", value="World",
                             help="Used in the greeting below.")

    st.divider()
    st.caption("These controls drive the rest of the app. Change them and "
               "watch everything update instantly.")

# ─────────────────────────────────────────────────────────────────────────────
# 3. TEXT OUTPUT EXAMPLES
# ─────────────────────────────────────────────────────────────────────────────

st.header("1 — Text & Markdown")

st.write(f"Hello, **{text_val}**! (`st.write` auto-detects markdown)")

col_a, col_b = st.columns(2)
with col_a:
    st.subheader("st.write")
    st.write("Handles strings, numbers, dicts, DataFrames — almost anything.")
    st.write({"key": "value", "number": 42})
with col_b:
    st.subheader("st.code")
    st.code('st.write("Hello, world!")', language="python")

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# 4. FILTERING THE DATA
# ─────────────────────────────────────────────────────────────────────────────

st.header("2 — Interactive Filtering")

st.markdown("""
The sidebar widgets above filter the sample dataset. Every time you change a
widget, the **entire script re-runs** and `filtered_df` is recomputed.
No callbacks needed — Streamlit's execution model handles it.
""")

filtered_df = sample_df[
    (sample_df["category"].isin(selected_categories)) &
    (sample_df["duration_min"] >= slider_val)
].copy()

st.write(f"**{len(filtered_df)}** of {len(sample_df)} activities match your filters.")

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# 5. METRICS (KPI CARDS)
# ─────────────────────────────────────────────────────────────────────────────

st.header("3 — Metrics")

st.markdown("`st.metric` creates large KPI cards. Lay them side by side with "
            "`st.columns`.")

if not filtered_df.empty:
    total_hrs = filtered_df["duration_min"].sum() / 60
    avg_dur = filtered_df["duration_min"].mean()
    avg_hr = filtered_df["heart_rate"].mean()
else:
    total_hrs = avg_dur = avg_hr = 0

c1, c2, c3 = st.columns(3)
c1.metric("Total Time", f"{total_hrs:.1f} hrs")
c2.metric("Avg Duration", f"{avg_dur:.0f} min")
c3.metric("Avg Heart Rate", f"{avg_hr:.0f} bpm")

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# 6. TABS
# ─────────────────────────────────────────────────────────────────────────────

st.header("4 — Tabs, Charts & DataFrames")

st.markdown("Use `st.tabs` to organize content into switchable panels.")

tab_charts, tab_data, tab_expander = st.tabs(["Charts", "Data Table", "Expanders"])

# ── Tab 1: Charts ──

with tab_charts:
    st.subheader("Bar Chart — Activity time by period & type")

    st.markdown("""
    `st.bar_chart` takes a DataFrame where the **index** becomes the x-axis and
    each **column** becomes a stacked color.  We pivot the data so each activity
    type is its own column — exactly the same technique used in `dashboard.py`.
    """)

    if not filtered_df.empty:
        chart_df = filtered_df.copy()
        chart_df["date"] = pd.to_datetime(chart_df["date"])
        if period == "Weekly":
            iso = chart_df["date"].dt.isocalendar()
            chart_df["period"] = iso.year.astype(str) + "-W" + iso.week.astype(str).str.zfill(2)
        else:
            chart_df["period"] = chart_df["date"].dt.to_period("M").astype(str)

        pivot = (
            chart_df
            .groupby(["period", "category"])["duration_min"]
            .sum()
            .div(60)
            .reset_index()
            .pivot(index="period", columns="category", values="duration_min")
            .fillna(0)
            .sort_index()
        )
        st.bar_chart(pivot)
    else:
        st.info("No data matches your filters.")

    st.subheader("Line Chart & Area Chart")

    st.markdown("`st.line_chart` and `st.area_chart` have the same API as "
                "`st.bar_chart`.")

    if not filtered_df.empty:
        line_data = (
            chart_df
            .groupby("period")[["duration_min", "calories"]]
            .mean()
            .sort_index()
        )
        left, right = st.columns(2)
        with left:
            st.caption("Line chart — avg duration & calories per period")
            st.line_chart(line_data)
        with right:
            st.caption("Area chart — same data")
            st.area_chart(line_data)

# ── Tab 2: Data Table ──

with tab_data:
    st.subheader("st.dataframe — Interactive Table")

    st.markdown("""
    `st.dataframe` renders a sortable, scrollable table. Click any column
    header to sort. Use `hide_index=True` and `use_container_width=True`
    for a cleaner look.
    """)

    st.dataframe(filtered_df, use_container_width=True, hide_index=True)

    st.subheader("st.table — Static Table")

    st.markdown("`st.table` renders a fixed table with no interaction. Best "
                "for small summaries.")

    st.table(filtered_df.describe().round(1))

# ── Tab 3: Expanders ──

with tab_expander:
    st.subheader("st.expander — Collapsible Sections")

    st.markdown("Use expanders to hide details that not everyone needs to see.")

    with st.expander("Click to see raw sample data"):
        st.write(sample_df)

    with st.expander("Click to see filter settings"):
        st.write({
            "Selected categories": selected_categories,
            "Min duration": slider_val,
            "Period": period,
        })

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# 7. CACHING
# ─────────────────────────────────────────────────────────────────────────────

st.header("5 — Caching")

st.markdown("""
Since the script re-runs on every interaction, expensive operations (loading
big files, calling APIs) would be painfully slow without caching.

Decorate a function with `@st.cache_data` and Streamlit will cache the return
value.  Subsequent calls with the same arguments return instantly.
""")

st.code("""
@st.cache_data
def load_data():
    return pd.read_csv("big_file.csv")   # only reads once

df = load_data()   # instant on re-runs
""", language="python")


@st.cache_data
def expensive_computation(n):
    """Simulates a slow computation."""
    time.sleep(2)
    return pd.DataFrame({
        "x": range(n),
        "y": np.cumsum(np.random.randn(n)),
    })


cache_n = st.number_input("Generate N points (cached)", min_value=10,
                           max_value=500, value=100, step=10)

if st.button("Run cached computation"):
    with st.spinner("Computing (only slow the first time per N value)..."):
        result = expensive_computation(cache_n)
    st.success(f"Got {len(result)} rows!")
    st.line_chart(result.set_index("x"))

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# 8. SESSION STATE
# ─────────────────────────────────────────────────────────────────────────────

st.header("6 — Session State")

st.markdown("""
Normal variables reset on every rerun. `st.session_state` lets values persist
across interactions for the duration of the browser session.
""")

if "click_count" not in st.session_state:
    st.session_state.click_count = 0

col_left, col_right = st.columns([1, 2])
with col_left:
    if st.button("Increment counter"):
        st.session_state.click_count += 1
    st.metric("Click count", st.session_state.click_count)
with col_right:
    st.code("""
if "click_count" not in st.session_state:
    st.session_state.click_count = 0

if st.button("Increment counter"):
    st.session_state.click_count += 1

st.metric("Click count", st.session_state.click_count)
""", language="python")

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# 9. FEEDBACK WIDGETS
# ─────────────────────────────────────────────────────────────────────────────

st.header("7 — Feedback Widgets")

st.markdown("Use these to communicate status to the user.")

f1, f2, f3, f4 = st.columns(4)
with f1:
    st.success("st.success")
with f2:
    st.error("st.error")
with f3:
    st.warning("st.warning")
with f4:
    st.info("st.info")

if st.button("Run with spinner"):
    with st.spinner("Working..."):
        time.sleep(1.5)
    st.success("Done! The spinner disappears when the `with` block exits.")

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# 10. PUTTING IT ALL TOGETHER
# ─────────────────────────────────────────────────────────────────────────────

st.header("8 — Putting It All Together")

st.markdown("""
The `dashboard.py` file in this project combines all the concepts above into a
real-world health metrics dashboard:

| Concept | Usage in `dashboard.py` |
|---------|------------------------|
| `st.set_page_config` | Wide layout |
| `@st.cache_data` | CSV loading functions |
| `st.sidebar` | Refresh button, period radio, activity filter |
| `st.button` + `subprocess` | Live data refresh from Garmin |
| `st.spinner` | Loading indicator during refresh |
| `st.radio` | Weekly / Monthly toggle |
| `st.multiselect` | Activity type filter |
| `st.tabs` | Activities vs Sleep & Rest |
| `st.columns` + `st.metric` | KPI rows |
| `st.bar_chart` | Stacked time charts |
| `st.dataframe` | Stats tables |

Open `dashboard.py` to see how these pieces fit into a complete application.
""")

st.caption("End of demo. See streamlit_tutorial.md for the full written guide.")
