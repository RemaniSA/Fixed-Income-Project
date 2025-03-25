#%%
#%%
import QuantLib as ql
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from q1 import bond_characteristics
from q3 import build_curves

# --- Shift Helpers ---
def apply_parallel_shift(rates, shift_bps=10):
    return [r + shift_bps / 10000 for r in rates]

def apply_slope_shift(rates):
    n = len(rates)
    return [r + (0.001 * (2 * i / n - 1)) for i, r in enumerate(rates)]  # -10bps to +10bps

def apply_curvature_shift(rates):
    n = len(rates)
    mid, width, bump = n // 2, n // 4, 0.001
    return [r + bump * np.exp(-((i - mid)**2) / (2 * width**2)) for i, r in enumerate(rates)]

def make_zero_curve(dates, shifted_rates, calendar, day_counter):
    curve = ql.ZeroCurve(dates, shifted_rates, day_counter, calendar)
    curve.enableExtrapolation()
    return curve

# --- Setup ---
spot_date = ql.Date(26, 11, 2024)
ql.Settings.instance().evaluationDate = spot_date
calendar = ql.TARGET()
day_counter_curve = ql.Actual360()
day_counter_coupon = ql.Thirty360(ql.Thirty360.BondBasis)

# Load base curve
base_curve = build_curves()["Log-Cubic"]
dates = base_curve.dates()
date_labels = [d.ISO() for d in dates]
base_rates = [base_curve.zeroRate(d, day_counter_curve, ql.Continuous).rate() for d in dates]
base_dfs = [base_curve.discount(d) for d in dates]

# Build shifted curves
shifted_curves = {
    "Base": base_curve,
    "Parallel +10bps": make_zero_curve(dates, apply_parallel_shift(base_rates), calendar, day_counter_curve),
    "Slope +10bps": make_zero_curve(dates, apply_slope_shift(base_rates), calendar, day_counter_curve),
    "Curvature +10bps": make_zero_curve(dates, apply_curvature_shift(base_rates), calendar, day_counter_curve)
}

# --- Bond Characteristics ---
frequency = ql.Quarterly
notional = bond_characteristics["Nominal Value"]
cap = bond_characteristics["Cap"]
floor = bond_characteristics["Floor"]
settlement_lag = bond_characteristics["Settlement Lag"]

issue_date = ql.Date(bond_characteristics["Issue Date"].day,
                     bond_characteristics["Issue Date"].month,
                     bond_characteristics["Issue Date"].year)
maturity_date = ql.Date(29, 7, 2027)

schedule = ql.Schedule(
    issue_date, maturity_date,
    ql.Period(frequency),
    calendar,
    ql.ModifiedFollowing, ql.ModifiedFollowing,
    ql.DateGeneration.Forward, False
)

# --- Pricing Function ---
def get_forward_rate(start, end, curve):
    safe_start = max(start, spot_date)
    return curve.forwardRate(safe_start, end, day_counter_curve, ql.Simple).rate() if safe_start < end else 0.0

def compute_gross_price(curve):
    cashflows = []
    for i in range(len(schedule) - 1):
        start = schedule[i]
        end = schedule[i + 1]
        if end <= spot_date:
            continue
        if start < spot_date:
            reset = calendar.advance(start, -settlement_lag, ql.Days)
            start_for_fwd = reset if spot_date >= reset else spot_date
        else:
            start_for_fwd = start
        fwd = get_forward_rate(start_for_fwd, end, curve)
        rate = min(max(fwd, floor), cap)
        yf = day_counter_coupon.yearFraction(start, end)
        coupon = notional * rate * yf
        df = curve.discount(end)
        cashflows.append(coupon * df)
    # redemption
    cashflows.append(notional * curve.discount(maturity_date))
    return sum(cashflows)

# --- Accrued Interest Calculation ---
def compute_accrued(curve):
    for i in range(len(schedule) - 1):
        start = schedule[i]
        end = schedule[i + 1]
        if start < spot_date <= end:
            reset = calendar.advance(start, -settlement_lag, ql.Days)
            start_for_fwd = reset if spot_date >= reset else spot_date
            fwd = get_forward_rate(start_for_fwd, end, curve)
            rate = min(max(fwd, floor), cap)
            yf = day_counter_coupon.yearFraction(start, spot_date)
            return notional * rate * yf
    return 0.0

# --- Pricing for Each Scenario ---
price_summary = {}
for label, curve in shifted_curves.items():
    gross = compute_gross_price(curve)
    accrued = compute_accrued(curve)
    clean = gross - accrued
    price_summary[label] = {
        "Gross Price": round(gross, 4),
        "Accrued Interest": round(accrued, 4),
        "Clean Price": round(clean, 4)
    }

df_prices = pd.DataFrame(price_summary).T
print("\n📊 Bond Price Sensitivity Summary:")
print(df_prices)

# --- Plot Spot Rate Curves ---
plt.figure(figsize=(12, 6), dpi=150)
for name, curve in shifted_curves.items():
    rates = [curve.zeroRate(d, day_counter_curve, ql.Continuous).rate() * 100 for d in dates]
    plt.plot(date_labels, rates, label=name)
plt.title("Spot Rate Curves: Original vs Shifted")
plt.ylabel("Zero Rate (%)")
plt.xlabel("Maturity Date")
plt.xticks(rotation=45)
plt.grid(True)
plt.legend()
plt.tight_layout()
plt.show()

# --- Plot Discount Factor Curves ---
plt.figure(figsize=(12, 6), dpi=150)
for name, curve in shifted_curves.items():
    dfs = [curve.discount(d) for d in dates]
    plt.plot(date_labels, dfs, label=name)
plt.title("Discount Factor Curves: Original vs Shifted")
plt.ylabel("Discount Factor")
plt.xlabel("Maturity Date")
plt.xticks(rotation=45)
plt.grid(True)
plt.legend()
plt.tight_layout()
plt.show()

# --- Save Output ---
df_prices.to_csv("q11_bond_price_sensitivity.csv")

#%%