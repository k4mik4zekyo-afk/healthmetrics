import pandas as pd
import matplotlib.pyplot as plt

# Load the daily rest summary
df = pd.read_csv('garmin_exports/daily_rest_summary.csv')

# Convert minutes to hours for plotting
dates = df['date']
sleep = df['total_sleep_minutes'] / 60
nap = df['total_nap_minutes'] / 60
rest = df['total_rest_minutes'] / 60

fig, ax = plt.subplots(figsize=(12, 6))

# Stacked bars for sleep and nap
d1 = ax.bar(dates, sleep, label='Sleep Hours')
d2 = ax.bar(dates, nap, bottom=sleep, label='Nap Hours')

# Annotate total rest hours on top of each bar
for i, total in enumerate(rest):
    ax.text(i, total + 0.1, f"{total:.1f}", ha='center', va='bottom', fontsize=9, fontweight='bold')

# Annotate % breakdown within each bar
for i, (s, n) in enumerate(zip(sleep, nap)):
    total = s + n
    if total > 0:
        sleep_pct = 100 * s / total
        nap_pct = 100 * n / total
        ax.text(i, s / 2, f"{sleep_pct:.0f}%", ha='center', va='center', color='white', fontsize=8, fontweight='bold')
        if n > 0:
            ax.text(i, s + n / 2, f"{nap_pct:.0f}%", ha='center', va='center', color='white', fontsize=8, fontweight='bold')

ax.set_ylabel('Hours')
ax.set_xlabel('Date')
ax.set_title('Rest data for Jan 2026')
ax.legend()
plt.xticks(rotation=45, ha='right')
plt.tight_layout()
plt.savefig('garmin_exports/daily_rest_barchart.png')
plt.show()
