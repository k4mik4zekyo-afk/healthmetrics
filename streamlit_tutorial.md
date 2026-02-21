# Streamlit Tutorial — From Zero to Dashboard

This guide walks you through everything you need to know to build interactive Python web apps with Streamlit. No HTML, CSS, or JavaScript required — just Python.

Every concept is demonstrated in the companion script `streamlit_demo.py`. Run it side-by-side as you read:

```bash
streamlit run streamlit_demo.py
```

---

## 1. What is Streamlit?

Streamlit turns a plain Python script into a live web application. You write Python, call Streamlit functions to display text, charts, and widgets, and Streamlit handles the rest — rendering the page, managing the server, and reacting to user input.

There is no separate template language, no routes to define, no frontend build step. Your script *is* the app.

---

## 2. Installation

```bash
pip install streamlit
```

Verify it works:

```bash
streamlit hello
```

This launches a built-in demo app in your browser.

---

## 3. Running an App

Create a file called `my_app.py`:

```python
import streamlit as st

st.title("Hello, world!")
st.write("This is my first Streamlit app.")
```

Run it:

```bash
streamlit run my_app.py
```

Streamlit starts a local web server (default `http://localhost:8501`) and opens it in your browser. Every time you save the file, the app reloads automatically.

---

## 4. The Execution Model

This is the single most important thing to understand:

**Your script re-runs from top to bottom every time the user interacts with a widget.**

If a user clicks a button, changes a slider, or selects a dropdown option, Streamlit re-executes the entire script. The widget functions (`st.slider`, `st.selectbox`, etc.) return the *current* value of that widget, so variables update automatically.

```python
name = st.text_input("Your name")       # returns current text
st.write(f"Hello, {name}!")              # updates on every keystroke
```

This means:
- You don't write callbacks or event handlers
- You don't manage DOM state
- Variables declared at the top of your script get re-initialized on every run (unless cached — see Section 11)

---

## 5. Displaying Text

```python
st.title("Large title")              # biggest heading
st.header("Section header")          # h2
st.subheader("Subsection header")    # h3
st.write("General-purpose output")   # auto-detects type (text, DataFrame, chart, etc.)
st.markdown("**Bold**, *italic*, `code`")   # GitHub-flavored markdown
st.code("print('hello')", language="python")  # syntax-highlighted code block
st.divider()                         # horizontal rule
```

`st.write` is the Swiss Army knife — it handles strings, numbers, DataFrames, dicts, and even charts. When in doubt, use `st.write`.

---

## 6. Input Widgets

Widgets are how users interact with your app. Each widget function returns the current value selected by the user.

### Buttons

```python
if st.button("Click me"):
    st.write("Button was clicked!")
```

Buttons return `True` on the run where they were clicked, `False` otherwise.

### Radio buttons

```python
choice = st.radio("Pick one", ["Option A", "Option B", "Option C"])
st.write(f"You picked: {choice}")
```

### Select boxes (dropdowns)

```python
color = st.selectbox("Favorite color", ["Red", "Green", "Blue"])
```

### Multi-select

```python
colors = st.multiselect(
    "Pick colors",
    options=["Red", "Green", "Blue", "Yellow"],
    default=["Red", "Blue"],
)
st.write(f"Selected: {colors}")
```

The return value is a list of the selected options. This is what `dashboard.py` uses for activity type filtering — the user can click types on and off and the charts respond immediately.

### Sliders

```python
age = st.slider("Your age", min_value=0, max_value=120, value=25)
```

### Text input

```python
name = st.text_input("Enter your name", value="World")
```

### Number input

```python
count = st.number_input("How many?", min_value=1, max_value=100, value=10)
```

---

## 7. Displaying Data

### Metrics (KPI cards)

```python
st.metric(label="Revenue", value="$12,345", delta="+5%")
```

Renders a large number with an optional green/red delta indicator. In `dashboard.py`, three `st.metric` calls show total activity time, count, and average duration side by side.

### DataFrames

```python
import pandas as pd

df = pd.DataFrame({"Name": ["Alice", "Bob"], "Score": [95, 87]})
st.dataframe(df)                     # interactive (sortable, scrollable)
st.table(df)                         # static (no interaction)
```

`st.dataframe` supports options like `use_container_width=True` and `hide_index=True` to control appearance.

---

## 8. Charts

Streamlit has built-in chart functions that work directly with DataFrames:

### Bar chart

```python
import pandas as pd

data = pd.DataFrame({"Apples": [3, 5, 2], "Oranges": [4, 1, 6]},
                     index=["Jan", "Feb", "Mar"])
st.bar_chart(data)
```

Each column becomes a stacked color in the bar. The index becomes the x-axis labels. This is exactly how `dashboard.py` builds the activity-by-type chart — it pivots the data so each activity type is a column, and each period (week/month) is a row.

### Line chart

```python
st.line_chart(data)
```

### Area chart

```python
st.area_chart(data)
```

All three accept a DataFrame where:
- The **index** is the x-axis
- Each **column** is a separate series

For more control (axis labels, custom colors, tooltips), you can use Plotly, Altair, or Matplotlib with `st.plotly_chart`, `st.altair_chart`, or `st.pyplot`.

---

## 9. Layout

### Columns (side by side)

```python
col1, col2, col3 = st.columns(3)
col1.metric("Total", "42")
col2.metric("Average", "7.0")
col3.metric("Max", "12")
```

You can also use `with` blocks:

```python
col1, col2 = st.columns(2)
with col1:
    st.write("Left side")
    st.bar_chart(data)
with col2:
    st.write("Right side")
    st.line_chart(data)
```

`dashboard.py` uses `st.columns(3)` to lay out three KPI metrics in a row.

### Tabs

```python
tab1, tab2 = st.tabs(["First Tab", "Second Tab"])
with tab1:
    st.write("Content of tab 1")
with tab2:
    st.write("Content of tab 2")
```

`dashboard.py` uses tabs to separate Activities from Sleep & Rest.

### Sidebar

```python
with st.sidebar:
    st.header("Settings")
    option = st.radio("Period", ["Weekly", "Monthly"])
```

Anything placed in `st.sidebar` renders in a collapsible panel on the left. Widget return values work the same way. `dashboard.py` puts all controls (refresh button, period selector, activity filter) in the sidebar.

### Expanders (collapsible sections)

```python
with st.expander("Click to expand"):
    st.write("Hidden content goes here")
```

---

## 10. Feedback & Status

```python
st.success("Operation completed!")
st.error("Something went wrong.")
st.warning("Heads up — check your input.")
st.info("FYI: data was last refreshed at 3 PM.")
```

### Spinners (for long operations)

```python
with st.spinner("Loading data..."):
    import time
    time.sleep(2)  # simulate slow work
st.success("Done!")
```

The spinner shows an animated indicator while the code inside the `with` block runs. `dashboard.py` uses this around the data refresh subprocess call.

---

## 11. Caching

Since the script re-runs on every interaction, you don't want to re-read large files or re-compute expensive results every time. Use `@st.cache_data`:

```python
@st.cache_data
def load_data():
    return pd.read_csv("big_file.csv")

df = load_data()  # reads file on first call, returns cached result after
```

The cache key is based on the function name and arguments. If the function or its inputs don't change, the cached result is returned instantly.

To clear the cache programmatically (e.g., after refreshing data):

```python
st.cache_data.clear()
```

`dashboard.py` caches all three CSV loads (`load_activities`, `load_sleep`, `load_naps`) and clears the cache when the Refresh Data button is clicked.

---

## 12. Session State

Sometimes you need a variable to survive across reruns. Use `st.session_state`:

```python
if "counter" not in st.session_state:
    st.session_state.counter = 0

if st.button("Increment"):
    st.session_state.counter += 1

st.write(f"Count: {st.session_state.counter}")
```

Without session state, `counter` would reset to 0 on every rerun. Session state persists for the duration of the browser session.

---

## 13. Page Configuration

Call this **first**, before any other Streamlit commands:

```python
st.set_page_config(
    page_title="My Dashboard",    # browser tab title
    layout="wide",                # "centered" (default) or "wide"
    page_icon="📊",               # browser tab icon
)
```

`dashboard.py` uses `layout="wide"` to give charts more horizontal space.

---

## 14. How dashboard.py Uses All of This

Here's a mapping of concepts to their usage in the healthmetrics dashboard:

| Concept | Where in `dashboard.py` |
|---------|------------------------|
| `st.set_page_config` | Line 9 — sets wide layout |
| `@st.cache_data` | `load_activities`, `load_sleep`, `load_naps` functions |
| `st.sidebar` | Refresh button, period radio, activity multiselect |
| `st.button` | "Refresh Data" triggers subprocess |
| `st.spinner` | Wraps the Garmin API call |
| `st.success` / `st.error` | Feedback after refresh |
| `st.radio` | Weekly / Monthly toggle |
| `st.multiselect` | Activity type filter |
| `st.tabs` | Activities vs Sleep & Rest |
| `st.columns` + `st.metric` | KPI rows (3 metrics side by side) |
| `st.bar_chart` | Stacked activity time and sleep/nap charts |
| `st.dataframe` | Descriptive stats tables |
| `st.cache_data.clear()` | Invalidates CSV cache after refresh |

---

## 15. Common Patterns

### Filter a DataFrame from a widget

```python
all_types = df["type"].unique().tolist()
selected = st.multiselect("Filter by type", all_types, default=all_types)
filtered = df[df["type"].isin(selected)]
st.dataframe(filtered)
```

### Show different content based on a selection

```python
period = st.radio("View", ["Weekly", "Monthly"])
if period == "Weekly":
    st.bar_chart(weekly_data)
else:
    st.bar_chart(monthly_data)
```

### Run an external process from a button

```python
if st.button("Run script"):
    with st.spinner("Running..."):
        result = subprocess.run(["python", "my_script.py"], capture_output=True, text=True)
    if result.returncode == 0:
        st.success("Done!")
    else:
        st.error("Failed!")
        st.code(result.stderr)
```

---

## 16. Next Steps

- **Official docs:** https://docs.streamlit.io
- **API reference:** https://docs.streamlit.io/develop/api-reference
- **Component gallery:** https://streamlit.io/components
- **Run the demo:** `streamlit run streamlit_demo.py` to see everything from this tutorial in action
