# %%
import os
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
import QuantLib as ql
from q1 import bond_characteristics  # we need cap, floor, notional, issue date

# ----------------------------
# 0. file paths and bond details
# ----------------------------

ROOT_PATH = os.path.dirname(__file__)
euribor_rates_file_path = os.path.join(ROOT_PATH, 'datasets', 'HistoricalEuribor_alt.csv')
holidays_file_path = os.path.join(ROOT_PATH, 'datasets', 'Holidays.csv')

# ----------------------------
# 1. load 3MEUR data and holidays
# ----------------------------

def load_euribor(filepath):
    df = pd.read_csv(filepath)
    df.columns = df.columns.str.strip()
    df = df[["Date", "3M"]]
    df["Date"] = pd.to_datetime(df["Date"])
    df.set_index("Date", inplace=True)
    return df

def load_holidays(filepath):
    df = pd.read_csv(filepath, parse_dates=["Date"])
    return [d.date() for d in df["Date"]]

# ----------------------------
# 2. helper function that converts QuantLib date into datetime
# ----------------------------

def ql_to_datetime(qldate):
    return datetime(qldate.year(), qldate.month(), qldate.dayOfMonth()).date()

# ----------------------------
# 3. build historical coupon rates and coupons
# ----------------------------

def build_historical_coupons(euribor_df, holidays):
    # bond characteristics
    calendar = ql.TARGET()
    business_convention = ql.ModifiedFollowing
    fixing_days = bond_characteristics["Settlement Lag"]
    frequency = ql.Quarterly
    notional = bond_characteristics["Nominal Value"]
    cap = bond_characteristics["Cap"]
    floor = bond_characteristics["Floor"]
    start_date = ql.Date(bond_characteristics["Issue Date"].day,
                         bond_characteristics["Issue Date"].month,
                         bond_characteristics["Issue Date"].year)
    end_date = ql.Date.todaysDate()
    day_counter = ql.Actual360()

    # build schedule of coupon payments
    schedule = ql.Schedule(
        start_date, end_date,
        ql.Period(frequency),
        calendar,
        business_convention, business_convention,
        ql.DateGeneration.Forward, False
    )

    # loop over periods
    coupon_data = []
    for i in range(len(schedule) - 1):
        start = schedule[i]
        end = schedule[i + 1]
        reset = calendar.advance(start, -fixing_days, ql.Days)
        reset_dt = ql_to_datetime(reset)

        # collect EUR rate as reference rate
        rate = euribor_df.loc[euribor_df.index == pd.to_datetime(reset_dt), "3M"]
        if rate.empty:
            rate = np.nan
        else:
            rate = rate.iloc[0] / 100

        # cap/floor adjustment
        if not np.isnan(rate):
            capped_rate = max(min(rate, cap), floor)
        else:
            capped_rate = np.nan

        # year fraction and coupon calc.
        yf = day_counter.yearFraction(start, end)
        coupon = notional * capped_rate * yf if not np.isnan(capped_rate) else np.nan

        coupon_data.append({
            "Reset Date": reset_dt,
            "Start Date": ql_to_datetime(start),
            "End Date": ql_to_datetime(end),
            "Reference Rate (3M)": rate * 100 if rate else np.nan,
            "Coupon Rate (%)": capped_rate * 100 if capped_rate else np.nan,
            "Coupon Amount": coupon
        })

    return pd.DataFrame(coupon_data)

# ----------------------------
# 4. run and plot
# ----------------------------

def main():
    euribor_df = load_euribor(euribor_rates_file_path)
    holidays = load_holidays(holidays_file_path)

    df_coupons = build_historical_coupons(euribor_df, holidays)
    print(df_coupons)

    # plot historical capped/floored coupon rates
    plt.figure(figsize=(10, 5))
    plt.plot(df_coupons["Start Date"], df_coupons["Coupon Rate (%)"], marker="o")
    plt.title("Historical Capped/Floored Coupon Rates")
    plt.xlabel("Start Date")
    plt.ylabel("Coupon Rate (%)")
    plt.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()

# %%
