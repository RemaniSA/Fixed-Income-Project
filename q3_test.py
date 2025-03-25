####################################
# TO DO: Fix Part 7 where we attempt to implement a Max Smoothness Fwd Curve using
# cxvpy. This is based on the paper by Adams and Van Deventer (1994) called
# "Fitting Yield Curves and Forward Rate Curves with Maximum Smoothness"
###################################

# %%
import os
import QuantLib as ql
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import re
import cvxpy as cp

# ----------------------------
# 0. SetUp
# ----------------------------

# Set evaluation date (spot date = trade date + 2 days = November 26, 2024)
spot_date = ql.Date(26, 11, 2024)
ql.Settings.instance().evaluationDate = spot_date
calendar = ql.TARGET()
fixingDays = 2

# Choose day counters
deposit_day_counter = ql.Actual360()
curve_day_counter   = ql.Actual360()  # Consistent use throughout

# ----------------------------
# 1. Load Deposit and IRS Rate Helpers from Excel
# ----------------------------

def load_rate_helpers(file_path, fixing_days=2):
    calendar = ql.TARGET()
    deposit_day_counter = ql.Actual360()

    # Map RICs to QuantLib Periods
    deposit_ric_map = {
        "EURSWD": ql.Period(1, ql.Weeks),
        "EUR1MD": ql.Period(1, ql.Months),
        "EUR3MD": ql.Period(3, ql.Months),
        "EUR6MD": ql.Period(6, ql.Months),
        "EUR9MD": ql.Period(9, ql.Months)
    }

    deposits_df = pd.read_excel(file_path, sheet_name="Deposit Rates")
    irs_df = pd.read_excel(file_path, sheet_name="IRS Rates")

    # Deposit Helpers
    depo_helpers = [
        ql.DepositRateHelper(
            ql.QuoteHandle(ql.SimpleQuote(row['Last'] / 100.0)),
            deposit_ric_map[row['RIC']],
            fixing_days,
            calendar,
            ql.ModifiedFollowing,
            True,
            deposit_day_counter
        )
        for _, row in deposits_df.iterrows() if row['RIC'] in deposit_ric_map
    ]

    # IRS Helpers
    def extract_maturity(name):
        match = re.search(r'(\d+)(?=Y)', name)
        return int(match.group(1)) if match else None

    swap_helpers = [
        ql.SwapRateHelper(
            ql.QuoteHandle(ql.SimpleQuote(row['Last'] / 100.0)),
            ql.Period(maturity, ql.Years),
            calendar,
            ql.Annual,
            ql.ModifiedFollowing,
            ql.Thirty360(ql.Thirty360.BondBasis),
            ql.Euribor3M()
        )
        for _, row in irs_df.iterrows()
        if (maturity := extract_maturity(row['Name'])) and maturity > 1
    ]

    return depo_helpers + swap_helpers

# Load from Excel
ROOT_PATH = os.path.dirname(__file__)
market_data_file_path = os.path.join(ROOT_PATH, 'datasets', 'MarketData.xlsx')
rate_helpers = load_rate_helpers(market_data_file_path)

# ----------------------------
# 2. Build the bootstrapped curves using different interpolators
# ----------------------------

linear_curve = ql.PiecewiseLinearZero(spot_date, rate_helpers, curve_day_counter)
flat_curve   = ql.PiecewiseFlatForward(spot_date, rate_helpers, curve_day_counter)
cubic_curve  = ql.PiecewiseCubicZero(spot_date, rate_helpers, curve_day_counter)
log_cubic_curve = ql.PiecewiseLogCubicDiscount(spot_date, rate_helpers, curve_day_counter)

curves = {"Linear": linear_curve, "Flat": flat_curve, "Cubic": cubic_curve, "Log-Cubic": log_cubic_curve}

# ----------------------------
# 3. Set up grids for curve evaluation
# ----------------------------

end_date = calendar.advance(spot_date, ql.Period(60, ql.Years))
n_points = 100
dates = [spot_date + ql.Period(int(i * (end_date.serialNumber() - spot_date.serialNumber()) / n_points), ql.Days)
         for i in range(n_points + 1)]
date_strings = [d.ISO() for d in dates]

max_forward_date = calendar.advance(end_date, -ql.Period(1, ql.Years))

# ----------------------------
# 4. Define function to extract curve data
# ----------------------------

def get_curve_data(curve, day_counter):
    discount_factors = [curve.discount(d) for d in dates]
    spot_rates = [curve.zeroRate(d, day_counter, ql.Continuous).rate() * 100 for d in dates]
    forward_rates = []
    for d in dates:
        if d <= max_forward_date:
            d1 = calendar.advance(d, ql.Period(1, ql.Years))
            fwd = curve.forwardRate(d, d1, day_counter, ql.Continuous).rate() * 100
            forward_rates.append(fwd)
        else:
            forward_rates.append(np.nan)
    return discount_factors, spot_rates, forward_rates

# ----------------------------
# 5. Loop over curves, build DataFrames, plot, and show heads
# ----------------------------

curve_dataframes = {}

for name, curve in curves.items():
    disc, spot, fwd = get_curve_data(curve, curve_day_counter)

    df = pd.DataFrame({
        'Date': date_strings,
        'Discount Factor': disc,
        'Spot Rate (%)': spot,
        '1Y Forward Rate (%)': fwd
    }).set_index('Date')
    curve_dataframes[name] = df

    # Plot the curves in a 3-panel figure
    fig, axs = plt.subplots(3, 1, figsize=(10, 15), sharex=True)
    fig.suptitle(f'{name} Interpolation Yield Curve', fontsize=16, y=0.96)

    axs[0].plot(date_strings, disc, label=name)
    axs[0].set_ylabel('Discount Factor')
    axs[0].set_title('Discount Factors vs Maturity')
    axs[0].grid(axis='y')

    axs[1].plot(date_strings, spot, label=name, color='orange')
    axs[1].set_ylabel('Spot Rate (%)')
    axs[1].set_title('Spot Rates vs Maturity')
    axs[1].grid(axis='y')

    axs[2].plot(date_strings, fwd, label=name, color='green')
    axs[2].set_ylabel('1Y Forward Rate (%)')
    axs[2].set_title('1Y Forward Rates vs Maturity')
    axs[2].set_xlabel('Maturity Date')
    axs[2].grid(axis='y')

    # Reduce number of x-ticks for readability
    tick_count = 5
    plt.xticks(date_strings[::tick_count], rotation=45)

    plt.tight_layout(rect=[0, 0, 1, 0.99])
    plt.show()

    print(f"{name} Interpolation Yield Curve Data (first 10 rows):")
    print(df.head(10))
    print("\n" + "="*80 + "\n")

# ----------------------------
# 6. Compare Forward Curves Across Interpolators
# ----------------------------

plt.figure(figsize=(12, 6))
for name, df in curve_dataframes.items():
    plt.plot(df.index, df['1Y Forward Rate (%)'], label=name)

plt.title("1Y Forward Rate Curve Comparison")
plt.xlabel("Maturity Date")
plt.ylabel("1Y Forward Rate (%)")
plt.xticks(date_strings[::5], rotation=45)
plt.grid(axis='y')
plt.legend()
plt.tight_layout()
plt.show()

# %%
# ----------------------------
# 7. Build Maximum Smoothness Forward Curve using cvxpy (not native to QuantLib)
# ----------------------------

# Step 1: Define grid of maturities in years (integer points for swap instruments)
T = sorted([helper.latestDate().serialNumber() - spot_date.serialNumber() for helper in rate_helpers])
T_years = [curve_day_counter.yearFraction(spot_date, ql.Date(spot_date.serialNumber() + t)) for t in T]
T_years = sorted(set([round(t, 6) for t in T_years if t > 0 and t <= 60]))

# Step 2: Discount factors as variables
P = cp.Variable(len(T_years))

# Step 3: Define objective — minimize the curvature of the forward curve
# We use second differences of implied forward rates (log(P[i]/P[i-1]))
fwd_rates = [cp.log(P[i - 1] / P[i]) / (T_years[i] - T_years[i - 1]) for i in range(1, len(T_years))]
second_diff = [fwd_rates[i+1] - 2 * fwd_rates[i] + fwd_rates[i-1] for i in range(1, len(fwd_rates) - 1)]
objective = cp.Minimize(cp.sum_squares(cp.vstack(second_diff)))

# Step 4: Add constraints to ensure the curve fits market swap rates
constraints = []

# Initial anchor: P[0] = 1
constraints.append(P[0] == 1.0)

# Deposit constraints: P(T) = 1 / (1 + r * T)
for helper in rate_helpers:
    date = helper.latestDate()
    t = curve_day_counter.yearFraction(spot_date, date)
    if t in T_years and isinstance(helper, ql.DepositRateHelper):
        idx = T_years.index(t)
        rate = helper.quote().value()
        constraints.append(P[idx] == 1 / (1 + rate * t))

# IRS constraints: match present value of fixed leg
for helper in rate_helpers:
    if isinstance(helper, ql.SwapRateHelper):
        swap = helper.swap()
        fixed_schedule = swap.fixedSchedule()
        fixed_leg_times = [curve_day_counter.yearFraction(spot_date, d) for d in fixed_schedule if d > spot_date]
        fixed_leg_times = [round(t, 6) for t in fixed_leg_times if t in T_years]

        if fixed_leg_times:  # ✅ Only process if non-empty
            notional = 1.0
            rate = helper.quote().value()
            alpha = 1.0  # annual payment

            annuity = 0
            for t in fixed_leg_times:
                idx = T_years.index(t)
                annuity += alpha * P[idx]

            last_idx = T_years.index(max(fixed_leg_times))
            constraints.append(rate * annuity + P[last_idx] == 1.0)


# Step 5: Solve
problem = cp.Problem(objective, constraints)
problem.solve()

# Step 6: Convert results into a DataFrame
maxsmooth_df = pd.DataFrame({
    'Maturity (Years)': T_years,
    'Discount Factor': P.value,
    'Spot Rate (%)': [-np.log(p) / t * 100 if p > 0 else np.nan for p, t in zip(P.value, T_years)],
    '1Y Forward Rate (%)': [
        -np.log(P.value[i+1] / P.value[i]) / (T_years[i+1] - T_years[i]) * 100
        if P.value[i] > 0 and P.value[i+1] > 0 else np.nan
        for i in range(len(T_years) - 1)
    ] + [np.nan]
}).set_index('Maturity (Years)')

curve_dataframes['MaxSmooth'] = maxsmooth_df

# Step 7: Plot forward curve comparison including MSFC
plt.figure(figsize=(12, 6))
for name, df in curve_dataframes.items():
    plt.plot(df.index, df['1Y Forward Rate (%)'], label=name)

plt.title("1Y Forward Rate Curve Comparison (Including Max Smoothness)")
plt.xlabel("Maturity (Years)")
plt.ylabel("1Y Forward Rate (%)")
plt.grid(True)
plt.legend()
plt.tight_layout()
plt.show()

# %%
