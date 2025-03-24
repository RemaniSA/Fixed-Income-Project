import os
import sys
from q1 import bond_characteristics

ROOT_PATH = os.path.dirname(__file__)

import pandas as pd
from datetime import datetime
import matplotlib.pyplot as plt

# Data loading and preprocessing
euribor_rates_file_path = ROOT_PATH + '/datasets/HistoricalEuribor.csv'

df_rates = pd.read_csv(euribor_rates_file_path, delimiter=";", parse_dates=["Date"])
df_rates = df_rates.iloc[:, :6]  # Keep only the first 6 columns
df_rates.columns = ["Date", "1W", "1M", "3M", "6M", "12M"]  # Rename columns
df_rates.set_index("Date", inplace=True)  # Make Date the index for easy lookup

# Replace commas with dots in all columns
df_rates[df_rates.columns] = df_rates[df_rates.columns].replace(',', '.', regex=True)

# Convert all columns to float
df_rates[df_rates.columns] = df_rates[df_rates.columns].astype(float, errors='ignore')

# TODO: Check if the start date is correct
start_date = datetime(2022, 7, 29)
current_date = datetime.now()
frequency_months = 3  # Quarterly

# Generate coupon dates
coupon_dates = []
d = start_date
while d <= current_date:
    coupon_dates.append(d)
    d += pd.DateOffset(months=frequency_months)

num_coupons = len(coupon_dates) - 1  # Exclude the last date as it's the start of the next (non-existent) period

# Build coupon schedule
coupon_schedule = []
for i in range(num_coupons):
    coupon_schedule.append({
        "coupon_index": i + 1,
        "start_date_unadj": coupon_dates[i],
        "end_date_unadj": coupon_dates[i + 1]
    })

df_schedule = pd.DataFrame(coupon_schedule)


def adjust_for_weekend(date):
    # If it's Saturday or Sunday, move to Monday
    while date.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
        date += pd.DateOffset(days=1)
    return date

def is_end_of_month(date):
    # Check if adding 1 day crosses into a new month
    return (date + pd.DateOffset(days=1)).month != date.month

def adjust_eom(date):
    # If the unadjusted date is end of month, keep it at end of month
    if is_end_of_month(date):
        # Adjust for weekend first
        date = adjust_for_weekend(date)
        # If after adjusting for weekend, we jumped to next month,
        # we might need a small correction, but this depends on your exact EOM rule.
    else:
        # Normal weekend adjustment
        date = adjust_for_weekend(date)
    return date


df_schedule["start_date"] = df_schedule["start_date_unadj"].apply(adjust_eom)
df_schedule["end_date"]   = df_schedule["end_date_unadj"].apply(adjust_eom)

# TODO: Check if the conventions are correct after this step
def find_reset_date(start_date, business_days_before=2):
    reset_date = start_date
    # Move backward day by day, skipping weekends
    days_to_move = business_days_before
    while days_to_move > 0:
        reset_date -= pd.DateOffset(days=1)
        # Skip weekends
        if reset_date.weekday() < 5:
            days_to_move -= 1
    return reset_date

df_schedule["reset_date"] = df_schedule["start_date"].apply(find_reset_date)

def get_reference_rate(date):
    # Ensure we handle the case if the date isn't in df_rates (e.g., a holiday)
    if date in df_rates.index:
        return df_rates.loc[date, "3M"]
    else:
        # If missing, you could find the nearest previous business day’s rate
        # or some other fallback. For simplicity:
        return None


df_schedule["reference_rate"] = df_schedule["reset_date"].apply(get_reference_rate)

df_schedule["coupon_rate"] = min(max(df_schedule["reference_rate"], bond_characteristics["Floor"]), bond_characteristics["Cap"])

notional = bond_characteristics["Nominal Value"]
day_count_fraction = 0.25  # approximate for a quarter in 30/360

df_schedule["coupon_amount"] = (
    notional
    * df_schedule["reference_rate"]
    * day_count_fraction
)

final_columns = [
    "reset_date",
    "start_date",
    "end_date",
    "reference_rate",
    "coupon_rate",
    "coupon_amount"
]
df_result = df_schedule[final_columns].copy()
print(df_result)

# TODO: The plot is not big enough to show the dates clearly
plt.plot(df_result["start_date"], df_result["coupon_rate"], marker='o')
plt.title("Coupon Rate Over Time")
plt.xlabel("Coupon Start Date")
plt.ylabel("Coupon Rate")
plt.grid(True)
plt.xticks(rotation=46)
plt.show()