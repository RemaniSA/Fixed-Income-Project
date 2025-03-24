import os
import pandas as pd
from datetime import datetime
import matplotlib.pyplot as plt
import numpy as np

from q1 import bond_characteristics

ROOT_PATH = os.path.dirname(__file__)
euribor_rates_file_path = ROOT_PATH + '/datasets/HistoricalEuribor.csv'
holidays_file_path = ROOT_PATH + '/datasets/Holidays.csv'


def modified_following_business_date(end_date, holidays):
    """
    Adjust a date according to the modified following business day convention.
    If pushing to the next business day changes the month, go to the previous one.

    Parameters:
    - end_date: datetime.date or string
    - holidays: list of datetime.date or strings

    Returns:
    - datetime.date
    """
    end_date = np.datetime64(pd.to_datetime(end_date).date())
    holidays = np.array(pd.to_datetime(holidays).date, dtype='datetime64[D]')

    foll_bus_date = np.busday_offset(end_date - 1, 1, holidays=holidays)
    prev_bus_date = np.busday_offset(end_date + 1, -1, holidays=holidays)

    if pd.to_datetime(foll_bus_date).month == pd.to_datetime(end_date).month:
        return pd.to_datetime(foll_bus_date).date()
    else:
        return pd.to_datetime(prev_bus_date).date()


def load_and_clean_rates(filepath):
    df_rates = pd.read_csv(filepath, delimiter=";", parse_dates=["Date"])
    df_rates = df_rates.iloc[:, :6]
    df_rates.columns = ["Date", "1W", "1M", "3M", "6M", "12M"]
    df_rates.set_index("Date", inplace=True)
    df_rates[df_rates.columns] = df_rates[df_rates.columns].replace(',', '.', regex=True)
    df_rates[df_rates.columns] = df_rates[df_rates.columns].astype(float, errors='ignore')
    return df_rates


def generate_coupon_dates(start_date, end_date, frequency_months):
    dates = []
    d = start_date
    while d <= end_date:
        dates.append(d)
        d += pd.DateOffset(months=frequency_months)
    return dates


def adjust_for_weekend(date):
    while date.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
        date += pd.DateOffset(days=1)
    return date


def is_end_of_month(date):
    return (date + pd.DateOffset(days=1)).month != date.month


def adjust_eom(date, holidays):
    return pd.to_datetime(modified_following_business_date(date, holidays))


def find_reset_date(start_date, business_days_before=2):
    reset_date = start_date
    days_to_move = business_days_before
    while days_to_move > 0:
        reset_date -= pd.DateOffset(days=1)
        if reset_date.weekday() < 5:
            days_to_move -= 1
    return reset_date


def get_reference_rate(date, df_rates):
    if date in df_rates.index:
        return df_rates.loc[date, "3M"]
    else:
        return None


def build_coupon_schedule(coupon_dates):
    schedule = []
    for i in range(len(coupon_dates) - 1):
        schedule.append({
            "coupon_index": i + 1,
            "start_date_unadj": coupon_dates[i],
            "end_date_unadj": coupon_dates[i + 1]
        })
    return pd.DataFrame(schedule)


def main():
    df_rates = load_and_clean_rates(euribor_rates_file_path)
    df_holidays = pd.read_csv(holidays_file_path, parse_dates=["Date"])
    # Print type of df_holidays["Date"] columns
    # df_holidays.set_index("Date", inplace=True)
    print(df_holidays["Date"].dtype)
    df_holidays["Date"] = pd.to_datetime(df_holidays["Date"])
    print(df_holidays.head())
    # holidays = pd.to_datetime(df_holidays["Date"]).dt.date.tolist()  # Convert holidays to a list of dates
    # print(holidays)

    start_date = datetime(2022, 7, 29)
    current_date = datetime.now()
    frequency_months = 3  # Quarterly

    coupon_dates = generate_coupon_dates(start_date, current_date, frequency_months)
    df_schedule = build_coupon_schedule(coupon_dates)

    # Use modified_following_business_date for start_date and end_date adjustments
    df_schedule["start_date"] = df_schedule["start_date_unadj"].apply(lambda date: modified_following_business_date(date, holidays))
    df_schedule["end_date"] = df_schedule["end_date_unadj"].apply(lambda date: modified_following_business_date(date, holidays))

    df_schedule["reset_date"] = df_schedule["start_date"].apply(find_reset_date)
    df_schedule["reference_rate"] = df_schedule["reset_date"].apply(lambda d: get_reference_rate(d, df_rates))

    df_schedule["coupon_rate"] = df_schedule["reference_rate"].clip(
        lower=bond_characteristics["Floor"],
        upper=bond_characteristics["Cap"]
    )

    notional = bond_characteristics["Nominal Value"]
    day_count_fraction = 0.25  # Approximate for quarterly 30/360

    df_schedule["coupon_amount"] = (
        notional * df_schedule["reference_rate"] * day_count_fraction
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

    # Plot
    plt.plot(df_result["start_date"], df_result["coupon_rate"], marker='o')
    plt.title("Coupon Rate Over Time")
    plt.xlabel("Coupon Start Date")
    plt.ylabel("Coupon Rate")
    plt.grid(True)
    plt.xticks(rotation=46)
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
