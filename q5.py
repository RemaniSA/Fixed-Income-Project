# %%
import os
import pandas as pd
import numpy as np
import QuantLib as ql
import matplotlib.pyplot as plt

from q1 import bond_characteristics
from q2 import load_euribor
from q3 import build_curves

# ----------------------------
# 0. setup and load curve
# ----------------------------

ROOT_PATH = os.path.dirname(__file__)
vol_path = os.path.join(ROOT_PATH, 'datasets', 'shifted_black_vols.csv')
euribor_path = os.path.join(ROOT_PATH, 'datasets', 'HistoricalEuribor.csv')

euribor_df = load_euribor(euribor_path)

ql.Settings.instance().evaluationDate = ql.Date(14, 11, 2024)
eval_date = ql.Settings.instance().evaluationDate

log_cubic_curve = build_curves()["Log-Cubic"]
calendar = ql.TARGET()

cap_rate = bond_characteristics["Cap"]
floor_rate = bond_characteristics["Floor"]
notional = bond_characteristics["Nominal Value"]
settlement_lag = bond_characteristics["Settlement Lag"]
issue_date = ql.Date(bond_characteristics["Issue Date"].day,
                     bond_characteristics["Issue Date"].month,
                     bond_characteristics["Issue Date"].year)
maturity_date = ql.Date(29, 7, 2027)
frequency = ql.Quarterly
day_counter = ql.Actual360()
shift = 0.03

# ----------------------------
# 1. load and process vol surface
# ----------------------------

def load_shifted_vol_surface(filepath):
    df = pd.read_csv(filepath)
    df = df.drop(columns=["STK", "ATM"], errors="ignore")
    df["Maturity"] = df["Maturity"].astype(float)
    df.set_index("Maturity", inplace=True)
    df.columns = df.columns.astype(float)
    return df / 100

vol_surface = load_shifted_vol_surface(vol_path)

def interpolate_vol(maturity, strike_percent):
    if maturity not in vol_surface.index:
        maturity = min(vol_surface.index, key=lambda x: abs(x - maturity))
    row = vol_surface.loc[maturity]
    strikes = row.index.to_numpy()
    vols = row.values
    return np.interp(strike_percent, strikes, vols)

# ----------------------------
# 2. build cap/floor schedule and leg
# ----------------------------

schedule = ql.Schedule(
    max(eval_date, issue_date), maturity_date,
    ql.Period(frequency),
    calendar,
    ql.ModifiedFollowing, ql.ModifiedFollowing,
    ql.DateGeneration.Forward, False
)

index = ql.Euribor3M(ql.YieldTermStructureHandle(log_cubic_curve))

# Bulk-load all fixings from historical data
for dt, row in euribor_df.iterrows():
    fixing_value = row["3M"]

    if pd.isna(fixing_value):
        continue  # skip NaNs

    fixing_date = ql.Date(dt.day, dt.month, dt.year)

    if index.isValidFixingDate(fixing_date):
        fixing_rate = fixing_value / 100

        try:
            index.addFixing(fixing_date, fixing_rate, forceOverwrite=False)
        except RuntimeError:
            # Skip if duplicate and already present
            continue



float_leg = ql.IborLeg([notional], schedule, index)

# ----------------------------
# 3. create cap and floor instruments
# ----------------------------

cap = ql.Cap(float_leg, [cap_rate])
floor = ql.Floor(float_leg, [floor_rate])

maturity = round(day_counter.yearFraction(eval_date, maturity_date))
vol_cap = interpolate_vol(maturity, cap_rate * 100)
vol_floor = interpolate_vol(maturity, floor_rate * 100)

# ----------------------------
# 4. assign pricing engine
# ----------------------------

def make_engine(vol):
    return ql.BlackCapFloorEngine(
        ql.YieldTermStructureHandle(log_cubic_curve),
        ql.QuoteHandle(ql.SimpleQuote(vol)),
        day_counter,
        shift
    )

cap.setPricingEngine(make_engine(vol_cap))
floor.setPricingEngine(make_engine(vol_floor))

npv_cap = cap.NPV()
npv_floor = floor.NPV()

# ----------------------------
# 5. results
# ----------------------------

print(f"cap leg NPV (short):  {-npv_cap:.4f}")
print(f"floor leg NPV (long): {npv_floor:.4f}")
print(f"net option value (floor - cap): {npv_floor - npv_cap:.4f}")

# ----------------------------
# 6. plot volatility surface
# ----------------------------

maturities = vol_surface.index.values
strikes = vol_surface.columns.values
M, S = np.meshgrid(strikes, maturities)
V = vol_surface.values

fig = plt.figure(figsize=(10, 6))
ax = fig.add_subplot(111, projection='3d')
surf = ax.plot_surface(S, M, V, cmap='viridis', edgecolor='k', linewidth=0.3)

ax.set_title("Shifted Black Volatility Surface", fontsize=14)
ax.set_xlabel("Strike (%)")
ax.set_ylabel("Maturity (Years)")
ax.set_zlabel("Implied Volatility")

fig.colorbar(surf, shrink=0.5, aspect=10)
plt.tight_layout()
plt.show()
# %%
