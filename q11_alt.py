#%%
import os
import pandas as pd
import numpy as np
import QuantLib as ql
import matplotlib.pyplot as plt
import re

from q8 import model_clean_price
from q3 import curve_day_counter, eval_date, calendar, get_curve_data, dates, date_strings
from q1 import bond_characteristics
from q8 import maturity_date, schedule, notional, cap, floor, day_counter_curve, day_counter_coupon

# ----------------------------
# 1. Load bumped market data with dynamic inputs
# ----------------------------

def period_to_years(period):
    """
    Convert a QuantLib Period to a fraction of a year.
    """
    unit = period.units()
    if unit == ql.Days:
        return period.length() / 365.0
    elif unit == ql.Weeks:
        return period.length() / 52.0
    elif unit == ql.Months:
        return period.length() / 12.0
    elif unit == ql.Years:
        return float(period.length())
    else:
        raise ValueError("Unknown time unit in period")

def load_bumped_helpers(filepath, bump_fn):
    # we use the same mapping as in q3.py but with bumped rates
    deposit_ric_map = {
        "EURSWD": ql.Period(1, ql.Weeks),
        "EUR1MD": ql.Period(1, ql.Months),
        "EUR3MD": ql.Period(3, ql.Months),
        "EUR6MD": ql.Period(6, ql.Months),
        "EUR9MD": ql.Period(9, ql.Months)
    }

    df_depo = pd.read_excel(filepath, sheet_name="Deposit Rates")
    df_swap = pd.read_excel(filepath, sheet_name="IRS Rates")

    depo_helpers = []
    for _, row in df_depo.iterrows():
        ric = row["RIC"]
        if ric not in deposit_ric_map:
            continue
        maturity_period = deposit_ric_map[ric]
        maturity_years = period_to_years(maturity_period)
        bumped_rate = bump_fn(maturity_years, row["Last"])
        helper = ql.DepositRateHelper(
            ql.QuoteHandle(ql.SimpleQuote(bumped_rate / 100)),
            maturity_period,
            bond_characteristics['Nominal Value'],  # fixing days
            calendar,
            ql.ModifiedFollowing,
            True,
            ql.Actual360()
        )
        depo_helpers.append(helper)

    def extract_maturity(name):
        match = re.search(r'(\d+)(?=Y)', name)
        return int(match.group(1)) if match else None

    swap_helpers = []
    for _, row in df_swap.iterrows():
        maturity = extract_maturity(row["Name"])
        if maturity is None or maturity < 1:
            continue
        bumped_rate = bump_fn(maturity, row["Last"])
        helper = ql.SwapRateHelper(
            ql.QuoteHandle(ql.SimpleQuote(bumped_rate / 100)),
            ql.Period(maturity, ql.Years),
            calendar,
            ql.Annual,
            ql.ModifiedFollowing,
            ql.Thirty360(ql.Thirty360.BondBasis),
            ql.Euribor3M()
        )
        swap_helpers.append(helper)

    return depo_helpers + swap_helpers

def build_bumped_curve(bump_fn):
    path = os.path.join(os.path.dirname(__file__), "datasets", "MarketData.xlsx")
    helpers = load_bumped_helpers(path, bump_fn)
    return ql.PiecewiseLogCubicDiscount(eval_date, helpers, curve_day_counter)

# ----------------------------
# 2. Define bump functions
# ----------------------------

def bump_parallel(_, rate): 
    return rate + 0.10

def bump_parallel_down(_, rate): 
    return rate - 0.10

def bump_slope(maturity, rate): 
    return rate + 0.10 if maturity <= 2 else rate - 0.10

def bump_slope_flatten(maturity, rate): 
    return rate - 0.10 if maturity <= 2 else rate + 0.10

def bump_curvature(maturity, rate): 
    return rate + 0.10 if 2 <= maturity <= 5 else rate

def bump_curvature_dip(maturity, rate): 
    return rate - 0.10 if 2 <= maturity <= 5 else rate

# ----------------------------
# 3. Recalculate clean price using bumped yield curve
# ----------------------------

def price_with_curve(yield_curve):
    cf_rows = []
    for i in range(len(schedule) - 1):
        start = schedule[i]
        end = schedule[i + 1]
        if end <= eval_date:
            continue
        start_for_fwd = max(start, eval_date)
        fwd_rate = yield_curve.forwardRate(start_for_fwd, end, day_counter_curve, ql.Simple).rate()
        eff_rate = min(max(fwd_rate, floor), cap)
        yf = day_counter_coupon.yearFraction(start, end)
        coupon = notional * eff_rate * yf
        df = yield_curve.discount(end)
        pv = coupon * df
        cf_rows.append(pv)

    redemp = notional * yield_curve.discount(maturity_date)
    gross = sum(cf_rows) + redemp

    accrued = 0.0
    for i in range(len(schedule) - 1):
        start = schedule[i]
        end = schedule[i + 1]
        if start < eval_date <= end:
            safe_start = max(start, eval_date)
            fwd = yield_curve.forwardRate(safe_start, end, day_counter_curve, ql.Simple).rate()
            eff = min(max(fwd, floor), cap)
            yf_accrued = day_counter_coupon.yearFraction(start, eval_date)
            accrued = notional * eff * yf_accrued
            break
    return gross - accrued

# ----------------------------
# 4. Run all bump scenarios
# ----------------------------

scenarios = {
    "Base": lambda m, r: r,
    "Level +10bps": bump_parallel,
    "Level -10bps": bump_parallel_down,
    "Slope Steepen": bump_slope,
    "Slope Flatten": bump_slope_flatten,
    "Curvature Bump": bump_curvature,
    "Curvature Dip": bump_curvature_dip
}

curve_results = {}
price_results = []

for name, bump_fn in scenarios.items():
    curve = build_bumped_curve(bump_fn)
    clean_price = price_with_curve(curve)
    curve_results[name] = curve
    price_results.append({
        "Scenario": name,
        "Clean Price": round(clean_price, 4),
        "Δ vs Base": round(clean_price - model_clean_price, 4)
    })

df_results = pd.DataFrame(price_results)

# ----------------------------
# 5. Output results
# ----------------------------

print("\nQ11: Sensitivity of Clean Price to Term Structure Shape")
print(df_results)

# ----------------------------
# 6. Plot: Yield Curve Comparisons
# ----------------------------

def plot_group(title, keys):
    plt.figure(figsize=(10, 5))
    for key in keys:
        _, spot, _ = get_curve_data(curve_results[key], curve_day_counter)
        plt.plot(date_strings, spot, label=key)
    plt.title(f"{title} Shift: Zero Rate Curves")
    plt.xlabel("Maturity Date")
    plt.ylabel("Zero Rate (%)")
    plt.xticks(date_strings[::5], rotation=45)
    plt.grid(axis='y')
    plt.legend()
    plt.tight_layout()
    plt.show()

plot_group("Level", ["Base", "Level +10bps", "Level -10bps"])
plot_group("Slope", ["Base", "Slope Steepen", "Slope Flatten"])
plot_group("Curvature", ["Base", "Curvature Bump", "Curvature Dip"])
# %%
