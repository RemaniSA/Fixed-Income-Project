# %%
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import QuantLib as ql
from datetime import date

# Import bond characteristics and helper functions from Q1, Q3, Q5, and Q8
from q1 import bond_characteristics, get_next_payment_date
from q3 import build_curves
from q5 import interpolate_vol

# ----------------------------
# 1. Setup Evaluation Date, Bond Data & Coupon Schedule
# ----------------------------
trade_date = bond_characteristics["Trade Date"]
ql.Settings.instance().evaluationDate = ql.Date(trade_date.day, trade_date.month, trade_date.year)

calendar = ql.TARGET()

# Define day count conventions:
discount_day_counter = ql.Actual360()
coupon_day_counter = ql.Thirty360(ql.Thirty360.BondBasis)

# Coupon frequency is quarterly
frequency = ql.Quarterly

# Convert issue and maturity dates to QuantLib Dates
issue_date = ql.Date(bond_characteristics["Issue Date"].day,
                     bond_characteristics["Issue Date"].month,
                     bond_characteristics["Issue Date"].year)
maturity_date = ql.Date(bond_characteristics["Maturity Date"].day,
                        bond_characteristics["Maturity Date"].month,
                        bond_characteristics["Maturity Date"].year)

# Build the coupon schedule using Modified Following convention
schedule = ql.Schedule(issue_date, maturity_date,
                       ql.Period(frequency),
                       calendar,
                       ql.ModifiedFollowing, ql.ModifiedFollowing,
                       ql.DateGeneration.Forward, False)

# ----------------------------
# 2. Build the Yield Curve and Create the Index
# ----------------------------
curves = build_curves()
yield_curve = curves["Log-Cubic"]
discount_curve_handle = ql.YieldTermStructureHandle(yield_curve)
index = ql.Euribor3M(discount_curve_handle)

# ----------------------------
# 3. Define Parameters and Prepare for Coupon Computation
# ----------------------------
notional = bond_characteristics["Nominal Value"]
floor_rate = bond_characteristics["Floor"]
cap_rate = bond_characteristics["Cap"]

# For a quarterly period using 30/360, the accrual factor is approximately 0.25
accrual_target = 0.25

# List to store coupon cash flow details
coupon_cashflows = []

# ----------------------------
# 4. Loop Over Coupon Periods After the Trade Date to Compute Expected Coupon Amounts
# ----------------------------
def ql_date_to_py_date(ql_date):
    return date(ql_date.year(), ql_date.month(), ql_date.dayOfMonth())


for i in range(1, len(schedule)):
    start_date = schedule[i-1]
    end_date = schedule[i]
    
    # Only consider coupon periods starting after the evaluation date
    if start_date < ql.Settings.instance().evaluationDate:
        continue

    # Compute accrual factor using 30/360 day count convention
    accrual = coupon_day_counter.yearFraction(start_date, end_date)
    
    # Compute the forward rate for the period (using simple compounding)
    fwd_rate = discount_curve_handle.forwardRate(start_date, end_date, discount_day_counter, ql.Simple).rate()
    
    # Apply floor and cap: effective rate = min(max(fwd_rate, floor_rate), cap_rate)
    effective_rate = min(max(fwd_rate, floor_rate), cap_rate)
    
    # Compute expected coupon amount for the period
    coupon_amount = notional * effective_rate * accrual
    
    # Append the payment date and computed coupon amount
    coupon_cashflows.append({
        "Payment Date": ql_date_to_py_date(end_date),
        "Expected Coupon (EUR)": coupon_amount
    })

# Create a DataFrame of coupon cash flows
df_coupons = pd.DataFrame(coupon_cashflows)

# ----------------------------
# 5. Plot the Expected Coupon Cash Flows
# ----------------------------
plt.figure(figsize=(12, 6))
plt.plot(df_coupons["Payment Date"], df_coupons["Expected Coupon (EUR)"],
         marker='o', linestyle='-', linewidth=2, color='blue', label="Expected Coupon")
plt.xlabel("Coupon Payment Date")
plt.ylabel("Expected Coupon Amount (EUR)")
plt.title("Expected Coupon Cash Flows (Excluding Notional)")
plt.grid(True)
plt.legend()
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()

# ----------------------------
# 6. Print Summary Table and Commentary
# ----------------------------
print("Expected Coupon Cash Flow Details:")
print(df_coupons.to_string(index=False))


# %%
